---
description: "Cut a CAPTF release by pushing a tag: what CI publishes, signing and verification, the manual fallback, and installing assets from a local repository."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "September 29, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-09-29"
authors:
  - "The CAPTF Authors"
icon: lucide/package-check
subtitle: "Cut a release"
---

# Releasing

This page is for whoever cuts a CAPTF release: what a release consists of,
the checklist, and installing the assets before or instead of publishing
them.

A release is a tag `vX.Y.Z` (or `vX.Y.Z-rc.N`) on a clean `main`, the
manager image `ghcr.io/captf-io/cluster-api-provider-terraform:vX.Y.Z`, and a
GitHub release with the clusterctl assets and the `tfcapi-lint` binaries.
The same image is the runner image. The no-op demo module images are not part
of a CAPTF release: they are built and tagged from
[captf-io/noop-modules](https://github.com/captf-io/noop-modules).

**Pushing the tag is the release.** The
[`publish.yaml`](https://github.com/captf-io/cluster-api-provider-terraform/blob/main/.github/workflows/publish.yaml)
workflow runs on the tag push: it runs `make release-preflight`, pushes the
image as `:vX.Y.Z`, builds the release assets and creates the GitHub release.
A `vX.Y.Z-rc.N` version is marked as a pre-release. `make release` is the
manual fallback for when CI cannot run; see [Manual
fallback](#manual-fallback).

!!! warning "Tags never move"

    Nothing is force-pushed: a bad release candidate gets a new `-rc.N`.
    CI publishes a release tag only from its own push, so a released image
    tag never moves.

!!! warning "Never run both paths for one tag"

    If CI publishes a tag, do not also run `make release` for it, and the
    other way round. Both would push the same image tag and create the same
    GitHub release.

!!! info "Before you begin"

    - Write access to push a signed tag to `captf-io/cluster-api-provider-terraform`.
    - For the manual fallback only: registry push access for
      `ghcr.io/captf-io/cluster-api-provider-terraform`, `gh` authenticated
      against this repository (for `make release-github`) and `skopeo` (for
      `make release` to read the pushed image's registry digest).

## Images from `main`

Every push to `main` publishes the manager image as `:edge` and
`:sha-<7-character commit>`, and running the workflow by hand
(`workflow_dispatch`) republishes `:edge` from `main`. `latest` is never
published. These images are signed and attested like release images.

## Assets

| Asset | Built by |
| --- | --- |
| `infrastructure-components.yaml` | `make manifests-release`: `config/default` with the release image, and `CAPTF_MANAGER_IMAGE` set to the same image. |
| `metadata.yaml` | The repository root file; `hack/check-metadata.sh` enforces an append-only `releaseSeries`. |
| `cluster-template.yaml`, `cluster-template-clusterclass.yaml`, `clusterclass-noop.yaml`, `identity.yaml` | [`templates/`](https://github.com/captf-io/cluster-api-provider-terraform/blob/main/templates/README.md). |
| `tfcapi-lint-<os>-<arch>`, `tfcapi-lint-checksums.txt` | GoReleaser (`.goreleaser.yaml`), run by `make release-assets`, for Linux and macOS on amd64 and arm64 and Windows on amd64; see [tfcapi-lint](../module-author/tfcapi-lint.md). |
| `provenance.intoto.jsonl` | The provenance attestation bundle for the assets above, added by `publish.yaml` for verifiers that cannot reach the attestations API. |

GoReleaser only builds the `tfcapi-lint` binaries and checksums: it does not
build the image or publish the release. The image is built by `publish.yaml`
(or by `make release` in the fallback), and the release is created by
`make release-github`, which `publish.yaml` runs. The manager image is
pinned by digest in `infrastructure-components.yaml`, which is what ties the
components to one specific image build.

## Signatures and attestations

`publish.yaml` signs and attests every image digest it pushes, from `main`
and from tags:

- A keyless cosign signature, using the GitHub OIDC identity of the workflow.
- A SLSA build-provenance attestation.
- An SPDX SBOM attestation.

The attestations are stored in the registry and in GitHub attestations. Every
release asset also gets a provenance attestation. Verify an image with:

```sh
cosign verify ghcr.io/captf-io/cluster-api-provider-terraform:vX.Y.Z \
  --certificate-identity-regexp '^https://github.com/captf-io/cluster-api-provider-terraform/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify oci://ghcr.io/captf-io/cluster-api-provider-terraform:vX.Y.Z \
  -R captf-io/cluster-api-provider-terraform
```

Add `--predicate-type https://spdx.dev/Document/v2.3` to the second command
to verify the SBOM attestation instead. Verify a downloaded release asset
with:

```sh
gh attestation verify infrastructure-components.yaml \
  -R captf-io/cluster-api-provider-terraform
```

Images pushed by the manual fallback are not signed or attested.

## Checklist

1. If this release starts a new minor series, append it to `metadata.yaml`
    `releaseSeries`. Never remove or change an existing series.
2. Update the
    [contract changelog](../module-author/contract/v1alpha1/CHANGELOG.md) for
    anything that changes what a module sees or must implement, and
    [Upgrades](../operator-guide/upgrades.md) for anything an operator needs
    to do when moving to this release. Make sure the documentation's
    reference pages ([Reference pages](documentation.md#reference-pages))
    match the code going into the release: from a
    `captf-io/captf-io.github.io` checkout, `tools/check_resources.py` and
    `tools/check_reference.py`, pointed at this checkout with `--provider`,
    list anything they miss.
3. `make lint test verify` is green, and CI is green on the commit you
    tag; CI also runs `make cover-check`, the per-package coverage gate.
    `verify` includes `verify-local-repository`, which generates the
    provider and the default and clusterclass flavors from a clusterctl
    local repository of the release assets, offline.
4. Tag and push the tag: `git tag -s vX.Y.Z && git push origin vX.Y.Z`.
    The push starts `publish.yaml`. `release-preflight` runs first and
    refuses a malformed version or a metadata change that is not
    append-only; nothing is pushed for the tag if it fails.
5. Watch the `publish` workflow. The `image` job builds and pushes the
    `linux/amd64` and `linux/arm64` image (the Dockerfile cross-compiles, so
    there is no emulation) and signs and attests it. The `release` job then
    builds the assets with the image pinned by the digest just pushed, so
    the published components never follow a moved tag, attests them, and
    creates the GitHub release with notes from the commits since the
    previous tag.
6. Smoke-test from a local repository against a real cluster, by hand: see
    [Installing from a local repository](#installing-from-a-local-repository).
    `make e2e-foundation e2e-noop` also runs the opt-in e2e suites on a
    kind cluster, but they build the manager from your tree rather than
    install the release assets, so they do not replace this step; see
    [Testing](testing.md#end-to-end-tests). Download the release assets to
    do this.
7. Verify the signature and attestations as shown in [Signatures and
    attestations](#signatures-and-attestations).

The first time `publish.yaml` pushes the image, set the visibility of the
`cluster-api-provider-terraform` package in the `captf-io` organization to
public once: a new organization package may default to private.

## Manual fallback

Use this only when CI cannot run, and never for a tag that CI has published
or will publish. Push the tag, then build and push the image and build the
assets:

```sh
make release VERSION=vX.Y.Z
```

`release-preflight` refuses a dirty tree, an untagged HEAD, a malformed
version, or a metadata change that is not append-only. `release` then
runs `docker-build` and `docker-push`, which build the image for the
host platform only and push it, reads its registry digest with
`skopeo`, and builds the assets with the image pinned by that digest.
The assets land in `out/release/`. Then publish with
`make release-github VERSION=vX.Y.Z`, which writes `out/release/notes.md`
from the commits since the previous tag and runs `gh release create` with
every asset.

!!! warning "`make release` publishes a single-architecture, unsigned image"

    `release` does not call `docker-buildx`, so the pushed image has the
    architecture of the machine that ran it, and it is not signed or
    attested. The Makefile also has `make docker-buildx`, which builds a
    multi-arch manifest list for `PLATFORMS` (`linux/amd64,linux/arm64` by
    default) and requires podman. `docker-push` pushes such a list with all
    its images when `CONTAINER_TOOL` is podman. To publish both
    architectures, build and push the list yourself with `IMG` set to the
    release image, for example `make docker-buildx docker-push
    IMG=ghcr.io/captf-io/cluster-api-provider-terraform:vX.Y.Z`, then build
    the assets from its digest with `make release-assets VERSION=vX.Y.Z
    RELEASE_IMG=<repo>@<digest>`. The digest is what
    `make release-image-digest VERSION=vX.Y.Z` prints.

## Installing from a local repository

To try the assets before publishing, or offline, copy `out/release/*` to
`~/local-repository/infrastructure-terraform/vX.Y.Z/`: the directory name
is the provider label `infrastructure-terraform`. Point a `clusterctl`
config's `url` at the local path instead of a release URL (see
[Register the provider](../operator-guide/installation.md#register-the-provider)
for the rest of the config entry):

```yaml title="clusterctl.yaml"
url: file:///home/<you>/local-repository/infrastructure-terraform/vX.Y.Z/infrastructure-components.yaml
```

!!! note "A `file://` URL needs the absolute path"

    `<you>` is your username on this machine; a `file://` URL needs the
    absolute path, so `~` does not work here.

Pin the version at install time:

```sh
clusterctl init --config clusterctl.yaml --infrastructure terraform:vX.Y.Z
```

`hack/verify-local-repository.sh` does the same layout in a temp directory
and runs `clusterctl generate provider` and `generate cluster` (the
default and clusterclass flavors) against it.

!!! related "See also"

    - [Writing Documentation](documentation.md#checks) for the book's own build
      and verification commands.
    - [Contributing](contributing.md) for the general build/lint/test/verify
      loop.
