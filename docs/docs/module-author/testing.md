---
description: "Test a CAPTF module and its image from fastest to slowest: format and validate, mocked unit tests, lint, image smoke test, and end-to-end on kind."
authors:
  - "The CAPTF Authors"
icon: lucide/flask-conical
subtitle: "From unit tests to end to end"
---

# Testing a Module

A module is tested in layers, from checks that finish in seconds on a laptop
to a full run on a Kubernetes cluster. Run the cheap layers on every change
and the expensive ones before a release. This page describes the layers the
reference repositories use, with `aws-modules` as the example, and what each
one catches. The same targets exist in the other `<cloud>-modules`
repositories; [`noop-modules`](https://github.com/captf-io/noop-modules) has
only `build` and `test`.

## Overview

| Layer | What it catches | Make target |
| --- | --- | --- |
| [Static checks](#static-checks) | Unformatted code, syntax errors, invalid references, constructs that the oldest supported runtime cannot parse. | `fmt-check`, `validate` |
| [Unit tests](#unit-tests-with-mocked-providers) | Wrong outputs, wrong health, missing validation, wrong resource arguments. No cloud account needed. | `unit-test` |
| [Lint](#lint) | Style and provider-rule violations, and contract violations in the module source. | `tflint`, `tfcapi-lint` |
| [Image tests](#image-tests) | A wrong user or label, a provider missing from the mirror, a module that cannot `init` offline, an image that breaks the contract. | `build`, `test` |
| [End-to-end](#end-to-end) | Behavior of the controllers and the module together on a real cluster. | Provider repository: `e2e-foundation`, `e2e-noop` |

`make verify` runs every layer above the image tests, plus license, layout,
shell and configuration scans. `make test` builds the images and smoke-tests
them. Run `make help` in a repository for the full list. The host needs
`make`, `podman` (or `docker` with `ENGINE=docker`), `jq` and Go; the
Terraform, OpenTofu, tflint and trivy tools run in containers pinned by
digest, so every contributor and CI run the same versions.

Narrow a run with variables, for example `make unit-test ROLES=machine
RUNTIMES=opentofu`.

## Static checks

`make fmt-check` fails on any file that `terraform fmt` or `tofu fmt` would
change; `make fmt` rewrites them. `make validate` runs `init
-backend=false` and `validate` for every role on both runtimes.

`validate` runs each role twice per runtime:

- on the runtime in the module's [base image](base-images.md), the version
  the module ships on;
- on the supported floor: Terraform 1.5.7 and OpenTofu 1.6.3.

The floors exist because a module image can be built `FROM` either runtime,
and a user may validate or reuse the module on an older release than the
newest one you test with. Every role declares `required_version = ">= 1.5.0"`;
the floor run proves that claim by failing on syntax or functions that the
old runtimes do not have. See [Supporting Terraform and
OpenTofu](repository-layout.md#supporting-terraform-and-opentofu) for the
version policy.

The reference `Makefile` pins the floors as `TF_FLOOR_terraform` and
`TF_FLOOR_opentofu`. Each `validate` and `test` action runs on a staged copy
of the role with the lock file from `locks/<runtime>/<role>.terraform.lock.hcl`
and `-lockfile=readonly`, so the role directory is never modified.
[`hack/tf-run.sh`](https://github.com/captf-io/aws-modules/blob/main/hack/tf-run.sh)
runs one action for one role in the pinned container; call it directly to
reproduce one cell of `make validate`:

```sh
hack/tf-run.sh validate opentofu base cluster
```

The arguments are the action, the runtime, `base` (or a full image
reference) and the role.

## Unit tests with mocked providers

`terraform test` and `tofu test` run `.tftest.hcl` files. With
`mock_provider`, they plan and apply the module against fake providers, so
the tests need no credentials and finish in seconds. Tests live in
`<role>/tests/`:

```text
cluster/tests/
  cluster.tftest.hcl                  # happy path, every output asserted
  cluster_validation.tftest.hcl       # one expect_failures run per validation
  cluster_endpoint_guard.tftest.hcl
```

`make unit-test` runs them for every role that has a `tests/` directory, on
both runtimes. The `tests/` directory is not copied into the image.

Each file declares a `mock_provider` per provider with defaults for the
computed attributes the module reads, a top-level `variables` block with
every contract input, then `run` blocks. A trimmed example from
[`cluster/tests/cluster_validation.tftest.hcl`](https://github.com/captf-io/aws-modules/blob/main/cluster/tests/cluster_validation.tftest.hcl):

```hcl
mock_provider "aws" {
  mock_data "aws_region" {
    defaults = {
      region = "us-east-1"
    }
  }
  # ...one mock_data or mock_resource for each computed value the module reads
}

variables {
  captf_contract = "v1alpha1"
  captf_cluster  = { name = "demo", namespace = "team-a" }
  # ...every other required input
}

run "valid_baseline" {
  command = plan

  assert {
    condition     = length(aws_lb.api_load_balancer) == 1
    error_message = "the baseline every other run varies must plan."
  }
}

run "invalid_captf_contract" {
  command = plan

  variables {
    captf_contract = "v1alpha2"
  }

  expect_failures = [var.captf_contract]
}
```

### What to assert

- **Contract outputs.** On the happy path, assert every output the role must
  produce (see the [output schemas](contract/README.md)), including
  `provider_id`, addresses and failure domain for a machine.
- **Health.** Assert the `health` output for each state the role can reach.
- **Validation errors.** Use one `expect_failures` run per variable
  validation and per `precondition`, so a removed check fails a test.
- **Stability.** Re-apply the same inputs and assert that ids stay the same,
  to prove that a change updates in place rather than replacing.

The `aws-modules` [conventions](https://github.com/captf-io/aws-modules/blob/main/CONVENTIONS.md)
fix the run names (`happy_path`, `reapply_is_stable`, `invalid_<variable>`
and so on) so reviewers can find them. Your module may use its own names.

### Runtime differences

Mock providers need Terraform 1.7+ or OpenTofu 1.8+, so the unit tests run
only on the runtimes of the base images and not on the floors. The two
floors handle test files differently:

- Terraform 1.5 ignores `*.tftest.hcl` files.
- OpenTofu 1.6 reads them at `init` and fails on `mock_provider`. The
  reference `Makefile` sets `NO_TESTS=1` for that floor, so `tf-run.sh`
  stages the role without `tests/`.

The two runtimes also differ in mock behavior. The reference conventions
require every test to pass on both, and list what to avoid: `override_during`,
`state_key`, `parallel`, mock `source` files, mock defaults for attributes the
configuration sets, instance keys in `override_*` targets and assertions on
generated random values. Mock ids on OpenTofu are fixed per address at plan
time, so a test that proves a replacement by a changed id checks less there.

## Lint

Two linters run on the module source.

**tflint** runs in a pinned container with the configuration in
[`.tflint.hcl`](https://github.com/captf-io/aws-modules/blob/main/.tflint.hcl):
the `terraform` ruleset with `preset = "all"` and the cloud ruleset for the
module's provider (the `aws` ruleset here, with `deep_check = false` so the
run needs no credentials). Rulesets are pinned by version and cached under
`.cache/tflint`. The reference repositories turn off
`terraform_standard_module_structure`, because their one-block-per-file layout
is enforced by `hack/check-layout.sh` instead. Run it with `make tflint`.

**tfcapi-lint** checks the module against the [image
contract](image-contract.md): `make tfcapi-lint` runs `tfcapi-lint module
--role <role> --strict` for each role. Strict mode turns warnings into
failures; a warning a module accepts deliberately goes in the Makefile as
`TFCAPI_LINT_ALLOW_<role> := --allow-warning <id>`, with the reason in a
comment and in the role's README. See [tfcapi-lint](tfcapi-lint.md#lint-a-module)
and [Strict mode and allowed
warnings](tfcapi-lint.md#strict-mode-and-allowed-warnings).

The reference repositories build tfcapi-lint from source instead of
installing a release. `PROVIDER_DIR` (default
`../../cluster-api-provider-terraform`) names a checkout of the provider
repository, and the Makefile runs `go build ./cmd/tfcapi-lint` there into
`.tools/bin/tfcapi-lint`. Set `TFCAPI_LINT` to a ready binary to skip the
build. When neither is available, `make tfcapi-lint` prints `SKIP` and exits
successfully, and the image lint in `make test` is skipped the same way. If
your checkout of the provider is elsewhere, pass it explicitly:

```sh
make verify PROVIDER_DIR=/path/to/cluster-api-provider-terraform
```

!!! warning "A skipped lint is not a pass"

    Check the output for `SKIP tfcapi-lint`. If your clone layout differs
    from the default, the contract lint does not run unless you set
    `PROVIDER_DIR` or `TFCAPI_LINT`.

For a standalone install, see [Install](tfcapi-lint.md#install).

## Image tests

`make build` builds `ghcr.io/captf-io/<cloud>-<role>:<version>-<runtime>` for
every role and runtime on the host platform (`VERSION` defaults to `dev`).
`make test` builds, then runs
[`test/smoke.sh`](https://github.com/captf-io/aws-modules/blob/main/test/smoke.sh)
on every image:

```sh
test/smoke.sh <image> <cluster|machine|machinepool> <terraform|opentofu>
```

The script makes three groups of checks and prints `PASS: <image>` or a
`FAIL:` line.

**Image configuration.**

- The user is `65532:65532`.
- `io.captf.contract` is `v1alpha1`, `io.captf.role` equals the role and
  `io.captf.runtime` equals `terraform` or `tofu` for the runtime.
- A machine image carries `io.captf.capacity` (an object with string `cpu`
  and `memory`) and `io.captf.node-info` (`operatingSystem` `linux`,
  `architecture` `amd64` or `arm64`, and equal to `MACHINE_ARCH` when set).
  Every other role must carry neither. With `MACHINE_LABELS=absent`, for a
  module without a default instance shape, the machine image must carry
  neither either.

**A runner-style run.** The script starts the image the way the CAPTF runner
does in a Job, as described in the [runtime
environment](runtime-environment.md): read-only root file system, no network
(`--network=none`), a `tmpfs` at `/captf/work` that allows exec (like the
Job's `emptyDir`), and the same `HOME`, `TF_DATA_DIR`, `TF_CLI_CONFIG_FILE`,
`TF_IN_AUTOMATION` and `TF_INPUT` variables. Inside, it:

- fails if the reserved paths `/captf/bin` or `/var/run/captf/credentials`
  exist in the image;
- requires an executable `/captf/runtime`, a `/captf/providers` directory and
  `*.tf` files in `/captf/module`;
- fails if `tests`, `README.md`, `.terraform` or `.terraform.lock.hcl` is in
  `/captf/module`;
- writes a CLI configuration that allows providers only from the
  `/captf/providers` filesystem mirror, copies the module to
  `/captf/work/root`, and runs `version`, `init -backend=false` and
  `validate`.

`init` with the network off proves that the mirror holds every provider the
module requires; `validate` proves that the module loads against the provider
schemas. The script does not run `apply`, because a real apply needs cloud
credentials.

**Image lint.** When `TFCAPI_LINT` is set, the script exports the image with
`save --format oci-dir` and runs `tfcapi-lint image --role <role> --strict`
on it, with the role's allowed warnings. `make test` sets it when it
resolves a binary as described in [Lint](#lint). See [Lint an
image](tfcapi-lint.md#lint-an-image).

The `noop-modules` smoke test differs in one way: it has no cloud to avoid,
so it mounts a rendered `main.tf.json` at `/captf/config` and goes on to run
`init`, `apply`, `output` and `destroy` offline.

## End-to-end

An end-to-end test exercises the controllers and a module image together on a
cluster. The provider repository,
[`cluster-api-provider-terraform`](https://github.com/captf-io/cluster-api-provider-terraform),
holds two opt-in suites that run on a kind cluster:

```sh
make e2e-foundation   # build the manager, create the cluster, install CAPTF, check it
make e2e-noop         # the noop data-flow suite, on the cluster foundation green-lit
make e2e-down         # delete the e2e cluster
```

They are opt-in: CI does not run them yet, and they need `podman` or
`docker`. The suites are for the provider's own development, so they test the
published [noop modules](../cloud-modules/noop/README.md). The noop images
are pinned in the provider's test framework and pulled into the kind nodes,
and the make targets take no variable that substitutes your own images. A
module author cannot point these suites at their images; the `CAPTF_E2E_*`
variables control the cluster name, reuse, teardown, the stability window,
worker count, green-light age and a bad-digest negative check, and
`TESTENV_ENGINE` picks the container engine; none selects images. See [End-to-end
tests](../developer-guide/testing.md#end-to-end-tests) for the suites.

To test your images on a cluster, take the manual route:

1. Install CAPTF on a kind cluster, with cert-manager and Cluster API, as in
   the [Quick Start](../getting-started/quick-start.md).
2. Push your images to a registry that the cluster can pull from, or load
   them into the kind nodes. A digest is more reliable than a tag; see the
   side-loading note in the provider's
   [`test/README.md`](https://github.com/captf-io/cluster-api-provider-terraform/blob/main/test/README.md).
3. Apply the Quick Start's cluster and machine objects with your images in
   place of the noop ones, and watch the conditions and the Job logs as the
   Quick Start does.

Credentials for a real cloud come from a `TerraformClusterIdentity`; a module
that creates cloud resources needs an account and costs money, so keep this
layer for pre-release checks.

## In CI

The reference repositories run these layers in
[`.github/workflows/build.yml`](https://github.com/captf-io/aws-modules/blob/main/.github/workflows/build.yml),
on pull requests, pushes to `main` and `v*.*.*` tags. The
`license-headers`, `verify` and `test` jobs call `make` with
`ENGINE=docker`. The `verify` and `test` jobs also check out the provider
repository's `main` into `.cache/provider` and pass
`PROVIDER_DIR=.cache/provider`, so the contract lint runs in CI:

| Job | Runs on | What it runs |
| --- | --- | --- |
| `license-headers` | `ubuntu-24.04` | `make check-headers` |
| `verify` | `ubuntu-24.04` | `make verify`: formatting, layout, shell, validate on both runtimes and floors, unit tests, tflint, `tfcapi-lint` and the trivy scan |
| `test` | `ubuntu-24.04` and `ubuntu-24.04-arm`, for each runtime | `make test RUNTIMES=<runtime>`: build and smoke-test every role natively on amd64 and arm64, including the image lint |
| `publish` | `ubuntu-24.04` | On push only, after the three jobs above pass: builds each role and runtime for `linux/amd64` and `linux/arm64` with QEMU and buildx, and pushes to GHCR with an SBOM and provenance |

The `test` job runs a matrix of two runners and two runtimes, so each image
is smoke-tested on both architectures it ships for. CI lints against the
provider's `main`, so run `make tfcapi-lint` and `make test` locally with
`PROVIDER_DIR` set before you push, to catch contract violations first
(see [Lint](#lint)). See [Releasing a
Module](releasing.md) for publishing and tags, and [tfcapi-lint
in CI](tfcapi-lint.md#in-ci) for running the linter in your own pipeline.

!!! related "See also"

    - [Module Repository Layout](repository-layout.md)
    - [Releasing a Module](releasing.md)
    - [tfcapi-lint](tfcapi-lint.md)
    - [Base Images](base-images.md)
    - [Image Contract](image-contract.md)
    - [Testing (developer guide)](../developer-guide/testing.md)
