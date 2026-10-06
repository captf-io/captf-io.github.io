---
title: "Module Image Contract: Paths and Labels"
description: "The normative image contract: fixed paths, OCI labels, user, multi-arch publishing, and pointers to the base images."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "September 29, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-09-29"
authors:
  - "The CAPTF Authors"
icon: lucide/package
subtitle: "Paths and labels an image needs"
---

# Image Contract

The OCI image is the deliverable a module author ships. This page is the
normative image contract for the `v1alpha1` module contract: the fixed
paths CAPTF's runner looks for, the labels it and `tfcapi-lint` read, the
user the image should run as, and multi-arch publishing. `tfcapi-lint
image` checks an image against this contract. What the module actually
sees when the runner executes it — the generated root, the environment,
the commands run and their order — is on
[Runtime Environment](runtime-environment.md).

One image bundles one role module (`cluster`, `machine` or `machinepool`)
*and* the runtime that runs it (`tofu` or `terraform`). There is no
separate module source and no separate runtime image: the image tag is the
module version, the image is what `spec.source.image` references, and the
image is what gets pinned, moved, rolled out and audited. The controller
runs it as a Job with its own runner binary as the entrypoint; the image
itself never needs a shell.

## Fixed paths

The runner discovers a module by fixed path, not by label or registry
metadata, and fails the Job at start (`error.kind: image-layout`) if a
required path is missing or unusable.

| Path | Required | Contents |
| --- | --- | --- |
| `/captf/module/` | yes | The role module: at least one `.tf`, `.tf.json`, `.tofu` or `.tofu.json` file at its top level, plus any local module it references by a relative `source`. It cannot declare a `terraform { backend … }` or `cloud` block: those are only valid in a root module, and the generated root, not this one, is the root. |
| `/captf/runtime` | yes | The `tofu` or `terraform` binary: a regular file, or a symlink to one inside the image, executable by the image's `USER`. It must support the Terraform 1.x / OpenTofu 1.x CLI surface: `version`, `init`, `validate`, `plan`, `apply`, `destroy`, `force-unlock`, `show`, and `state push`/`state list`. There is no override for this path. |
| `/captf/providers/` | no | An optional provider filesystem mirror (below). Without it, `init` needs registry egress. |
| `/captf/work/`, `/captf/bin/`, `/captf/config/`, `/var/run/captf/credentials/` | must be empty | The Job mounts an `emptyDir`, the runner binary, the per-run Secret and the identity's credential files at these paths respectively. Anything the image ships under them is shadowed (or, for `/captf/work`, never used, since the image's own root filesystem is read-only by default). |
| `/captf/plan-key/`, `/tmp/` | must be empty | The Job also mounts the plan-key Secret at `/captf/plan-key` (plan and apply Jobs only) and an `emptyDir` at `/tmp` (every Job). Content the image ships there is shadowed too. `tfcapi-lint image` does not check these two paths (its `image/reserved-paths` check covers only the four above), so nothing warns you. |

