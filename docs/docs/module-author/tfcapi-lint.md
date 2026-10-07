---
title: "Linting Modules with tfcapi-lint"
description: "Install tfcapi-lint, lint a module or image against the CAPTF contracts, use strict mode and exit codes, and run it in CI."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "September 29, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-09-29"
authors:
  - "The CAPTF Authors"
icon: lucide/spell-check
subtitle: "Check a module for contract errors"
---

# tfcapi-lint

`tfcapi-lint` checks a Terraform or OpenTofu module, and the OCI image built
from it, against the CAPTF module contract
([module contract](contract/README.md)) and the
[image contract](image-contract.md), without running `init`, `plan` or
`apply`. It is for module authors, and for CI pipelines that build module
images. It is released alongside the provider, with the same version.

## Install

Every release attaches one binary per platform, plus a checksum file:

| Asset | Platform |
| --- | --- |
| `tfcapi-lint-linux-amd64` | Linux x86-64 |
| `tfcapi-lint-linux-arm64` | Linux ARM64 |
| `tfcapi-lint-darwin-amd64` | macOS Intel |
| `tfcapi-lint-darwin-arm64` | macOS Apple silicon |
| `tfcapi-lint-windows-amd64.exe` | Windows x86-64 |
| `tfcapi-lint-checksums.txt` | SHA-256 of every asset above |

```sh
base="https://github.com/captf-io/cluster-api-provider-terraform/releases/download/<version>"
curl -fsSLO "${base}/tfcapi-lint-<os>-<arch>"
curl -fsSLO "${base}/tfcapi-lint-checksums.txt"
sha256sum --check --ignore-missing tfcapi-lint-checksums.txt
install -m 0755 "tfcapi-lint-<os>-<arch>" /usr/local/bin/tfcapi-lint
tfcapi-lint version
```

- `<version>` is the provider release you deploy, for example `v0.2.0`.
- `<os>` and `<arch>` pick one row of the table above, for example
  `linux` and `amd64`. On macOS, verify the checksum with
  `shasum -a 256 -c --ignore-missing tfcapi-lint-checksums.txt` instead.

Match the `tfcapi-lint` release to the controller you deploy against:
`tfcapi-lint version --json` reports the contract versions it lints
against, `["v1alpha1"]`.

!!! warning "`go install` does not work"

    `go install .../cmd/tfcapi-lint@<version>` fails: the repository is
    a Go workspace, and `cmd/tfcapi-lint` depends on the `api` module, which
    only the workspace resolves. Build from source instead (below), or use a
    release binary.

### Container image

