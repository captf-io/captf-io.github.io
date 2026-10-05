---
description: "The CAPTF OpenTofu and Terraform base images: what they provide, how a module image builds FROM one, tags, digest pinning, updates and platforms."
authors:
  - "The CAPTF Authors"
icon: lucide/layers
subtitle: "Images every module builds FROM"
---

# Base Images

CAPTF publishes one base image per runtime: `ghcr.io/captf-io/opentofu-base`
and `ghcr.io/captf-io/terraform-base`. Each lays out the runtime half of the
[image contract](image-contract.md) (the `/captf/runtime` binary, a non-root
user, the contract labels) so that a module image adds only its module. Every
reference module image builds FROM one of them.

Using a base image is recommended, not required: the contract is about the
paths and labels in the final image, not how you produce it. See [Without a
base image](#without-a-base-image) for what you then provide yourself.

## The images

| Image | Runtime | Sources |
| --- | --- | --- |
| `ghcr.io/captf-io/opentofu-base` | OpenTofu (`tofu`), `io.captf.runtime=tofu` | [`opentofu-base`](https://github.com/captf-io/opentofu-base) |
| `ghcr.io/captf-io/terraform-base` | Terraform (`terraform`), `io.captf.runtime=terraform` | [`terraform-base`](https://github.com/captf-io/terraform-base) |

The two are near-identical; only the runtime binary and its label differ.
The runtime versions the bases currently carry are listed in
[Compatibility](../operator-guide/compatibility.md).

## What the base provides

| Path or setting | Provided by the base |
| --- | --- |
| `/captf/runtime` | Symlink to the runtime binary in `/usr/local/bin` (`tofu` or `terraform`). Both binaries are statically linked and copied from the upstream images. |
| `USER` | `captf`, `65532:65532`, shell `/usr/sbin/nologin`, home `/tmp`. Satisfies the Pod Security `restricted` profile. |
| OS | Ubuntu 26.04 LTS. |
| Packages | `ca-certificates` (CA roots for registry and provider downloads), `git` and `openssh-client` (modules and providers fetched over git), and the Ubuntu shell for `local-exec` provisioners. |
| Entrypoint | `/captf/runtime`, with working directory `/captf`. The runner replaces the entrypoint in a Job; this one is for running the image by hand. |
| `io.captf.contract` | `v1alpha1` |
| `io.captf.runtime` | `tofu` or `terraform` |
| `io.captf.runtime.version` | The runtime version, for example `1.12.6`. |

The three `io.captf.*` labels are inherited unchanged by module images. The
base also sets the `org.opencontainers.image.source`, `.revision` and
`.version` labels; a module image overrides them.

The base leaves these absent:

- `/captf/module`, `/captf/providers` and the `io.captf.role` label: the
  module image adds them.
- The reserved paths `/captf/work`, `/captf/bin`, `/captf/config` and
  `/var/run/captf/credentials`: the Job mounts them. See [Fixed
  paths](image-contract.md#fixed-paths).

## What your module image adds

- The module at `/captf/module` and, optionally, the provider mirror at
  `/captf/providers`, both owned by `65532:65532`.
- The `io.captf.role` label.
- The `org.opencontainers.image.source`, `.revision` and `.version` labels,
  with `.version` equal to the tag.
- On machine images, optionally, the `io.captf.capacity` and
  `io.captf.node-info` labels.

Label values and rules are in [OCI labels](image-contract.md#oci-labels).

## Building a module image

The reference Containerfiles are two-stage builds, one per runtime. Each
takes `ARG ROLE`, and `ARG BASE` selects the base tag.

=== "OpenTofu"

    ```dockerfile title="Containerfile.opentofu"
    --8<-- "module-author/examples/Containerfile.opentofu"
    ```

=== "Terraform"

    ```dockerfile title="Containerfile.terraform"
    --8<-- "module-author/examples/Containerfile.terraform"
    ```

The same files are available as
[`examples/Containerfile.opentofu`](examples/Containerfile.opentofu) and
[`examples/Containerfile.terraform`](examples/Containerfile.terraform).

The `mirror` stage runs `get` and `providers mirror` for `linux/amd64` and
`linux/arm64` into `/captf/providers`. It switches to `USER root` because the
base's `captf` user cannot create `/captf/providers`. That stage is not
shipped. The final stage starts again from the base, so the image keeps the
non-root `USER` and copies in only the mirror and the module, owned by
`65532`.

!!! note "Mirroring providers needs registry egress at build time"

    Drop the `mirror` stage (and its `COPY --from=mirror`) for a
    non-hermetic image whose `init` downloads providers at run time.

Add a `.dockerignore` next to the Containerfile with at least `.terraform/`,
`*.tfstate*` and the Containerfile itself, so a local `init` directory,
state or the build file never lands in `/captf/module`. Podman reads
`.dockerignore` as well.

Lint the module, build, then lint the image
([tfcapi-lint](tfcapi-lint.md)):

```sh
tfcapi-lint module . --role cluster --strict
podman build -f Containerfile.opentofu --build-arg ROLE=cluster \
  --build-arg IMAGE_SOURCE=https://github.com/<org>/<repo> \
  --build-arg IMAGE_REVISION="$(git rev-parse HEAD)" \
  --build-arg IMAGE_VERSION=<tag> -t <registry>/<repo>:<tag> .
tfcapi-lint image <registry>/<repo>:<tag> --role cluster --strict
```

## One Dockerfile for every role

A repository that ships several images can use one Dockerfile with the stages
`mirror`, `module`, then one final stage per role named `cluster`, `machine`
and `machinepool`. `--build-arg IMAGE=<image>` picks the module files, and
`--build-arg ROLE=<role>` with a `--target` of the same role picks the final
stage. The [`module-images`
Dockerfile](https://github.com/captf-io/module-images/blob/main/Dockerfile.opentofu)
is the reference: its `mirror` stage copies the module and the image's lock
file, and its final stages are:

```dockerfile
FROM module AS cluster

FROM module AS machinepool

FROM module AS machine
```

The machine capacity labels, `io.captf.capacity` and `io.captf.node-info`,
are not in the Dockerfile. They describe a machine module's default instance
shape, so they belong to the image, not the role: `images.json` holds them,
and `make build` and the publish job add them with `--label`. The
architecture is fixed there, never `TARGETARCH`, so every platform of a
multi-arch build gets identical labels. An image without a default shape (the
OpenStack machine image) carries neither label. Build one image with:

```sh
make test IMAGES=aws-machine RUNTIMES=opentofu
```

## Tags and pinning

| Tag | Moves | Meaning |
| --- | --- | --- |
| `<version>`, for example `1.12.6` | yes | The newest build for that runtime release, rebuilt weekly. |
| `<major.minor>`, for example `1.12` | yes | The newest build of the newest patch release of that minor. |
| `<version>-YYYYMMDD` | no | That day's build. |
| `latest` | yes | The newest build. |

Pin the base in a module image by tag and digest, for example
`opentofu-base:1.12.6@sha256:<digest>`: the tag documents the version, and
the digest fixes the content. To look up a digest:

```sh
skopeo inspect --format '{{.Digest}}' docker://ghcr.io/captf-io/opentofu-base:1.12.6
```

Dependabot's `docker` ecosystem bumps a pin of this form. `module-images` uses this stanza for the base pins:

```yaml
version: 2
updates:
  - package-ecosystem: docker
    directory: /
    schedule:
      interval: weekly
    commit-message:
      prefix: deps
```

## Updates and security fixes

The base is rebuilt every Monday at 05:17 UTC, without the build cache and
with `apt-get upgrade`, to pick up Ubuntu security fixes. A digest pin does
not receive those fixes until you bump it to a newer digest and rebuild your
module image, so keep Dependabot (or an equivalent) enabled for the `FROM`
line.

Runtime upgrades come from Dependabot on the `AS runtime` `FROM` line in the
base repository's Dockerfile; the base build fails if the installed binary
does not match the version in that tag. Each push to GHCR carries an SBOM and
provenance attestations (`mode=max`).

To read the labels of a published image:

```sh
skopeo inspect docker://ghcr.io/captf-io/opentofu-base:1.12.6 | jq .Labels
```

## Platforms

The base images are multi-arch (`linux/amd64`, `linux/arm64`). Ubuntu 26.04
targets the baseline x86-64 instruction set, so the image runs on any amd64
node. A custom final stage on a RHEL 10-family image (such as Rocky Linux 10)
requires x86-64-v3, which older amd64 nodes lack.

## Without a base image

A hand-rolled image must provide every [fixed
path](image-contract.md#fixed-paths), a non-root `USER`, and all the labels
in [OCI labels](image-contract.md#oci-labels), including `io.captf.contract`,
`io.captf.runtime` and `io.captf.runtime.version`, which the base would
otherwise supply. `/captf/runtime` must be the `tofu` or `terraform` binary
or a symlink to it.

A `distroless/static:nonroot` final stage works if the module needs no other
tool, because `tofu` is statically linked. It has no `git`, no `ssh` and no
shell, so a module that fetches over git, or runs a `local-exec`
provisioner, fails on it.

!!! related "See also"

    - [Image Contract](image-contract.md)
    - [Module Repository Layout](repository-layout.md)
    - [Testing a Module](testing.md)
    - [Releasing a Module](releasing.md)
    - [tfcapi-lint](tfcapi-lint.md)
    - [Compatibility](../operator-guide/compatibility.md)
