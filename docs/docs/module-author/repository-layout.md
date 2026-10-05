---
description: "How to structure a repository of CAPTF modules, modelled on the reference repos: layout, lock files, runtime support, quality gates and docs, and how to start one."
authors:
  - "The CAPTF Authors"
icon: lucide/folder-tree
subtitle: "Structure a repo of modules"
---

# Module Repository Layout

A module repository holds one root module for each CAPTF role (`cluster`,
`machine`, `machinepool`), the Dockerfiles that turn each into an image, and
the checks that keep them consistent. The five cloud repositories
([`aws-modules`](https://github.com/captf-io/aws-modules) and its siblings)
share one layout and one rulebook, and
[`noop-modules`](https://github.com/captf-io/noop-modules) is the smallest
working version of it. This page describes that layout and how to start your
own.

The image contract is in [Image Contract](image-contract.md); this page covers
only how a repository is organized.

## Starting point

There are two routes.

**Fork a reference cloud repository.** Take the repository closest to your
target. You inherit the rulebook, the gates, the CI workflow and a working
test suite, and you replace the cloud-specific resources. Choose this when
you are building modules for a real cloud or platform and want the same
quality bar as the reference sets.

To publish the fork under your own registry and name, change:

- `CLOUD` and `REGISTRY` in the `Makefile`.
- The image names in `.github/workflows/build.yml`.
- The provider pins in each role's `versions.tf`, and the provider blocks in
  `providers.tf` and the plugin in `.tflint.hcl` to match.
- `MACHINE_CAPACITY` and `MACHINE_ARCH` in the `Makefile`: the capacity and
  architecture labels of the machine image, describing the module's default
  instance shape. Leave both empty if the machine module has no default shape,
  as in `openstack-modules`.
- `.trivyignore.yaml`, which carries ignores specific to the original
  resources.

Then rerun `make lock`, and run `make verify` and `make test`. A role you do
not need is deleted along with its directory: the `ROLES` variable lists the
directories that hold a `versions.tf`, so the Makefile follows; also remove the
role from the publish matrix in `.github/workflows/build.yml`. `openstack-modules`
has no `machinepool/` because OpenStack has no native scaling group.

**Start from `noop-modules`.** It has all three roles, both Dockerfiles, a
smoke test and nothing else: every resource is a `terraform_data`, there are no
providers and no lock files, and the Makefile has `help`, `build`, `test` and
the license-header checks only. Choose this when you are writing a module for
one site or one platform, or when you want to grow the checks yourself. You can
adopt the reference gates later by copying `hack/`, `CONVENTIONS.md` and the
Makefile targets from a cloud repository.

!!! note

    The cloud repositories keep `CONVENTIONS.md`, `.dockerignore`,
    `hack/check-layout.sh`, `hack/tf-run.sh` and `test/smoke.sh` identical. If
    you maintain several repositories, keep them identical in yours too.

## The layout

The tree of a reference repository, modelled on
[`CONVENTIONS.md`](https://github.com/captf-io/aws-modules/blob/main/CONVENTIONS.md)
section 1:

```text
<cloud>-modules/
  README.md                 what the modules are, images, quick start, forking
  CONVENTIONS.md            the rulebook for module code
  DESIGN.md                 why the modules look the way they do
  LICENSE.md                Apache-2.0
  Makefile                  every check and build; `make help`
  Dockerfile.terraform      module images on the terraform-base image
  Dockerfile.opentofu       module images on the opentofu-base image
  .dockerignore .gitignore .tflint.hcl .trivyignore.yaml .licenserc.yaml
  .github/workflows/build.yml  .github/dependabot.yml
  hack/                     check-layout.sh, check-tags.sh, tags.json,
                            check-shell.sh, tf-run.sh, testdata/
  locks/terraform/<role>.terraform.lock.hcl
  locks/opentofu/<role>.terraform.lock.hcl
  examples/                 README.md, identity Secret, manifests
  test/smoke.sh             image smoke test
  cluster/ machine/ machinepool/      one directory per role
    *.tf  templates/*.tftpl  tests/*.tftest.hcl  README.md
```

`hack/testdata/` holds good and bad fixtures: `check-layout.sh` runs itself
against them, so every rule it enforces has a test. `hack/tf-run.sh` runs one
Terraform or OpenTofu action for one role in a digest-pinned container, and is
what the Makefile calls; you can run it by hand to reproduce one cell of
`make validate`.

Three things are never committed. `.gitignore` lists them:

- `.terraform/` directories.
- A `.terraform.lock.hcl` inside a role directory. Lock files live under
  `locks/`.
- State files (`*.tfstate*`), and the local `build/`, `.cache/` and `.tools/`
  directories the Makefile creates.

`.dockerignore` goes the other way and lists what an image does receive: only
the role directories and `locks/`. Tests, READMEs, `.terraform/` and lock files
are left out of `/captf/module`.

## Inside a role directory

The full rules are in
[`CONVENTIONS.md`](https://github.com/captf-io/aws-modules/blob/main/CONVENTIONS.md)
sections 2 and 3. The shape of them:

**One block per file.** Every `.tf` file holds exactly one `resource` or
`data` block, and the file stem is the block's local name. Data sources
prefix `data_`:

```text
resource "aws_lb" "api_load_balancer"   ->  api_load_balancer.tf
data "aws_ami" "node_image"             ->  data_node_image.tf
```

Local names are snake_case `<purpose>_<kind>` (`api_load_balancer`,
`node_ingress_rules`). A block that uses `for_each` over many similar objects
is still one block and takes a plural name. `this`, `main`, `default`,
`example` and `self` are rejected.

**Fixed files** may hold several blocks, and only these:

| File | Holds |
| --- | --- |
| `versions.tf` | one `terraform {}` block: `required_version`, `required_providers` |
| `providers.tf` | every `provider` block, aliases included |
| `variables_contract.tf` | the role's contract inputs, in contract order, with the contract's types |
| `variables.tf` | user variables, alphabetical |
| `outputs.tf` | the role's contract outputs, in contract order |
| `outputs_extra.tf` | non-contract outputs, alphabetical; never starting with `captf_` (section 9) |
| `locals_<topic>.tf` | `locals` blocks for one topic, such as `names`, `tags`, `health`, `exports` |

User-data templates live in `templates/<name>.tftpl`. Provider versions are
pinned exactly in `versions.tf`:

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.67.0"
    }
  }
}
```

**Comments.** Every file starts with the Apache-2.0 license header
(`make check-headers` verifies it, `make fix-headers` adds it), then a comment
of one to three lines saying what the block is and why it exists, with a link
to the contract or the cloud's documentation where one explains the choice.
Inline comments explain why, not what. Inside a block, arguments are
alphabetical, with `lifecycle` and `depends_on` last; the formatting is
whatever `terraform fmt` and `tofu fmt` produce.

**Variables and outputs.** Contract inputs use exactly the contract's names
and types, and every output has a `description`. Names, tags, health and
exports have their own sections in `CONVENTIONS.md`. The reference sets
document the same decisions per role in their READMEs.

`noop-modules` is simpler on purpose: each role has `main.tf`, `variables.tf`,
`outputs.tf` and `versions.tf`. The one-block-per-file rule is a convention of
the cloud sets, enforced by their `check-layout.sh`; the image contract does
not require it.

## Lock files and the provider mirror

Provider versions are pinned twice: exactly in `versions.tf`, and with hashes
in a lock file. The lock files live outside the role directories, at
`locks/<runtime>/<role>.terraform.lock.hcl`, for two reasons:

- One lock file cannot serve both runtimes. Terraform drops entries for
  registry hosts the configuration does not use, and OpenTofu's provider
  builds have different hashes.
- The role directory is what ships in the image, and the image should not
  carry them. `.dockerignore` excludes lock files from `/captf/module`.

`make lock` regenerates all of them, for the platforms `linux_amd64`,
`linux_arm64` and `darwin_arm64`. Every `init` in the Makefile and the
Dockerfiles runs on a staged copy of the role with its lock file, with
`-lockfile=readonly`, so a stale lock fails the build rather than updating
silently. A provider upgrade is its own commit: bump the pin, run
`make lock`, then `make verify`.

The image's `mirror` stage copies the role and its lock file and runs
`providers mirror` for `linux_amd64` and `linux_arm64`, which produces the
hermetic mirror at `/captf/providers`. See
[Building a module image](base-images.md#building-a-module-image) and
[One Dockerfile for every role](base-images.md#one-dockerfile-for-every-role).
CAPTF never reads a module's lock file at run time: the controller generates
the root module, and the mirror plus the exact pin decide what runs. The locks
pin development, CI and image builds.

A module with no providers, like `noop-modules`, has no locks. Its mirror stage
runs `tofu get` and creates an empty `/captf/providers`.

## Supporting Terraform and OpenTofu

Every module repository ships two images per role, one on each runtime: a
`terraform` image built `FROM` [`terraform-base`](base-images.md) and an
`opentofu` image built `FROM` `opentofu-base`. Both are built from the same
module source, from the same role directory, so the module has to work on both.
The tags are `vX.Y.Z-terraform` and `vX.Y.Z-opentofu`.

**Version floor.** In the cloud sets every role declares
`required_version = ">= 1.5.0"`; `noop-modules` declares `">= 1.5"`. The
repositories validate on the floors, Terraform 1.5.7 and OpenTofu 1.6.3, as
well as on the runtimes of the base images, so a feature newer than 1.5 fails
`make validate`. The tests are the exception: they need Terraform 1.7 or
OpenTofu 1.8 (mock providers) and run only on the base images' runtimes.

**Separate lock files.** Each role has one lock file per runtime, under
`locks/terraform/` and `locks/opentofu/` (see above).

**What keeps a module portable.** `hack/check-layout.sh` rejects these in a
role directory:

- `main.tf` files, `.tofu` files and `.tf.json` files.
- `module` calls (modules are flat), `check` blocks, and `moved`, `removed`
  and `import` blocks.
- `backend` and `cloud` blocks, because CAPTF generates the root module and
  owns the state, and provisioners.
- `ephemeral` resources.
- The functions `timestamp()`, `uuid()`, `plantimestamp()` and
  `templatestring()`, in `.tf` files and in templates, because a module must
  plan deterministically.

`CONVENTIONS.md` section 4 adds rules that review enforces rather than a tool:

- No variable validation that refers to other variables (Terraform 1.9 or
  later). Put cross-variable checks in a `lifecycle.precondition` on the role's
  primary resource instead.
- No write-only arguments and no provider-defined functions.
- No OpenTofu-only features: provider `for_each`, `enabled`, early variable
  evaluation and state encryption.
- Do not rely on `&&` and `||` short-circuiting: the floor runtimes do not
  short-circuit them. Guard operands with `coalesce()` or `try()`. A
  conditional does evaluate only the branch it picks.

The checked-in tests must pass on both runtimes too. Section 14 of
`CONVENTIONS.md` lists the test features that differ between them and should
be avoided.

!!! note

    Terraform 1.5 ignores `*.tftest.hcl`, but OpenTofu 1.6 reads them at
    `init` and fails on `mock_provider`. The Makefile therefore runs the
    OpenTofu floor on a staged copy without `tests/`.

For which runtimes and versions CAPTF itself supports, see
[Compatibility](../operator-guide/compatibility.md).

## Quality gates

The host needs `make`, `podman` (or `docker` with `ENGINE=docker`), `jq` and
Go (to build [tfcapi-lint](tfcapi-lint.md)). Every other tool runs in a
container pinned by digest, as the host user, with the repository mounted at
`/work`, so nothing in the repository is left owned by root and a gate gives
the same result on every machine.

`make help` lists the targets. `make verify` runs all the checks, in this
order:

| Target | Enforces |
| --- | --- |
| `check-headers` | The Apache-2.0 license header on every source file (`.licenserc.yaml`). |
| `fmt-check` | `terraform fmt` and `tofu fmt` output, recursively. |
| `check-conventions` | `hack/check-layout.sh` (file layout, naming, forbidden blocks and functions) and `hack/check-tags.sh` (every taggable resource sets its tags from `local.tags`; `hack/tags.json` lists exempt types with a reason). |
| `shellcheck` | `hack/check-shell.sh`: shellcheck over `hack/`, `test/` and every shell template, rendered with placeholders. |
| `validate` | `init` and `validate` per role, on both current runtimes and on the floors Terraform 1.5.7 and OpenTofu 1.6.3. |
| `unit-test` | `terraform test` and `tofu test` per role, with mocked providers. |
| `tflint` | tflint with the terraform ruleset (preset `all`) and the cloud's ruleset, configured in `.tflint.hcl`. |
| `tfcapi-lint` | `tfcapi-lint module --strict` per role. It is built from the provider repository (`PROVIDER_DIR`), or taken from `TFCAPI_LINT`, and skips when neither is available. |
| `scan` | `trivy config` over Dockerfiles, workflows and HCL. Every ignore in `.trivyignore.yaml` needs a path and a statement of why. |

`make build` builds the images, and `make test` builds them and runs
`test/smoke.sh`: labels, then `init` and `validate` from the image's provider
mirror with networking off, then `tfcapi-lint image --strict`. Variables such
as `ROLES=machine`, `RUNTIMES=opentofu` and `ENGINE=docker` narrow or redirect
a run.

!!! warning

    `PROVIDER_DIR` defaults to `../../cluster-api-provider-terraform`. If the
    provider repository is cloned elsewhere, `tfcapi-lint` skips without
    failing. Pass `PROVIDER_DIR=<path>` or `TFCAPI_LINT=<binary>` so the gate
    runs.

The test layers, and how to write the `*.tftest.hcl` files, are in
[Testing a Module](testing.md).

## Documenting a module

Each role has a `README.md` with the H1 `<cloud>-<role>` and these sections,
in this order (`CONVENTIONS.md` section 17):

1. What it creates, as a resource table.
2. Prerequisites: network, quotas, the identity's permissions, image
   requirements.
3. Inputs: the contract inputs used and a table of user variables.
4. Outputs.
5. Exports.
6. Identity Secret.
7. Lifecycle (machinepool): what updates in place and what rolls.
8. Bootstrap (machine and machinepool).
9. Tags.
10. Health.
11. Any cloud-specific sections.
12. Limitations.
13. Exceptions.
14. Examples.

**Exceptions** is where a deliberate deviation from `CONVENTIONS.md` is
recorded, with its reason. A warning that `tfcapi-lint` is allowed to emit is
listed there too, next to the `TFCAPI_LINT_ALLOW_<role>` variable in the
Makefile that permits it, and a `.trivyignore.yaml` entry carries its own
statement.

`DESIGN.md` has exactly five top-level sections: Scope, Decisions, Exports,
Unverified and Rejected alternatives. It records each decision with the
evidence behind it, what was rejected, and which facts have not yet been
checked against a real cloud. Write the unverified list honestly: it tells a
reader what the first real apply is testing.

The top-level `README.md` covers what the modules are and why, the images and
tags, compatibility (runtimes, provider pins, contract version), a quick
start, development targets, releasing and forking.

`examples/` holds a `README.md`, the identity Secret, and manifests that use
the images. The manifests pin a release tag (`vX.Y.Z-<runtime>`), never a
moving tag. Role READMEs do the same.

!!! related "See also"

    - [Testing a Module](testing.md)
    - [Releasing a Module](releasing.md)
    - [Base Images](base-images.md)
    - [Image Contract](image-contract.md)
    - [tfcapi-lint](tfcapi-lint.md)
    - [Module Design Patterns](design-patterns.md)
    - [Cloud Modules](../cloud-modules/README.md)
