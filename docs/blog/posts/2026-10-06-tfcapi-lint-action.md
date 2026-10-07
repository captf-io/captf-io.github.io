---
date: 2026-10-06 13:00:00
slug: tfcapi-lint-action
title: Lint your module in CI with one step
description: "tfcapi-lint now ships as a signed container image and a GitHub Action: check a module and its image against the CAPTF contract on every pull request."
authors:
  - maintainers
categories:
  - Modules
---

# Lint your module in CI with one step

A module that breaks the CAPTF contract does not fail where you wrote it.
It fails in a runner Job, on a management cluster, with a `Cluster`
waiting on it: a missing output, a variable name the contract reserves, a
`backend` block the generated root cannot accept. `tfcapi-lint` finds those
mistakes statically, before a Job ever runs, and since v0.1.1 it no longer
needs a provider checkout to do it. It ships as a signed container image
and a GitHub Action, and all 17 reference module repositories now lint
with it on every pull request.

<!-- more -->

## The whole setup

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
      - uses: captf-io/cluster-api-provider-terraform/actions/tfcapi-lint@<commit> # vX.Y.Z (1)
        with:
          command: module
          target: .
          role: machine # (2)!
          strict: true # (3)!
```

1.  Pin a commit, with the release tag in a comment. The action runs the
    linter image built from that same commit, so this one line pins both.
2.  `cluster`, `machine` or `machinepool`: the role decides which inputs
    and outputs the contract requires.
3.  Fail on warnings too. The reference modules all lint this way, and
    allow the few warnings they accept by ID.

`tfcapi-lint` never runs `init`, `plan` or `apply`, needs neither
`terraform` nor `tofu`, and touches no cloud. It parses the module's
`.tf`, `.tf.json`, `.tofu` and `.tofu.json` files and any local nested
modules, so it finishes in seconds.

## What it catches

These are real runs against the fixtures in the provider's test suite,
taken from a fresh build:

=== "A pool without provider_id_list"

    ```text
    $ tfcapi-lint module --role machinepool --strict .
    error output/provider-id-list-shape -:0 output provider_id_list is not declared: a pool reports every non-terminated member
    1 error(s), 0 warning(s), 0 info (read terraform files)
    ```

=== "A reserved variable name"

    ```text
    $ tfcapi-lint module --role machine --strict .
    error input/reserved extra.tf:1 variable captf_extra uses the reserved captf_ prefix but is not a contract input
    1 error(s), 0 warning(s), 0 info (read terraform files)
    ```

=== "A backend block"

    ```text
    $ tfcapi-lint module --role machine --strict .
    error module/backend backend.tf:2 terraform { backend } in the module: the generated root owns the backend, a module must not declare one
    1 error(s), 0 warning(s), 0 info (read terraform files)
    ```

=== "A clean module"

    ```text
    $ tfcapi-lint module --role machinepool --strict .
    0 error(s), 0 warning(s), 0 info (read terraform files)
    ```

Each finding names its check, its file and line, and why it matters. A
few of the checks, and what each one saves you from:

| Check | Severity | Without it |
| --- | --- | --- |
| `input/required`, `output/required` | error | The generated root passes an input the module does not declare, or reads an output that is not there. |
| `output/health` | error | No `health` output, so nothing feeds the `InfrastructureHealthy` condition, `Ready`, or a MachineHealthCheck. |
| `input/reserved` | error | A `captf_` variable that is not a contract input collides with a name the contract owns. |
| `module/backend`, `module/cloud` | error | The generated root owns the backend; CAPTF keeps state in Kubernetes Secrets. |
| `input/user-variable-default` | warning | An object that does not set the variable in `spec.variables` or `variablesFrom` fails to apply. |
| `output/endpoint-never-set` | warning | A cluster with no user-set endpoint waits forever for one. |
| `pool/autoscaling-ignore-changes` | warning | Each apply resets the cloud autoscaler's desired count. |
| `image/reserved-paths` | error | Files under `/captf/work` or `/captf/bin` that the Job's own mounts would hide. |
| `image/user-root` | warning | The Job cannot run under the restricted Pod Security Standard. |

The [CLI reference](../../docs/reference/tfcapi-lint-cli.md#checks) lists
all of them with their fixes.

## Lint the image, not just the source

A module that lints clean can still ship in a broken image: the module in
the wrong place, a provider mirror missing a platform, no role label, or
running as root. The image contract covers all of that, and so does
`command: image`. Build, save the image as an OCI layout, lint the layout,
and push only if it passes:

```yaml hl_lines="8-13"
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