Everything else in the image is the author's business: CA certificates,
`git` for `provider` blocks that shell out, or a helper binary a
`local-exec` provisioner calls. The [CAPTF base
images](#captf-base-images) already supply CA certificates, `git`, `ssh`
and a shell.

### Nested modules

`/captf/module` includes any local module it calls. `tfcapi-lint module`
follows only module calls whose `source` is a local path (`./` or `../`)
inside the module directory, and lints those. A nested module from a
registry, a git URL or an HTTP URL is not linted. It is also not part of
the image: Terraform and OpenTofu fetch it when `init` runs, which needs
network egress from the Job at run time. Vendor nested modules as local
paths under `/captf/module` instead.

### Provider mirror layout

Build `/captf/providers` with `terraform providers mirror <dir>` or `tofu
providers mirror <dir>`, for every platform the image publishes (for
example `-platform=linux_amd64 -platform=linux_arm64`). Both runtimes
accept either layout it can produce: the *packed* layout
(`HOST/NAMESPACE/TYPE/terraform-provider-TYPE_VERSION_TARGET.zip` plus
`.json` index files) or the *unpacked* layout
(`HOST/NAMESPACE/TYPE/VERSION/TARGET/`).

`providers mirror` creates its target directory only when it writes at
least one provider, so a module that requires none needs the mirror stage
to create `/captf/providers` itself (see the reference
Containerfiles on [Base Images](base-images.md#building-a-module-image)) or the later `COPY --from=mirror` fails. It also fails with
"Module not installed" when the module calls local modules that are not
yet installed, so run `terraform get` / `tofu get` first, in the same
stage; that installs modules only, never providers.

Providers are optional: an image without `/captf/providers` still works,
but needs registry egress at `init` and is slower and non-hermetic. The
reference images in this repository ship a mirror. How the runner uses the
mirror at run time is on
[Runtime Environment](runtime-environment.md#provider-mirror-and-cli-configuration).

## OCI labels

Labels are metadata only: the runner never reads them for behavior.
`tfcapi-lint image` checks them for consistency with `--role`/`--contract`.

With the [CAPTF base images](#captf-base-images), the base supplies
`io.captf.contract`, `io.captf.runtime` and `io.captf.runtime.version`, and
a module image inherits them unchanged. The module image sets
`io.captf.role`, the `org.opencontainers.image.*` labels, and on machine
images the capacity labels below. An image that does not build FROM a CAPTF
base must set every label itself.

| Label | Value |
| --- | --- |
| `io.captf.contract` | Contract version, for example `v1alpha1`. |
| `io.captf.role` | `cluster`, `machine` or `machinepool`. |
| `io.captf.runtime` | `tofu` or `terraform`: what `/captf/runtime` is. |
| `io.captf.runtime.version` | For example `1.12.7`. |
| `org.opencontainers.image.source`, `.revision`, `.version` | Standard OCI annotations; `.version` should equal the tag. |

The reference Containerfiles on [Base Images](base-images.md#building-a-module-image) take these three as `IMAGE_SOURCE`,
`IMAGE_REVISION` and `IMAGE_VERSION` build args (empty by default), so a
build pipeline sets them with `--build-arg` from the source repository
URL, the commit, and the tag being built.

**Capacity labels** (machine role only, optional) let
`TerraformMachineTemplate` support Cluster Autoscaler scale-from-zero: the
module fixes the instance type, the image is the place that knows the
node's size. If the module takes the size as a variable (`instance_type`,
`vm_size`, `machine_type`, `shape`, `flavor`, ...), do not set
`io.captf.capacity`: the label cannot follow a changed variable, and
[`tfcapi-lint`](../reference/tfcapi-lint-cli.md) warns with
`image/capacity-size-variable`. Users set
[`spec.capacity`](../reference/resources/terraformmachinetemplate.md#spec) on
the `TerraformMachineTemplate` instead, which overrides the label. Set both
labels identically on every platform of a multi-arch
index; an image without them leaves `status.capacity`/`status.nodeInfo`
unset.

| Label | Value | Maps to |
| --- | --- | --- |
| `io.captf.capacity` | JSON object, resource name to Kubernetes quantity string, for example `{"cpu":"4","memory":"16Gi","nvidia.com/gpu":"1"}`. Each key is a valid Kubernetes resource name; each value parses as a quantity. | `TerraformMachineTemplate.status.capacity` |
| `io.captf.node-info` | JSON object `{"architecture":"amd64","operatingSystem":"linux"}`; `architecture` is one of `amd64`, `arm64`, `s390x`, `ppc64le`; at least one key set. | `TerraformMachineTemplate.status.nodeInfo` |

A module whose instance type varies needs one image per instance type to
use these labels; pool images may carry them, but they are ignored.

Set the labels from build arguments with a fixed architecture value, never
from `TARGETARCH`, so every platform of a multi-arch build gets identical
labels. [One Dockerfile for every
role](base-images.md#one-dockerfile-for-every-role) shows the `machine`
stage and build command.

## User

Any UID works for the runner, but recommend a non-root `USER` (for example
`65532`) so the Job can run under a namespace that enforces the Pod
Security `restricted` profile. Files and directories under `/captf/module`
and, when present, `/captf/providers` must be readable, and directories
traversable, by that UID. Credential files are mounted mode `0440`, so a
non-root image user reads them through the pod's `fsGroup`, not through
ownership. See [Security Model](../concepts/security-model.md#pod-security)
for how the pod's own security context defaults interact with the image's
`USER`.

## Multi-arch

Publish a multi-arch manifest (`linux/amd64`, `linux/arm64`) or pin the
management cluster's node architecture to the platform the image ships:
`tfcapi-lint image` checks the `linux/amd64` platform by default, and
`--platform`/`--all-platforms` select others. A provider mirror must carry
a package for the target platform it is checked against.

The CAPTF base images are multi-arch; see
[Platforms](base-images.md#platforms) for the x86-64 baseline.

## Versioning and pinning

The image tag is the module version: `spec.source.image` is
`registry/repo:tag` or `registry/repo@sha256:…`, and a new module version
is a new tag referenced by a new `Terraform*Template`. The controller pins
the digest it actually ran after the first successful apply and, for
immutable machines, uses that digest for every later drift and destroy
Job; see [Security Model](../concepts/security-model.md#image-pinning-by-digest)
for the full mechanics and why it matters. [Releasing a
Module](releasing.md) describes the tags the reference repositories publish.

Contract version is not declared in the image: labels are informational.
The controller injects the contract it generates against as
`captf_contract`, and `tfcapi-lint` takes `--contract` on the command
line.

## Trust boundary

Referencing an image is equivalent to granting its publisher the runner's
Secret access and the resolved identity's cloud credentials in that
namespace: see [Security Model](../concepts/security-model.md) for the
full trust boundary and what it means for review and tenancy.

## Building an image

Lint the module first, then build, then lint the pushed image:

```sh
tfcapi-lint module ./cluster --role cluster --strict
podman build -t "$IMAGE" .
tfcapi-lint image "$IMAGE" --role cluster --strict
```

Keep a `.dockerignore` next to the Containerfile so a local `.terraform/`
directory, state or the build file never lands in `/captf/module`. The
reference Containerfiles for Terraform and OpenTofu, and the build
commands, are on [Base Images](base-images.md#building-a-module-image).

### CAPTF base images

CAPTF publishes `ghcr.io/captf-io/opentofu-base` and
`ghcr.io/captf-io/terraform-base`. They supply the runtime half of this
contract (`/captf/runtime`, the non-root user and the `io.captf.contract`
and `io.captf.runtime*` labels), and every reference module image builds
FROM one. Using one is recommended, not required: an image built another
way must provide every fixed path, a non-root `USER` and all the labels
above. See [Base Images](base-images.md) for what they provide, stage
layout, tags, digest pinning and [building without
one](base-images.md#without-a-base-image).

## Checklist for `tfcapi-lint image`

Summarized: `/captf/module` present and lints clean for the role;
`/captf/runtime` present and executable; `/captf/providers`, if present,
follows the mirror layout and covers every `required_providers` entry for
the platform being checked; labels, if present, agree with
`--role`/`--contract`; the capacity labels, if present, are valid JSON of
the shapes above; no files under the reserved paths; `config.User` is
non-root (running as root is a warning, not an error). See
[tfcapi-lint CLI: checks](../reference/tfcapi-lint-cli.md#checks) for
every check's ID, severity and the roles it applies to.

!!! related "See also"

    - [Runtime Environment](runtime-environment.md)
    - [Module Contract](contract/README.md)
    - [tfcapi-lint](tfcapi-lint.md)
    - [Security Model](../concepts/security-model.md)
