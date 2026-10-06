---
description: "Run tfcapi-lint in CI with the GitHub Action or the container image: workflows, pinning, allowed warnings, private registries and troubleshooting."
authors:
  - "The CAPTF Authors"
icon: lucide/workflow
subtitle: "Lint modules in a pipeline"
---

# tfcapi-lint in CI

The provider repository publishes [`tfcapi-lint`](tfcapi-lint.md) as a
container image, `ghcr.io/captf-io/tfcapi-lint`, and carries a GitHub
Action that runs it, `captf-io/cluster-api-provider-terraform/actions/tfcapi-lint`.
This page shows how to lint a module repository with them: a pull request
workflow, image linting, several modules at once, pinning, private
registries, self-hosted runners, other CI systems, and what to do when the
step fails. For the checks themselves, see [tfcapi-lint](tfcapi-lint.md)
and the [tfcapi-lint CLI](../reference/tfcapi-lint-cli.md).

!!! info "Before you begin"

    - A module repository on GitHub, and the [role](tfcapi-lint.md#roles)
      of each module in it.
    - A Linux runner with the `docker` CLI. GitHub's `ubuntu-*` runners
      have it; for your own runners, see [Self-hosted
      runners](#self-hosted-runners).
    - The commit of the provider release to pin, from its
      [releases page](https://github.com/captf-io/cluster-api-provider-terraform/releases)
      (or `git ls-remote https://github.com/captf-io/cluster-api-provider-terraform refs/tags/vX.Y.Z`).

## Lint a module on every pull request

The action takes the module directory, its role and the linter flags as
inputs, and fails the step with the linter's exit code. A module at the
repository root, checked on pull requests and on `main`:

```yaml title=".github/workflows/lint.yml"
name: lint

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  tfcapi-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<commit> # v7
        with:
          persist-credentials: false
      - uses: captf-io/cluster-api-provider-terraform/actions/tfcapi-lint@<commit> # vX.Y.Z
        with:
          command: module
          target: .
          role: machine
          strict: true
```

- `@<commit> # vX.Y.Z` pins the commit of a provider release, with the
  tag in the comment. The action runs the linter image built from that
  same commit; see [Pin the action](#pin-the-action-and-keep-it-current).
- `target` is a path relative to the workspace (the checkout). Paths
  outside the workspace and `$RUNNER_TEMP` are not visible to the linter.
- Without `strict`, warnings are reported but the step passes. The
  reference modules lint in strict mode.

The step's log is the linter's text report; a failed step shows each
finding with its check ID, file and line. Set `json: true` for the
`--json` report instead. Every input is listed in
[tfcapi-lint: GitHub Actions](tfcapi-lint.md#github-actions).

| Exit code | The step | Meaning |
| --- | --- | --- |
| `0` | passes | No error, and no warning under `strict`. |
| `1` | fails | At least one error, or a warning under `strict`. |
| `2` | fails | The module could not be parsed, or the image could not be pulled. |
| `3` | fails | A usage error: a wrong input, or the action could not pick an image. |
| `125` | fails | `docker run` itself failed, for example because the linter image does not exist. |

## Allow a warning

A warning your module accepts on purpose is downgraded to info with
`allow-warnings`; errors cannot be allowed. List the check IDs separated by
spaces or newlines:

```yaml
- uses: captf-io/cluster-api-provider-terraform/actions/tfcapi-lint@<commit> # vX.Y.Z
  with:
    command: module
    target: .
    role: machinepool
    strict: true
    allow-warnings: pool/autoscaling-ignore-changes
```

Keep the list in one place with its reasons. The reference modules keep
it in the Makefile's `TFCAPI_LINT_ALLOW` and in the README's Exceptions
section; see [Strict mode and allowed
warnings](tfcapi-lint.md#strict-mode-and-allowed-warnings).

## Lint the image before pushing it

The module source passing is not enough: the [image
contract](image-contract.md) also covers the paths, labels and user of the
built image. Build the image, save it as an OCI layout under
`$RUNNER_TEMP`, lint the layout, and push only if it passes:

```yaml
- name: Build
  env:
    IMAGE: ghcr.io/acme/machine:${{ github.sha }}
  run: |
    docker build -t "$IMAGE" .
    mkdir -p "$RUNNER_TEMP/image"
    docker save "$IMAGE" | tar -x -C "$RUNNER_TEMP/image"
- uses: captf-io/cluster-api-provider-terraform/actions/tfcapi-lint@<commit> # vX.Y.Z
  with:
    command: image
    target: oci:${{ runner.temp }}/image
    role: machine
    strict: true
- name: Push
  env:
    IMAGE: ghcr.io/acme/machine:${{ github.sha }}
  run: docker push "$IMAGE"
```

`docker save` writes the layout for the runner's own platform, which
`tfcapi-lint` checks as `linux/amd64` by default; on an arm64 runner, set
`platform: linux/arm64`. To check a multi-platform image that another step
built and pushed, lint the pushed reference instead, with every platform.
Here the push step has the id `push` and a `digest` output, as
`docker/build-push-action` has:

```yaml
- uses: captf-io/cluster-api-provider-terraform/actions/tfcapi-lint@<commit> # vX.Y.Z
  with:
    command: image
    target: ghcr.io/acme/machine@${{ steps.push.outputs.digest }}
    role: machine
    strict: true
    all-platforms: true
```

## Lint several modules

A repository with one module per role lints them as a matrix, one job
per module:

```yaml
jobs:
  tfcapi-lint:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        role: [cluster, machine, machinepool]
    steps:
      - uses: actions/checkout@<commit> # v7
        with:
          persist-credentials: false
      - uses: captf-io/cluster-api-provider-terraform/actions/tfcapi-lint@<commit> # vX.Y.Z
        with:
          command: module
          target: modules/${{ matrix.role }}
          role: ${{ matrix.role }}
          strict: true
```

To save jobs, use one job with one step per module instead: each step
checks the image tag again, but its layers are downloaded only once.

## Pin the action and keep it current

The linter image follows the ref the action is pinned to, so the linter
and the action always come from the same provider commit:

| Pinned to | Image the action runs |
| --- | --- |
| A release tag, `@vX.Y.Z` | `ghcr.io/captf-io/tfcapi-lint:vX.Y.Z` |
| A commit, `@<40-character SHA>` | `ghcr.io/captf-io/tfcapi-lint:sha-<first 7 characters>` |
| `@main` | `ghcr.io/captf-io/tfcapi-lint:edge` |
| Another branch | None: the step fails; set `version` |

Pin the commit of a release, as for every other action: a tag can be
moved, a commit cannot. Every commit on the provider's `main` whose CI passed gets a
`:sha-<7>` image, and a release is tagged on `main`,
so the commit of a release has one. Pin the provider release you deploy:
the linter checks the contract versions its own release supports. Two
inputs override the image:

- `version`: a tag of `ghcr.io/captf-io/tfcapi-lint`, such as `v0.2.0`
  or `edge`.
- `image`: any image, such as one pinned by digest
  (`ghcr.io/captf-io/tfcapi-lint@sha256:…`) or one built by an earlier
  step. It is used as is when it is already on the runner.

Dependabot updates a commit pin and its tag comment together, and so the
linter with it:

```yaml title=".github/dependabot.yml"
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

The images are signed with keyless cosign and carry build provenance and
an SBOM attestation. Verify one with the commands in
[Releasing](../developer-guide/releasing.md#signatures-and-attestations),
using `ghcr.io/captf-io/tfcapi-lint` and
`-R captf-io/cluster-api-provider-terraform`.

## Private registries

`command: image` pulls the image to lint with the runner's docker
credentials: the action mounts the `config.json` of an earlier
`docker login` into the linter's container, read-only. Log in first:

```yaml
- uses: docker/login-action@<commit> # v4
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
- uses: captf-io/cluster-api-provider-terraform/actions/tfcapi-lint@<commit> # vX.Y.Z
  with:
    command: image
    target: ghcr.io/acme/private-machine:v1.0.0
    role: machine
    strict: true
```

The job needs `packages: read` to pull a private GHCR image with
`GITHUB_TOKEN`. A plain-HTTP registry, such as one in a service container
on `localhost`, also needs `insecure: true`; the linter's container shares
the runner's network, so `localhost` means the runner.

!!! warning "Credential helpers do not work inside the linter's container"

    The container has only the `tfcapi-lint` binary, so it cannot run a
    `credsStore` or `credHelpers` program from `config.json`. The action
    warns when the configuration uses one, and the pull is then anonymous.
    `docker/login-action` on GitHub's runners writes the credentials into
    `config.json` itself, which works.

## Self-hosted runners

The action works on any Linux runner where the job's user can run `docker`:

- Docker, or Podman with its Docker-compatible CLI and socket. The
  container runs with `--security-opt label=disable`, so SELinux hosts
  can read the mounted workspace.
- The workspace and `$RUNNER_TEMP` are mounted read-only at their own
  paths, and the container runs as the runner's user and group.
- `--network host`: the linter reaches what the runner reaches.
- A derived tag (`vX.Y.Z`, `sha-<7>`, `edge`) is pulled on every run, so a
  long-lived runner never reuses a stale `:edge`. An `image` input is
  pulled only when missing.

macOS and Windows runners are not supported: use a [release
binary](tfcapi-lint.md#install) there.

## Other CI systems

The image has no shell: its entrypoint is `tfcapi-lint`, and its
arguments are the linter's. It cannot be a job image whose script runs in
a shell, such as a GitLab CI `image:`. Run it with `docker run` from a
job that has docker, mounting the module read-only:

```sh
docker run --rm -v "$PWD:/work:ro" -w /work \
  ghcr.io/captf-io/tfcapi-lint:vX.Y.Z module --role machine --strict .
```

Where docker is not available, download a [release
binary](tfcapi-lint.md#install) of the same version instead. The binary
and the image are built from the same source and print the same report.

## Run the same check locally

To reproduce a CI failure, run the same image tag on your checkout:

```sh
docker run --rm -v "$PWD:/work:ro" -w /work \
  ghcr.io/captf-io/tfcapi-lint:vX.Y.Z module --role machine --strict \
  --allow-warning pool/autoscaling-ignore-changes .
```

Podman works the same way; add `--security-opt label=disable` on an
SELinux host. The [reference module
repositories](../cloud-modules/README.md) run the linter with
`make tfcapi-lint` instead, which builds it from a provider checkout; see
[Testing a Module](testing.md#lint).

## Troubleshooting

| What the step prints | Cause | Fix |
| --- | --- | --- |
| `cannot tell this action's ref from '…' (a local action?); set the version or image input` | The action was used by path (`uses: ./…`), so it has no ref to pick an image from. | Set `version` or `image`. |
| `no tfcapi-lint image is published for action ref '…'` | The action is pinned to a branch other than `main`, or to a short SHA. | Pin a release commit or tag, or set `version`. |
| `docker: Error response from daemon: manifest unknown`, exit `125` | The image tag does not exist: a commit that was never the head of a push to `main`, or one whose publish run failed or has not finished. | Pin a release, or set `version` to a release tag. |
| `read module: open …: no such file or directory`, exit `2` | `target` is outside the workspace and `$RUNNER_TEMP`, or the path is wrong. | Check out or copy the module into the workspace and pass a relative path. |
| `unknown role: "…"`, exit `3` | `role` is not `cluster`, `machine` or `machinepool`. | Fix the input. |
| A credential-helper warning, then exit `2` on a private image | `config.json` uses a credential helper. | See [Private registries](#private-registries). |
| `docker: command not found` | The runner has no docker. | Use a runner with docker, or a [release binary](tfcapi-lint.md#install). |

A finding itself (exit `1`) names its check ID: look it up in [tfcapi-lint
CLI: checks](../reference/tfcapi-lint-cli.md#checks) for what it means and
how to fix it.

!!! related "See also"

    - [tfcapi-lint](tfcapi-lint.md) for installing the linter and every
      action input.
    - [tfcapi-lint CLI](../reference/tfcapi-lint-cli.md) for every flag,
      check and exit code.
    - [Testing a Module](testing.md) for the full set of module checks.
    - [Image Contract](image-contract.md) for what `command: image`
      enforces.
