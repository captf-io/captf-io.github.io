#!/usr/bin/env python3
# Copyright 2026 The CAPTF Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Check that the custom resource pages document every field of every kind.

The pages under docs/docs/reference/resources/ are written by hand, one per
kind, plus common-fields.md for the fields the Terraform-run kinds share.
This reads the CRDs from a provider repository checkout
(config/crd/bases/*.yaml), lists every field path of each kind, and reports
each one its page does not mention as a code span, such as
`spec.source.image`. Array items are written `[]`:
`spec.variablesFrom[].secretRef.name`. A free-form object (a map) and an
embedded Kubernetes type (OPAQUE, such as `spec.jobs.resources`) are
checked to their own path, not into their keys.

Who documents what:

  - a kind's page names every path of its kind, except below the shared
    workspace fields (COMMON), where naming the field itself is enough;
  - common-fields.md names every path below the COMMON fields, as they
    appear on TerraformCluster (`spec.jobs.resources`), which is where
    those paths are the same for every kind;
  - a template kind's page names the paths outside spec.template.spec, and
    each field directly under spec.template.spec; the rest is the page of
    the kind it is a template for.

Usage: check_resources.py [--provider PATH] [--list KIND]
  --provider  the provider checkout (default ../../cluster-api-provider-terraform
              from this repository, or $CAPTF_PROVIDER)
  --list      print the paths a page must name for KIND, then exit
"""

import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "docs" / "docs" / "reference" / "resources"
DEFAULT_PROVIDER = ROOT.parent.parent / "cluster-api-provider-terraform"

PAGE_OF = {
    "TerraformCluster": "terraformcluster.md",
    "TerraformClusterTemplate": "terraformclustertemplate.md",
    "TerraformMachine": "terraformmachine.md",
    "TerraformMachineTemplate": "terraformmachinetemplate.md",
    "TerraformMachinePool": "terraformmachinepool.md",
    "TerraformMachinePoolTemplate": "terraformmachinepooltemplate.md",
    "TerraformClusterIdentity": "terraformclusteridentity.md",
    "TerraformPlan": "terraformplan.md",
}
COMMON_PAGE = "common-fields.md"

# The workspace fields every Terraform-run kind embeds (api/v1alpha1
# workspace_types.go), and TerraformCluster's defaults.jobs, the same type
# as jobs. Below these, a kind's page need not go: common-fields.md does.
COMMON = [
    "spec.source", "spec.identityRef", "spec.jobs", "spec.variables", "spec.variablesFrom",
    "spec.deletionPolicy", "spec.adoptRetainedState",
    "status.initialization", "status.activeJob", "status.lastRun", "status.lastDriftCheck",
    "status.lastRefresh", "status.pendingRefreshes", "status.source", "status.stateBackups",
]
ALSO_COMMON = ["spec.defaults.jobs"]  # same type as spec.jobs

# Kubernetes' own types, embedded whole: documented by Kubernetes, so a page
# names the field and links there instead of going into its keys.
OPAQUE = {
    "spec.jobs.env", "spec.jobs.resources", "spec.jobs.securityContext",
    "spec.jobs.podSecurityContext", "spec.jobs.imagePullSecrets",
    "spec.allowedNamespaces.selector",
}


def paths(schema: dict, prefix: str) -> list[str]:
    """Every field path under schema, depth first."""
    out = []
    props = schema.get("properties") or {}
    for name, sub in props.items():
        p = f"{prefix}.{name}" if prefix else name
        out.append(p)
        if p in OPAQUE:
            continue
        if sub.get("type") == "array" and isinstance(sub.get("items"), dict):
            item = sub["items"]
            if item.get("properties"):
                out += paths(item, p + "[]")
        elif sub.get("properties"):
            out += paths(sub, p)
    return out


def crds(provider: Path) -> dict[str, list[str]]:
    out = {}
    for f in sorted((provider / "config" / "crd" / "bases").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        kind = d["spec"]["names"]["kind"]
        s = d["spec"]["versions"][0]["schema"]["openAPIV3Schema"]
        out[kind] = [p for p in paths(s, "") if p.split(".")[0] in ("spec", "status")]
    return out


def under(path: str, prefixes: list[str]) -> str | None:
    for c in prefixes:
        if path.startswith(c + ".") or path.startswith(c + "[]"):
            return c
    return None


def required(kind: str, all_paths: list[str]) -> list[str]:
    if kind.endswith("Template") and any(p.startswith("spec.template.spec") for p in all_paths):
        keep = []
        for p in all_paths:
            if p.startswith("spec.template.spec."):
                if "." in p[len("spec.template.spec."):] or "[]" in p[len("spec.template.spec."):]:
                    continue
            keep.append(p)
        return keep
    return [p for p in all_paths if not under(p, COMMON + ALSO_COMMON)]


def common_required(kinds: dict[str, list[str]]) -> list[str]:
    seen = []
    for p in kinds.get("TerraformCluster", []):
        if under(p, COMMON) and p not in seen:
            seen.append(p)
    # Fields only some kinds have under the shared prefixes still belong here.
    for kind, ps in kinds.items():
        if kind.endswith("Template"):
            continue
        for p in ps:
            if under(p, COMMON) and p not in seen:
                seen.append(p)
    return seen


def mentioned(text: str) -> set[str]:
    return set(re.findall(r"`([a-zA-Z][\w.\[\]]*)`", text))


def main(argv: list[str]) -> int:
    provider = Path(os.environ.get("CAPTF_PROVIDER", DEFAULT_PROVIDER))
    if "--provider" in argv:
        provider = Path(argv[argv.index("--provider") + 1])
    kinds = crds(provider)
    if not kinds:
        print(f"no CRDs under {provider}/config/crd/bases")
        return 2
    if "--list" in argv:
        kind = argv[argv.index("--list") + 1]
        req = common_required(kinds) if kind == "common" else required(kind, kinds[kind])
        print("\n".join(req))
        return 0
    missing_total = 0
    checks = [(PAGE_OF[k], required(k, ps)) for k, ps in kinds.items() if k in PAGE_OF]
    checks.append((COMMON_PAGE, common_required(kinds)))
    for page, req in checks:
        f = PAGES / page
        if not f.exists():
            print(f"{page}: missing page ({len(req)} fields to document)")
            missing_total += len(req)
            continue
        have = mentioned(f.read_text())
        missing = [p for p in req if p not in have]
        if missing:
            print(f"{page}: {len(missing)} of {len(req)} fields not named")
            for p in missing:
                print(f"    {p}")
        missing_total += len(missing)
    print("all fields documented" if not missing_total else f"\n{missing_total} field(s) not documented", file=sys.stderr)
    return 1 if missing_total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
