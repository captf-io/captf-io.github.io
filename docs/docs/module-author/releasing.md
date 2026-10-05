---
description: "How CAPTF module images are tagged and published, how a module version reaches the Terraform Registry, and which image reference to put in spec.source.image."
authors:
  - "The CAPTF Authors"
icon: lucide/tag
subtitle: "Tags, images and publishing"
---

# Releasing a Module

A CAPTF module is shipped as an OCI image, so releasing a module means
building that image, tagging it and pushing it to a registry. The module code
is also published as a Terraform module, on the Terraform Registry. This page
describes both. The images are built, tagged and published from the image
repositories ([`aws-modules`](https://github.com/captf-io/aws-modules) and the other
`<cloud>-modules`, plus [`noop-modules`](https://github.com/captf-io/noop-modules)); the
registry module is published from the one-module-per-repository
`terraform-<provider>-<role>` repositories (see [Module Repository
Layout](repository-layout.md)), by pushing a tag. A repository of your own can
follow the same schemes.

The [image contract](image-contract.md) decides what is inside the image.
This page covers only how it is named, versioned and published.

## Image names

Each image repository publishes one image per role per runtime. The name is
`<registry>/<set>-<role>`, where `<set>` is the repository's prefix (`aws`,
`azure`, `gcp`, `oci`, `openstack` or `noop`) and `<role>` is `cluster`,
`machine` or `machinepool`. The runtime is part of the tag, not the name:

| Image | Role |
| --- | --- |
| `ghcr.io/captf-io/aws-cluster` | `cluster` |
| `ghcr.io/captf-io/aws-machine` | `machine` |
| `ghcr.io/captf-io/aws-machinepool` | `machinepool` |

A role with no module is not published. For the full list of sets and
images, see [Cloud Modules](../cloud-modules/README.md#images-and-tags).

## Tags

Every image is published once for each runtime (`terraform` and `opentofu`)
under three tags:

| Tag | Pushed when | Moves |
| --- | --- | --- |
| `vX.Y.Z-<runtime>` | A `vX.Y.Z` Git tag is pushed. | No. It is the immutable release. |
| `<runtime>` | The same tag push. | Yes. It points at the newest release. |
| `edge-<runtime>` | Every push to `main`. | Yes. It points at the newest build of `main`. |

The workflow publishes on any Git tag matching `v*.*.*`, and any such tag,
including a pre-release such as `v1.2.3-rc.1`, also moves `<runtime>`. Push
only final `vX.Y.Z` tags, from `main`.

The workflow derives these tags with `docker/metadata-action`, with
`latest` turned off, so there is no `latest` tag:

```yaml title=".github/workflows/build.yml (publish job, trimmed)"
tags: |
  type=edge,branch=main,suffix=-${{ matrix.runtime }}
  type=ref,event=tag,suffix=-${{ matrix.runtime }}
  type=raw,value=${{ matrix.runtime }},enable=${{ startsWith(github.ref, 'refs/tags/v') }}
```

Pull requests build and test but never publish. The `publish` job runs only
on a `push` event.

## Cutting a release

The release steps in the reference repositories are:

1. Run the gate on `main` of the image repository: `make verify`, then
   `make test`. `make verify`
   runs the static checks (format, conventions, `validate` on both runtimes
   and their floors, unit tests, tflint, `tfcapi-lint`, trivy) and
   `make test` builds every image and smoke-tests it. When the repository is
   a sibling of the provider checkout, pass
   `PROVIDER_DIR=../cluster-api-provider-terraform` so `tfcapi-lint` runs
   instead of printing `SKIP`. The checks are described in
   [Testing a Module](testing.md).
2. Tag the commit on `main` `vX.Y.Z` and push the tag:

    ```sh
    git tag vX.Y.Z
    git push origin vX.Y.Z
    ```

3. CI takes over. The workflow triggers on `push` to `main` and on tags
   matching `v*.*.*`. It reruns the license-header check and `make verify`
   (not in `noop-modules`) on `ubuntu-24.04`, and `make test` on
   `ubuntu-24.04` and `ubuntu-24.04-arm` for both runtimes; only if those
   pass does the `publish` job push the images. It publishes
   `vX.Y.Z-<runtime>` and moves `<runtime>` to it, for every role. In the
   cloud repositories, `make verify` and `make test` check out the
   provider's `main` and run `tfcapi-lint` against it; `noop-modules` does
   not. Run it locally, as in step 1, before you tag, so a contract
   violation does not first surface on the tag's CI run.

The repositories do not state a semantic-versioning policy, so this page
does not define one. A provider upgrade is its own commit: bump the pin,
`make lock`, `make verify`.

The tag also sets the image's `org.opencontainers.image.version` label. The
workflow passes the metadata action's primary tag as the `IMAGE_VERSION`
build argument (on a release, `vX.Y.Z-<runtime>`; on `main`,
`edge-<runtime>`), and the Dockerfile writes it into the label together with
`org.opencontainers.image.source` (the repository URL) and
`org.opencontainers.image.revision` (the commit SHA). The `io.captf.role`
label comes from the `ROLE` build argument. See [OCI
labels](image-contract.md#oci-labels) for what the contract requires.

To build a tagged image locally, `make build` uses `VERSION` (default
`dev`) as the tag:

```sh
make build VERSION=v0.1.0 RUNTIMES=opentofu ROLES=machine
```

This builds `ghcr.io/captf-io/aws-machine:v0.1.0-opentofu` for the host
platform.

## Terraform Registry

Each `terraform-<provider>-<role>` module is also published on the Terraform
Registry as `captf-io/<role>/<provider>`, for example `captf-io/cluster/aws`
from [`terraform-aws-cluster`](https://github.com/captf-io/terraform-aws-cluster). The providers are
`aws`, `azure`, `google`, `oci`, `openstack` and `noop`. A release is a signed
`vX.Y.Z` tag on `main` of the module repository; the registry publishes every
semantic-version tag as a module version within a minute of the push. The
reference modules' versions follow the CAPTF release they were cut with
(`0.1.0` today).

1. Run the gate on `main`: `make verify`, with `PROVIDER_DIR` set as above if
   the provider repository is not a sibling. It is the same gate CI runs on
   the tag.
2. Tag the commit and push the tag:

    ```sh
    git tag -s vX.Y.Z -m "vX.Y.Z"
    git push origin vX.Y.Z
    ```

3. Check that the new version appears on the module's registry page.

A registry release is separate from an image release. The registry module is
source: calling it directly makes it a root module with its own provider
blocks and exact provider pins (see the "Using it" section of the module's
README). The image is what CAPTF runs. Cut both for the same version so the
two stay in step.

To publish your own module on the registry, you need:

- A public GitHub repository named `terraform-<PROVIDER>-<NAME>`.
- A one-sentence repository description.
- The `.tf` files at the repository root, as in the [reference
  layout](repository-layout.md#the-layout).
- A semantic-version tag (`vX.Y.Z`), pushed to GitHub.
- The repository connected to the registry: sign in to the registry with the
  GitHub account that owns it, choose *Publish*, then *Module*, and select
  the repository. The registry then publishes every tag by itself.

Use absolute links in the README: the registry renders it as the module's
page, where relative links break.

## What CI publishes

The image repositories' workflow publishes the images:

| Aspect | Value |
| --- | --- |
| Registry | GHCR, `ghcr.io/<repository owner>/<set>-<role>`, logged in with the workflow's `GITHUB_TOKEN`. |
| Matrix | Three roles by two runtimes, one `publish` job each: six images (five in `openstack-modules`, which has no `machinepool`). |
| Platforms | `linux/amd64` and `linux/arm64`, one multi-arch index per tag, built with QEMU and Buildx. |
| Attestations | An SBOM (`sbom: true`) and provenance at `mode=max`. |
| Labels | `org.opencontainers.image.title`, `.description` and `.licenses` from the workflow, plus `.source`, `.revision` and `.version` and `io.captf.role` from the Dockerfile. The inherited `io.captf.*` labels come from the [base image](base-images.md). |
| Annotations | The title, description and licenses again, on the index and the manifests. |
| Permissions | The `publish` job has `contents: read` and `packages: write`. The workflow default is `contents: read`. |

Image signing is not part of the workflow. In the cloud repositories, the
machine image's `io.captf.capacity` and `io.captf.node-info` labels come
from the Makefile's `MACHINE_CAPACITY` and `MACHINE_ARCH`, which the
workflow reads with `make -s print-<VARIABLE>`, so a CI build matches
`make build`. `noop-modules` has neither variable.

## Which reference to use

Put a release tag and its digest in `spec.source.image`:

```text
ghcr.io/captf-io/aws-machine:v0.1.0-opentofu@sha256:<digest>
```

- Use `vX.Y.Z-<runtime>`, not `<runtime>`. The release tag does not move.
  The `<runtime>` tag changes on the next release, so the same manifest
  resolves to different module code over time.
- Do not use `edge-<runtime>` for anything you keep. It moves on every push
  to `main`, and it can hold code that is not released.
- Add the digest to fix the content. A tag is a mutable pointer in the
  registry; the digest is not. The controller also pins the digest it ran
  after the first successful apply, as
  [Versioning and pinning](image-contract.md#versioning-and-pinning)
  describes, but pinning in the manifest keeps what you review and what
  runs the same.

To find the digest of a tag:

```sh
skopeo inspect --format '{{.Digest}}' docker://ghcr.io/captf-io/aws-machine:v0.1.0-opentofu
```

See [`spec.source.image`](../reference/resources/common-fields.md) for the
field rules.

## Publishing from a fork

To publish images under your own registry and name, the `aws-modules` README
gives this procedure: change `REGISTRY` and `CLOUD` in the Makefile, change the
image names in `.github/workflows/build.yml`, rerun `make lock`, then run
`make verify` and `make test`.

- `REGISTRY` (default `ghcr.io/captf-io`) and `VERSION` (default `dev`) are
  `?=` variables in the Makefile, so they can also be set on the command
  line, for example `make build REGISTRY=ghcr.io/me`. In the cloud
  repositories, `CLOUD` is fixed in the Makefile (`CLOUD := aws`) and is
  edited, not overridden; `noop-modules` has no `CLOUD`.
- The workflow derives the registry owner from `github.repository_owner`,
  so the owner changes by itself in a fork. The `aws-` prefix in the image
  name and in the job name is written in the workflow and must be edited.
- Enable GitHub Actions in the fork and push a `vX.Y.Z` tag. The job logs
  in to GHCR with `GITHUB_TOKEN`, which needs the `packages: write`
  permission the job already requests.
- Keep the base pin current. Each Dockerfile pins the base by tag and
  digest, and Dependabot's `docker` ecosystem (weekly, commit prefix
  `deps`) bumps it. A digest pin gets no OS security fixes until you bump it
  and release again; see [Tags and
  pinning](base-images.md#tags-and-pinning).

The Makefile reads the base image from the `AS mirror` line of the
Dockerfile, so that `FROM` line is the only pin to maintain.

!!! related "See also"

    - [Image Contract](image-contract.md)
    - [Base Images](base-images.md)
    - [Testing a Module](testing.md)
    - [Module Repository Layout](repository-layout.md)
    - [Cloud Modules](../cloud-modules/README.md)