The provider also publishes `tfcapi-lint` as a container image,
`ghcr.io/captf-io/tfcapi-lint`, for `linux/amd64` and `linux/arm64`. It
holds the static binary alone, on distroless, as its entrypoint, and is
signed and attested like the manager image (see
[Releasing](../developer-guide/releasing.md#signatures-and-attestations)).

| Tag | Built from |
| --- | --- |
| `vX.Y.Z` | The provider release `vX.Y.Z`; never moves. |
| `edge` | The newest commit on `main` whose CI passed. |
| `sha-<7>` | That commit on `main`, once its CI passed. |

Mount the module read-only and lint it in place:

```sh
docker run --rm -v "$PWD:/work:ro" -w /work \
  ghcr.io/captf-io/tfcapi-lint:<version> module --role machine --strict .
```

`tfcapi-lint image` inside the container needs the registry credentials
too: mount the directory of your `config.json` and set `DOCKER_CONFIG` to
it (the [GitHub Action](#github-actions) does this for you).

## Roles

Every module implements exactly one role, and `--role` on `module` and
`image` is required and takes one of `cluster`, `machine` or
`machinepool`, matching the [`TerraformCluster`](../concepts/kinds.md),
[`TerraformMachine`](../concepts/kinds.md) and
[`TerraformMachinePool`](../concepts/kinds.md) contracts. `tfcapi-lint`
checks the module or image against that role's inputs, outputs and checks
only; see [tfcapi-lint CLI](../reference/tfcapi-lint-cli.md#checks) for
which checks apply to which roles.

## Lint a module

```sh
tfcapi-lint module --role machine ./machine
```

This reads the `.tf`, `.tf.json`, `.tofu` and `.tofu.json` files under
`./machine` directly; it needs neither `terraform` nor `tofu` installed,
and never contacts a registry. A clean module prints an empty finding
list and an all-zero summary.

## Lint an image

```sh
tfcapi-lint image --role machine registry.example.com/acme/machine:v1.0.0
```

This pulls the image manifest and its layers, and checks the fixed paths
and labels the [image contract](image-contract.md) requires, without
running the image. `<image-ref>` is a registry reference; `oci:<dir>`
reads a local OCI image layout instead, such as one written by
`podman save --format oci-dir` or `skopeo copy ... oci:<dir>`, with no
registry or daemon involved. By default it checks the `linux/amd64`
platform of a multi-platform image; `--platform os/arch` picks a
different one, and `--all-platforms` checks every platform the image
publishes.

### Registry credentials

`tfcapi-lint image` authenticates the same way `docker` and `podman` do,
through go-containerregistry's default keychain: it reads
`~/.docker/config.json`, or `$DOCKER_CONFIG/config.json` when that
variable is set; if neither exists, it falls back to a Podman-style
config at `$REGISTRY_AUTH_FILE` or
`$XDG_RUNTIME_DIR/containers/auth.json`. With none of those present, the
pull is anonymous. Log in with `docker login` or `podman login` against
the registry before linting a private image; `--insecure` allows a
plain-HTTP registry for a local or air-gapped registry that has none.

## Print the variables schema

```sh
tfcapi-lint schema --role machine ./machine
```

Prints the JSON Schema of the module's user variables on one line. Pass it
to the image build as the `io.captf.variables-schema` label, so the manager
rejects unknown, missing or mistyped variables before any Job runs; see
[the image contract](image-contract.md#oci-labels).

## Strict mode and allowed warnings

`--strict` treats a warning the same as an error for the exit code, so a
module or image that is merely clean today does not silently pick up new
warnings later. `--allow-warning <id>` (repeatable, or a comma-separated
list) downgrades one check ID's warnings to informational findings; it
never touches errors. Use it for a deliberate, reviewable exception, for
example a module whose provider cannot tag anything:
`--allow-warning input/tags-unused`. Run with `--strict` by default, and
add `--allow-warning` only for checks you have decided not to act on.

`--json` prints a report with a `findings` array (`id`, `severity`,
`file`, `line`, `message`) and a `summary`, instead of one line of text
per finding. See [tfcapi-lint CLI](../reference/tfcapi-lint-cli.md) for
every flag, and
[tfcapi-lint CLI: checks](../reference/tfcapi-lint-cli.md#checks) for
every check ID, its severity and the roles it applies to.

## What the linter does not see

The linter follows only local nested module calls: a `source` of `.`,
`..`, or a path starting with `./` or `../`. It never fetches a registry,
git, HTTP or other remote module, so it does not lint one. A `backend` or
`cloud` block, or a credential literal in a provider block, inside a remote
module is not reported. A strict run does not change this. Vendor such a
module into the module directory, as a local path, if you want it checked.

## Exit codes

`tfcapi-lint` uses its exit code to signal a CI step's pass or fail; see
[tfcapi-lint CLI: exit codes](../reference/tfcapi-lint-cli.md#exit-codes)
for the full list. In short:

| Code | Meaning |
| --- | --- |
| `0` | Clean. |
| `1` | At least one error (or, under `--strict`, at least one warning). |
| `2` | The module could not be parsed or the image could not be pulled. |
| `3` | A usage error. |

## In CI

Lint the module before building the image, then lint the built image
before pushing it: the source is checked before the build, and the built
layout after it. On GitHub, the [GitHub Action](#github-actions) runs both
steps; [tfcapi-lint in CI](tfcapi-lint-ci.md) has complete workflows. Any
other CI runs the binary:

```sh title="CI step"
tfcapi-lint module --role machine --strict ./module
podman build -t "$IMAGE" .
podman save --format oci-dir -o "$RUNNER_TEMP/image" "$IMAGE"
tfcapi-lint image --role machine --strict "oci:$RUNNER_TEMP/image"
podman push "$IMAGE"
```

To check exactly what was pushed, for example a multi-platform index
built and pushed by a separate step, lint the pushed reference instead of
the local layout:

```sh
tfcapi-lint image --role machine --strict --all-platforms "$IMAGE"
```

### GitHub Actions

The provider repository carries a GitHub Action,
`captf-io/cluster-api-provider-terraform/actions/tfcapi-lint`, that runs
the [container image](#container-image) with `docker`, so it needs a Linux
runner with docker, as GitHub's `ubuntu-*` runners have. Pin it by commit,
like every other action:

```yaml title=".github/workflows/ci.yml"
- uses: captf-io/cluster-api-provider-terraform/actions/tfcapi-lint@<commit> # vX.Y.Z
  with:
    command: module
    target: .
    role: machine
    strict: true
```

The linter follows the action's ref: pinned to the commit of release
`vX.Y.Z` (or to the tag itself), the action runs `tfcapi-lint:vX.Y.Z`; pinned
to another commit on `main`, that commit's `:sha-<7>` image; and on `main`,
`:edge`. A Dependabot update of the pin therefore updates the linter too.
The `version` input picks a tag explicitly, and `image` names any image,
for example one pinned by digest, or one built in an earlier step.

| Input | Default | Meaning |
| --- | --- | --- |
| `command` | (required) | `module` or `image`. |
| `target` | (required) | The module directory, or the image reference or `oci:<dir>`. |
| `role` | (required) | `cluster`, `machine` or `machinepool`. |
| `strict` | `false` | `--strict`: warnings fail the step too. |
| `allow-warnings` | (none) | Check IDs for `--allow-warning`, separated by spaces or newlines. |
| `contract` | (the linter's) | `--contract`. |
| `platform` | `linux/amd64` | `image` only: `--platform`. |
| `all-platforms` | `false` | `image` only: `--all-platforms`. |
| `insecure` | `false` | `image` only: `--insecure`, for a plain-HTTP registry. |
| `json` | `false` | `--json`. |
| `args` | (none) | Extra flags, separated by spaces. |
| `version` | (from the ref) | The image tag: `vX.Y.Z`, `edge` or `sha-<7>`. |
| `image` | (none) | The full image to run; overrides `version`. |

The step fails with the linter's [exit code](#exit-codes). Its `image`
output names the image that ran. Local paths are mounted read-only and
must be inside the workspace or `$RUNNER_TEMP`, which keeps an image
layout saved to `$RUNNER_TEMP` lintable. The action also mounts the
credentials of an earlier `docker/login-action` step, for a private image.

[tfcapi-lint in CI](tfcapi-lint-ci.md) walks through it: a pull request
workflow, [linting the built
image](tfcapi-lint-ci.md#lint-the-image-before-pushing-it), several
modules, Dependabot, private registries, self-hosted runners, other CI
systems and [troubleshooting](tfcapi-lint-ci.md#troubleshooting).

## Building from source

`make release-lint-snapshot` builds all five release assets and the
checksum file into `dist/` with GoReleaser, stamped with a snapshot
version; `make release-lint` does the same from the current git tag.
See [Releasing](../developer-guide/releasing.md) for how these assets
reach a GitHub release.

!!! related "See also"

    - [tfcapi-lint CLI](../reference/tfcapi-lint-cli.md) for every flag, every
      check ID and the exit codes.
    - [tfcapi-lint in CI](tfcapi-lint-ci.md) for the GitHub Action and the
      container image in a pipeline.
    - [Module contract](contract/README.md) and
      [image contract](image-contract.md) for what the checks enforce.
    - [Runtime environment](runtime-environment.md) for what a module sees
      once CAPTF actually runs it.
