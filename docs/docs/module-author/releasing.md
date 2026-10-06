---
description: "How CAPTF module images are tagged and published, how a module version reaches the Terraform Registry, and which image reference to put in spec.source.image."
authors:
  - "The CAPTF Authors"
icon: lucide/tag
subtitle: "Tags, images and publishing"
---

# Releasing a Module

A CAPTF module is shipped as an OCI image, so releasing a module means
publishing that module and building an image of the release. The module code
is published as a Terraform module, on the Terraform Registry, from the
one-module-per-repository `terraform-<provider>-<role>` repositories (see
[Module Repository Layout](repository-layout.md)), by pushing a tag. The images
are built, tagged and published from one repository,
[`module-images`](https://github.com/captf-io/module-images), which pins a
release of each module. A repository of your own can follow the same schemes.

The [image contract](image-contract.md) decides what is inside the image.
This page covers only how it is named, versioned and published.

## Image names

`module-images` publishes one image per role per runtime. The name is
`<registry>/module-images/<set>-<role>`, where `<set>` is the cloud (`aws`, `azure`, `gcp`,
`oci`, `openstack` or `noop`) and `<role>` is `cluster`, `machine` or
`machinepool`. The runtime is part of the tag, not the name:

| Image | Role |
| --- | --- |
| `ghcr.io/captf-io/module-images/aws-cluster` | `cluster` |
| `ghcr.io/captf-io/module-images/aws-machine` | `machine` |
| `ghcr.io/captf-io/module-images/aws-machinepool` | `machinepool` |

A role with no module is not published.

Images are published under `module-images/` rather than at the top level
of `ghcr.io/captf-io/`. The packages under the old names, such as
`ghcr.io/captf-io/aws-machine`, are owned by the archived `<cloud>-modules`
repositories, and GitHub has no API to grant another repository's workflow
write access to a package. So `module-images` publishes new packages under
its own name, which its workflow creates and owns; adding an image needs no
package settings. The old images stay pullable with their existing tags and
digests, but receive no new builds.

For the full list of sets and
images, see [Cloud Modules](../cloud-modules/README.md#images-and-tags).

## Tags

The image version is the module release. Every image is published once for
each runtime (`terraform` and `opentofu`) under two tags:

| Tag | Meaning | Moves |
| --- | --- | --- |
| `vX.Y.Z-<runtime>` | The image holding module release `vX.Y.Z`. | Only when the image is rebuilt without a module release. |
| `<runtime>` | The image holding the newest module release. | Yes: on every new module release, and on every rebuild. |

The image is rebuilt, and both tags get a new digest, when it changes without
a module release, for example after a base image bump. So a tag is not
immutable: pin a digest for content that must not change. There is no
`latest` tag and no tag for unreleased code; the `edge-<runtime>` tags no
longer exist.

Which module release an image holds is pinned in `sources/versions.tf` of
`module-images`, as a Registry module block:

```hcl title="sources/versions.tf (trimmed)"
module "aws-machine" {
  source  = "captf-io/machine/aws"
  version = "0.1.0"
}
```

The other build values of an image are in `images.json`: its role, the
machine capacity labels and the tfcapi-lint warnings it is allowed. The
provider lock files are `locks/<runtime>/<image>.terraform.lock.hcl`.

Pull requests build and test but never publish. Only a merge to `main`
publishes.

## Cutting a release

A release starts in the module repository and reaches the images through
`module-images`:

1. Run the gate on `main` of the module repository: `make verify`. The checks
   are described in [Testing a Module](testing.md).
2. Tag the commit `vX.Y.Z` and push the tag; the Terraform Registry
   publishes the module version (see [Terraform Registry](#terraform-registry)).
3. Dependabot, daily on the `terraform` ecosystem, opens a pull request in
   `module-images` that bumps the version in `sources/versions.tf`.
4. If the release changes providers, run `make lock IMAGES=<image>` in
   `module-images` and commit the new lock files to the Dependabot branch.
5. CI builds and tests the image on both runtimes. Merge the pull request
   once it is green. The merge to `main` publishes `<image>:vX.Y.Z-<runtime>`
   and moves `<image>:<runtime>` to it.

The build fetches the tagged release from the Registry, only the top-level
`*.tf` files and `templates/`, into the image at `/captf/module`, mirrors the
providers named in the lock files, smoke-tests the image and lints it with
`tfcapi-lint`.

Before you tag, you can build an image from local checkouts of the module
repositories, with the `terraform-*` repositories as siblings of
`module-images`, so a contract violation does not first surface on the pull
request:

```sh
make test IMAGES=aws-machine LOCAL_MODULES=..
```

`make verify` in `module-images` checks that `images.json`, the module
versions and the locks agree, and runs the license-header check, shellcheck
and trivy. `make test` fetches, builds and smoke-tests every image on both
runtimes; narrow it with `CLOUDS=aws`, `RUNTIMES=opentofu` or
`IMAGES=noop-machine`. When `module-images` is a sibling of the provider
checkout (`PROVIDER_DIR` defaults to
`../cluster-api-provider-terraform`), `tfcapi-lint` runs; if it cannot find
the provider, it prints `SKIP`.

The repositories do not state a semantic-versioning policy, so this page
does not define one.

The release also sets the image's `org.opencontainers.image.version` label,
together with `org.opencontainers.image.source` (the repository URL) and
`org.opencontainers.image.revision` (the commit SHA). The `io.captf.role`
label comes from the `role` value of the image in `images.json`. See [OCI
labels](image-contract.md#oci-labels) for what the contract requires.

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

A registry release is the first half of an image release. The registry module
is source: calling it directly makes it a root module with its own provider
blocks and exact provider pins (see the "Using it" section of the module's
README). The image is what CAPTF runs, and `module-images` builds it from the
registry release, so the image version always equals the module version.

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

The `module-images` workflow publishes the images:

| Aspect | Value |
| --- | --- |
| Registry | GHCR, `ghcr.io/<repository owner>/module-images/<set>-<role>`, logged in with the workflow's `GITHUB_TOKEN`. |
| Matrix | Three roles by two runtimes, one `publish` job each: six images for each cloud (five for OpenStack, which has no `machinepool`). |
| Platforms | `linux/amd64` and `linux/arm64`, one multi-arch index per tag, built with QEMU and Buildx. |
| Attestations | An SBOM (`sbom: true`) and provenance at `mode=max`. |
| Labels | `org.opencontainers.image.title`, `.description` and `.licenses` from the workflow, plus `.source`, `.revision` and `.version` and `io.captf.role` from the Dockerfile. The inherited `io.captf.*` labels come from the [base image](base-images.md). |
| Annotations | The title, description and licenses again, on the index and the manifests. |
| Permissions | The `publish` job has `contents: read` and `packages: write`. The workflow default is `contents: read`. |

Image signing is not part of the workflow. The machine image's
`io.captf.capacity` and `io.captf.node-info` labels come from the machine
capacity values in `images.json`, so a CI build matches a local `make test`.
The OpenStack machine image has no default shape, so it sets none.

## Which reference to use

Put a release tag and its digest in `spec.source.image`:

```text
ghcr.io/captf-io/module-images/aws-machine:v0.1.0-opentofu@sha256:<digest>
```

- Use `vX.Y.Z-<runtime>`, not `<runtime>`. The release tag names one module
  release. The `<runtime>` tag changes on the next release, so the same
  manifest resolves to different module code over time.
- Add the digest to fix the content. A tag is a mutable pointer in the
  registry, and even `vX.Y.Z-<runtime>` gets a new digest when the image is
  rebuilt without a module release, for example after a base image bump; the
  digest does not move. The controller also pins the digest it ran
  after the first successful apply, as
  [Versioning and pinning](image-contract.md#versioning-and-pinning)
  describes, but pinning in the manifest keeps what you review and what
  runs the same.

To find the digest of a tag:

```sh
skopeo inspect --format '{{.Digest}}' docker://ghcr.io/captf-io/module-images/aws-machine:v0.1.0-opentofu
```

See [`spec.source.image`](../reference/resources/common-fields.md) for the
field rules.

## Publishing from a fork

To publish images under your own registry and name, fork
[`module-images`](https://github.com/captf-io/module-images), point
`sources/versions.tf` at your own Registry modules (or your own releases of
them), change the registry and image names, rerun `make lock`, then run
`make verify` and `make test`.

- `REGISTRY` (default `ghcr.io/captf-io`) is a `?=` variable in the Makefile,
  so it can also be set on the command line, for example
  `make test REGISTRY=ghcr.io/me`.
- The workflow derives the registry owner from `github.repository_owner`,
  so the owner changes by itself in a fork. The image names are written in
  the workflow and `images.json` and must be edited.
- Enable GitHub Actions in the fork and merge to `main`. The job logs
  in to GHCR with `GITHUB_TOKEN`, which needs the `packages: write`
  permission the job already requests.
- Keep the base pin current. Each Dockerfile pins the base by tag and
  digest, and Dependabot's `docker` ecosystem bumps it. A digest pin gets no
  OS security fixes until you bump it and release again; see [Tags and
  pinning](base-images.md#tags-and-pinning).

The Makefile reads the base image from the `AS mirror` line of the
Dockerfile, so that `FROM` line is the only pin to maintain.

!!! related "See also"

    - [Image Contract](image-contract.md)
    - [Base Images](base-images.md)
    - [Testing a Module](testing.md)
    - [Module Repository Layout](repository-layout.md)
    - [Cloud Modules](../cloud-modules/README.md)