`command: image` also runs every module check on `/captf/module`, so one
step covers both.

## One pin for the action and the linter

The action is a small composite step that runs
`ghcr.io/captf-io/tfcapi-lint` with Docker. It picks the image tag from the
ref you pinned:

| You pin | It runs |
| --- | --- |
| A release tag, `vX.Y.Z` | `ghcr.io/captf-io/tfcapi-lint:vX.Y.Z` |
| A full commit SHA | `:sha-<first 7>`, the image built from that commit |
| `main` | `:edge`, the newest `main` commit whose CI passed |

So when Dependabot bumps the action's commit pin and its tag comment, the
linter moves with it, and nothing else in the workflow changes. The
`version` and `image` inputs override the choice, for example to pin the
image by digest.

??? note "How the action knows its own ref"

    GitHub's `github.action_ref` context is empty inside a composite
    action's `run` steps
    ([actions/runner#2473](https://github.com/actions/runner/issues/2473)).
    The runner does check a remote action out under
    `…/_actions/<owner>/<repo>/<ref>/actions/tfcapi-lint`, so the script
    reads the ref from `GITHUB_ACTION_PATH` instead. A local `uses: ./`
    has no ref to read, and the action then asks for the `version` or
    `image` input.

A few more details from the action, all of which the
[CI guide](../../docs/module-author/tfcapi-lint-ci.md) covers:

- The workspace and the runner's temp directory are mounted read-only, at
  their own paths, so `target` paths mean the same inside and out.
- Inputs reach the script as environment variables, never as expressions
  expanded into the shell.
- Logged in with `docker/login-action`, it can lint private images. Docker
  credential helpers cannot run inside the distroless linter image; the
  action warns and pulls anonymously.
- It needs a Linux runner with Docker. On macOS or Windows, use the
  release binary.

## The same check, locally

The image is a static binary on distroless, for `linux/amd64` and
`linux/arm64`, signed with keyless cosign and carrying build provenance and
an SBOM attestation. Run it on your own machine before you push:

```sh
docker run --rm -v "$PWD:/work:ro" -w /work \
  ghcr.io/captf-io/tfcapi-lint:vX.Y.Z module --role machine --strict \
  --allow-warning pool/autoscaling-ignore-changes .
```

Podman works the same; add `--security-opt label=disable` on an SELinux
host. Release binaries for Linux, macOS and Windows are attached to every
provider release, too.

<div class="grid cards" markdown>

-   :material-github:{ .lg .middle } __tfcapi-lint in CI__

    ---

    Workflows, allowed warnings, several modules, private registries,
    self-hosted runners and troubleshooting.

    [:octicons-arrow-right-24: Read the guide](../../docs/module-author/tfcapi-lint-ci.md)

-   :material-console:{ .lg .middle } __tfcapi-lint CLI__

    ---

    Every command, flag, exit code and check, with severity and fix.

    [:octicons-arrow-right-24: Look it up](../../docs/reference/tfcapi-lint-cli.md)

-   :material-package-variant-closed:{ .lg .middle } __The image contract__

    ---

    The paths, labels and user a module image must have.

    [:octicons-arrow-right-24: Read the contract](../../docs/module-author/image-contract.md)

</div>
