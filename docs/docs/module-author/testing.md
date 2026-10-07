---
title: "Testing a Terraform Module for CAPTF"
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
reference repositories use and what each one catches. The code checks live in
the one-module-per-repository `terraform-<provider>-<role>` repositories, with
[`terraform-aws-cluster`](https://github.com/captf-io/terraform-aws-cluster) as the example; the
same targets exist in the other cloud repositories. The image smoke test lives
in [`module-images`](https://github.com/captf-io/module-images), which builds
the images from released modules. The
[`terraform-noop-*`](https://github.com/captf-io/terraform-noop-cluster) repositories run format,
`validate` and an apply and destroy of `test/root`.

## Overview

| Layer | What it catches | Make target |
| --- | --- | --- |
| [Static checks](#static-checks) | Unformatted code, syntax errors, invalid references, constructs that the oldest supported runtime cannot parse. | `fmt-check`, `validate` |
| [Unit tests](#unit-tests-with-mocked-providers) | Wrong outputs, wrong health, missing validation, wrong resource arguments. No cloud account needed. | `unit-test` |
| [Lint](#lint) | Style and provider-rule violations, and contract violations in the module source. | `tflint`, `tfcapi-lint` |
| [Image tests](#image-tests) | A wrong user or label, a provider missing from the mirror, a module that cannot `init` offline, an image that breaks the contract. | `build`, `test` (in `module-images`) |
| [End-to-end](#end-to-end) | Behavior of the controllers and the module together on a real cluster. | Provider repository: `e2e-foundation`, `e2e-noop` |

In a `terraform-*` repository, `make verify` runs every layer above the image
tests, plus license, layout, shell and configuration scans; it is the only
thing CI runs there. In `module-images`, `make test` fetches the modules, builds the
images and smoke-tests them, and `make verify` checks that `images.json`,
`sources/versions.tf` and the locks agree. Run `make help` in a repository for the full
list. The host needs
`make`, `podman` (or `docker` with `ENGINE=docker`), `jq` and Go; the
Terraform, OpenTofu, tflint and trivy tools run in containers pinned by
digest, so every contributor and CI run the same versions.

Narrow a run with variables, for example `make unit-test
RUNTIMES=opentofu`.

## Static checks

`make fmt-check` fails on any file that `terraform fmt` or `tofu fmt` would
change; `make fmt` rewrites them. `make validate` runs `init
-backend=false` and `validate` on both runtimes.

`validate` runs the module twice per runtime:

- on the runtime in the module's [base image](base-images.md), the version
  the module ships on;
- on the supported floor: Terraform 1.5.7 and OpenTofu 1.6.3.

The floors exist because a module image can be built `FROM` either runtime,
and a user may validate or reuse the module on an older release than the
newest one you test with. The module declares `required_version = ">= 1.5.0"`;
the floor run proves that claim by failing on syntax or functions that the
old runtimes do not have. See [Supporting Terraform and
OpenTofu](repository-layout.md#supporting-terraform-and-opentofu) for the
version policy.

The reference `Makefile` pins the floors as `TF_FLOOR_terraform` and
`TF_FLOOR_opentofu`. Each `validate` and `test` action runs on a staged copy
of the module, and resolves the exact provider pins of `versions.tf` afresh,
because no lock file is committed, so the repository itself is never modified.
[`hack/tf-run.sh`](https://github.com/captf-io/terraform-aws-cluster/blob/main/hack/tf-run.sh)
runs one action for the module in the pinned container; call it directly to
reproduce one cell of `make validate`:

```sh
hack/tf-run.sh validate opentofu default
```

The arguments are the action, the runtime, and `default` (the base image the
`Makefile` pins) or a full image reference.

## Unit tests with mocked providers

`terraform test` and `tofu test` run `.tftest.hcl` files. With
`mock_provider`, they plan and apply the module against fake providers, so
the tests need no credentials and finish in seconds. Tests live in
`tests/`, at the repository root:

```text
tests/
  cluster.tftest.hcl                  # happy path, every output asserted
  cluster_validation.tftest.hcl       # one expect_failures run per validation
  cluster_endpoint_guard.tftest.hcl
```

`make unit-test` runs them on both runtimes, and skips when there is no
`tests/*.tftest.hcl`. The `tests/` directory is not copied into the image.

Each file declares a `mock_provider` per provider with defaults for the
computed attributes the module reads, a top-level `variables` block with
every contract input, then `run` blocks. A trimmed example from
[`tests/cluster_validation.tftest.hcl`](https://github.com/captf-io/terraform-aws-cluster/blob/main/tests/cluster_validation.tftest.hcl):

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

The `terraform-aws-cluster` [conventions](https://github.com/captf-io/terraform-aws-cluster/blob/main/CONVENTIONS.md)
fix the run names (`happy_path`, `reapply_is_stable`, `invalid_<variable>`
and so on) so reviewers can find them. Your module may use its own names.

### Runtime differences

Mock providers need Terraform 1.7+ or OpenTofu 1.8+, so the unit tests run
only on the runtimes of the base images and not on the floors. The two
floors handle test files differently:

- Terraform 1.5 ignores `*.tftest.hcl` files.
- OpenTofu 1.6 reads them at `init` and fails on `mock_provider`. The
  reference `Makefile` sets `NO_TESTS=1` for that floor, so `tf-run.sh`
  stages the module without `tests/`.

The two runtimes also differ in mock behavior. The reference conventions
require every test to pass on both, and list what to avoid: `override_during`,
`state_key`, `parallel`, mock `source` files, mock defaults for attributes the
configuration sets, instance keys in `override_*` targets and assertions on
generated random values. Mock ids on OpenTofu are fixed per address at plan
time, so a test that proves a replacement by a changed id checks less there.

## Lint

Two linters run on the module source.

**tflint** runs in a pinned container with the configuration in
[`.tflint.hcl`](https://github.com/captf-io/terraform-aws-cluster/blob/main/.tflint.hcl):
the `terraform` ruleset with `preset = "all"` and the cloud ruleset for the
module's provider (the `aws` ruleset here, with `deep_check = false` so the
run needs no credentials). Rulesets are pinned by version and cached under
`.cache/tflint`. The reference repositories turn off
`terraform_standard_module_structure`, because their one-block-per-file layout
is enforced by `hack/check-layout.sh` instead. Run it with `make tflint`.

**tfcapi-lint** checks the module against the [image
contract](image-contract.md): `make tfcapi-lint` runs `tfcapi-lint module
--role <role> --strict`. Strict mode turns warnings into
failures; a warning a module accepts deliberately goes in the Makefile as
`TFCAPI_LINT_ALLOW := --allow-warning <id>`, with the reason in a
comment and in the README's Exceptions section. See [tfcapi-lint](tfcapi-lint.md#lint-a-module)
and [Strict mode and allowed
warnings](tfcapi-lint.md#strict-mode-and-allowed-warnings).

The reference repositories build tfcapi-lint from source instead of
installing a release. `PROVIDER_DIR` (default
`../cluster-api-provider-terraform`, a sibling checkout) names a checkout of the provider
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

For a standalone install, see [Install](tfcapi-lint.md#install). A
module repository of your own does not need the provider checkout: on
GitHub, the tfcapi-lint GitHub Action runs the linter's container image in
one step; see [tfcapi-lint in CI](tfcapi-lint-ci.md).

## Image tests

The image tests run in `module-images`, which builds the images; the
`terraform-*` repositories have no `build` or `test` target. `make build`
fetches the module release that `sources/versions.tf` pins for each image and
builds `ghcr.io/captf-io/module-images/<image>:<module tag>-<runtime>` for every image and
runtime on the host platform. `make test` builds, then runs
[`test/smoke.sh`](https://github.com/captf-io/module-images/blob/main/test/smoke.sh)
on every image. Narrow a run with `CLOUDS=aws`, `RUNTIMES=opentofu` or
`IMAGES=noop-machine`, and build from local checkouts of the module
repositories, for a change that is not released, with `LOCAL_MODULES=..`:

```sh
make test IMAGES=aws-machine LOCAL_MODULES=..
```

Each image is checked with:

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

The `noop-*` images get one more step: they have no cloud to avoid, so the
script mounts a rendered `main.tf.json` (the image's `smokeRoot` in
`images.json`) at `/captf/config` and goes on to run `init`, `apply`, `output`
and `destroy` offline.

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

A `terraform-*` repository runs one job, `verify`, in
[`.github/workflows/ci.yml`](https://github.com/captf-io/terraform-aws-cluster/blob/main/.github/workflows/ci.yml),
on pull requests, pushes to `main` and `v*.*.*` tags, on `ubuntu-24.04`.
It first lints the module with the provider's [tfcapi-lint GitHub
Action](tfcapi-lint-ci.md), pinned to a provider release, with the role and
the allowed warnings read from the Makefile (`make print-ROLE`,
`make print-TFCAPI_LINT_ALLOW`). Then it calls `make verify ENGINE=docker`,
even when the lint failed. `make verify` covers license headers, format,
layout, shell, `validate` and `unit-test` on both runtimes and the floors,
tflint and the trivy scan, with the independent groups side by side; its own
`tfcapi-lint` target prints `SKIP`, because CI has no provider checkout to
build it from. The noop repositories run the same lint, then `make verify`
with its smaller set: headers, format, `validate` and the apply and destroy
of `test/root`. Nothing there builds or smoke-tests an image.

`module-images` tests and publishes the images in
[`.github/workflows/build.yml`](https://github.com/captf-io/module-images/blob/main/.github/workflows/build.yml),
on pull requests and pushes to `main`; only a push to `main` publishes:

| Job | Runs on | What it runs |
| --- | --- | --- |
| `verify` | `ubuntu-24.04` | `make verify`: `images.json`, versions and locks agree, license headers, shellcheck, trivy |
| `test` | `ubuntu-24.04` and `ubuntu-24.04-arm`, for each cloud | `make test CLOUDS=<cloud>`: build and smoke-test every image of the cloud on both runtimes, natively on amd64 and arm64, including the image lint |
| `publish` | `ubuntu-24.04` | On a push to `main` only, after the jobs above pass: builds each image and runtime for `linux/amd64` and `linux/arm64` with QEMU and buildx, and pushes to GHCR with an SBOM and provenance |

The `test` job runs a matrix of the clouds and two runners, so each image
is smoke-tested on both architectures it ships for. A module repository's
CI lints with the provider release its workflow pins, and `module-images`
with the provider's `main`, so run `make tfcapi-lint` in the module
repository, and `make test` in `module-images`, locally before
you push, to catch contract violations first (see [Lint](#lint)). See
[Releasing a Module](releasing.md) for publishing and tags, and [tfcapi-lint
in CI](tfcapi-lint-ci.md) for running the linter in your own pipeline.

!!! related "See also"

    - [Module Repository Layout](repository-layout.md)
    - [Releasing a Module](releasing.md)
    - [tfcapi-lint](tfcapi-lint.md)
    - [Base Images](base-images.md)
    - [Image Contract](image-contract.md)
    - [Testing (developer guide)](../developer-guide/testing.md)
