#!/usr/bin/env python3
"""Check that the reference pages name everything the provider defines.

The reference pages under docs/docs/reference/ (conditions, events, alerts,
metrics, manager flags, Job environment, the runner and tfcapi-lint command
lines, annotations and labels, clusterctl variables, make targets) are
written by hand. This reads the names each one must cover straight from the
provider repository's source, and reports every name its page does not
mention anywhere:

  conditions.md            condition types and reasons (api/v1alpha1/conditions_consts.go)
  events.md                manager and runner event reasons (Event* constants)
  alerts.md                alert names (config/prometheus/rules.yaml)
  metrics.md               metric names (captf_* in internal/metrics)
  manager-flags.md         the manager's own flags (cmd/manager)
  environment.md           the Job's environment variables (internal/jobs)
  runner-cli.md            the runner's flags (cmd/runner)
  tfcapi-lint-cli.md       check IDs (internal/lint) and flags (cmd/tfcapi-lint)
  annotations-labels.md    captf.io/ keys and finalizers (api/, internal/)
  clusterctl-variables.md  ${VARIABLES} in templates/*.yaml
  make-targets.md          Makefile targets with a ## help comment

Test files are skipped. Flags registered by libraries (logging, feature
gates, controller-runtime) are not in the provider's source, so they are
not checked; neither is any wording, default or meaning.

Usage: check_reference.py [--provider PATH] [--list PAGE] [PAGE...]
  --provider  the provider checkout (default ../../cluster-api-provider-terraform
              from this repository, or $CAPTF_PROVIDER)
  --list      print the names PAGE must mention, then exit
  PAGE        check only these pages, such as conditions.md
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "docs" / "docs" / "reference"
DEFAULT_PROVIDER = ROOT.parent.parent / "cluster-api-provider-terraform"

GO_CONST = re.compile(r'^\s*(\w+)\s*(?:[\w.]+\s*)?=\s*"([^"]+)"', re.M)
FLAG = re.compile(r'(?:Var|VarP)\(\s*&?[^,()]+(?:\([^)]*\))?,\s*"([a-z][a-z0-9-]*)"')
FLAG_RET = re.compile(r'\.(?:String|Int|Int32|Int64|Bool|Duration|Float64|StringSlice|Uint)P?\(\s*"([a-z][a-z0-9-]*)"')


def go_files(base: Path):
    return [p for p in base.rglob("*.go") if not p.name.endswith("_test.go")] if base.exists() else []


def consts(files, name_re: str, value_re: str = r".+") -> list[str]:
    out = []
    for f in files:
        for name, value in GO_CONST.findall(f.read_text()):
            if re.fullmatch(name_re, name) and re.fullmatch(value_re, value):
                out.append(value)
    return out


def flags(files) -> list[str]:
    out = []
    for f in files:
        text = f.read_text()
        out += ["--" + n for n in FLAG.findall(text) + FLAG_RET.findall(text)]
    return out


def inventory(pr: Path) -> dict[str, list[str]]:
    shared = pr / "internal" / "controllers" / "shared"
    lint = go_files(pr / "internal" / "lint")
    keys = []
    for f in go_files(pr / "api") + go_files(pr / "internal"):
        text = f.read_text()
        keys += re.findall(r'"(captf\.io/[a-z0-9][a-z0-9./-]*)"', text)
        keys += re.findall(r'"([a-z]+\.infrastructure\.cluster\.x-k8s\.io)"', text)
    variables = []
    for f in sorted((pr / "templates").glob("*.yaml")):
        variables += re.findall(r"\$\{([A-Z][A-Z0-9_]*)", f.read_text())
    targets = re.findall(r"^([a-zA-Z0-9][a-zA-Z0-9_-]*):[^=\n]*##", (pr / "Makefile").read_text(), re.M)
    alerts = re.findall(r"^\s*-\s*alert:\s*(\S+)", (pr / "config" / "prometheus" / "rules.yaml").read_text(), re.M) \
        if (pr / "config" / "prometheus" / "rules.yaml").exists() else []
    return {
        "conditions.md": consts([pr / "api" / "v1alpha1" / "conditions_consts.go"], r"\w+(?:Condition|Reason)", r"[A-Z][A-Za-z]+"),
        "events.md": consts(go_files(shared) + go_files(pr / "internal" / "runner"), r"Event[A-Z]\w*", r"[A-Z][A-Za-z]+"),
        "alerts.md": alerts,
        "metrics.md": consts(go_files(pr / "internal" / "metrics"), r"\w+", r"captf_[a-z0-9_]+"),
        "manager-flags.md": flags(go_files(pr / "cmd" / "manager")),
        "environment.md": [n for f in go_files(pr / "internal" / "jobs")
                           for n in re.findall(r'Name:\s*"([A-Z][A-Z0-9_]*)"', f.read_text())],
        "runner-cli.md": flags(go_files(pr / "cmd" / "runner")),
        "tfcapi-lint-cli.md": consts(lint, r"ID\w*", r"[a-z]+/[a-z0-9-]+") + flags(go_files(pr / "cmd" / "tfcapi-lint")),
        "annotations-labels.md": keys,
        "clusterctl-variables.md": variables,
        "make-targets.md": targets,
    }


def unique(names: list[str]) -> list[str]:
    seen = []
    for n in names:
        if n and n not in seen:
            seen.append(n)
    return seen


def main(argv: list[str]) -> int:
    provider = Path(os.environ.get("CAPTF_PROVIDER", DEFAULT_PROVIDER))
    if "--provider" in argv:
        provider = Path(argv[argv.index("--provider") + 1])
    if not (provider / "Makefile").exists():
        sys.exit(f"no provider checkout at {provider}")
    inv = {page: unique(names) for page, names in inventory(provider).items()}
    if "--list" in argv:
        print("\n".join(inv[argv[argv.index("--list") + 1]]))
        return 0
    selected = [a for a in argv if a.endswith(".md")] or list(inv)
    missing_total = 0
    for page in selected:
        want = inv[page]
        ours = PAGES / page
        if not ours.exists():
            print(f"{page}: missing page ({len(want)} names to document)")
            missing_total += len(want)
            continue
        text = ours.read_text()
        missing = [n for n in want if not re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", text)]
        if missing:
            print(f"{page}: {len(missing)} of {len(want)} names not mentioned")
            for n in missing:
                print(f"    {n}")
        missing_total += len(missing)
    print("every name documented" if not missing_total else f"\n{missing_total} name(s) not documented", file=sys.stderr)
    return 1 if missing_total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
