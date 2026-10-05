---
description: "Cut a CAPTF release: what it consists of, the checklist, and installing the assets from a local repository."
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

!!! warning "Tags never move"

    Nothing is force-pushed: a bad release candidate gets a new `-rc.N`.

!!! info "Before you begin"

    - Write access to push a signed tag and create a GitHub release.
    - Registry push access for `ghcr.io/captf-io/cluster-api-provider-terraform`.
    - `gh` authenticated against this repository, for `make release-github`.
    - `skopeo`, for `make release` to read the pushed image's registry digest.

## Assets

| Asset | Built by |
| --- | --- |
| `infrastructure-components.yaml` | `make manifests-release`: `config/default` with the release image, and `CAPTF_MANAGER_IMAGE` set to the same image. |
| `metadata.yaml` | The repository root file; `hack/check-metadata.sh` enforces an append-only `releaseSeries`. |
| `cluster-template.yaml`, `cluster-template-clusterclass.yaml`, `clusterclass-noop.yaml`, `identity.yaml` | [`templates/`](https://github.com/captf-io/cluster-api-provider-terraform/blob/main/templates/README.md). |
| `tfcapi-lint-<os>-<arch>`, `tfcapi-lint-checksums.txt` | GoReleaser (`.goreleaser.yaml`), run by `make release-assets`, for Linux and macOS on amd64 and arm64 and Windows on amd64; see [tfcapi-lint](../module-author/tfcapi-lint.md). |

GoReleaser only builds the `tfcapi-lint` binaries and checksums: it does not
build the image or publish the release. `make release` builds and pushes the
image, and `make release-github` publishes.

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
5. Build and push the image and build the assets:

    ```sh
    make release VERSION=vX.Y.Z
    ```

    `release-preflight` refuses a dirty tree, an untagged HEAD, a malformed
    version, or a metadata change that is not append-only. `release` then
    builds and pushes the manager image, reads its registry digest with
    `skopeo`, and builds the assets with the image pinned by that digest,
    so the published components never follow a moved tag. The assets land
    in `out/release/`.
6. Smoke-test from a local repository against a real cluster, by hand: see
    [Installing from a local repository](#installing-from-a-local-repository).
    `make e2e-foundation e2e-noop` also runs the opt-in e2e suites on a
    kind cluster, but they build the manager from your tree rather than
    install the release assets, so they do not replace this step; see
    [Testing](testing.md#end-to-end-tests).
7. Publish: `make release-github VERSION=vX.Y.Z` writes
    `out/release/notes.md` from the commits since the previous tag and runs
    `gh release create` with every asset.

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
