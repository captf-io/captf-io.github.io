---
description: "How the CAPTF reference modules are laid out, one module per repository, and how the module images are built from them in `module-images`."
authors:
  - "The CAPTF Authors"
icon: lucide/folder-tree
subtitle: "Structure a repo of modules"
---

# Module Repository Layout

The reference modules use one repository for each module. A repository holds
the root module for one CAPTF role (`cluster`, `machine` or `machinepool`) at
its root, and the checks that keep it consistent. It is named
`terraform-<provider>-<role>`, for example
[`terraform-aws-cluster`](https://github.com/captf-io/terraform-aws-cluster),
and is published on GitHub and on the Terraform Registry as
`captf-io/<role>/<provider>`. The providers are `aws`, `azure`, `google`,
`oci`, `openstack` and `noop`; OpenStack has no `machinepool`. The 14 cloud
repositories share one layout and one rulebook, and the three
[`terraform-noop-*`](https://github.com/captf-io/terraform-noop-cluster)
repositories are the smallest working version of it.

The module images (`ghcr.io/captf-io/module-images/<cloud>-<role>`) are built from a
separate repository,
[`module-images`](https://github.com/captf-io/module-images), which holds no
module code: it holds the Dockerfiles, the lock files and the image smoke
test, and fetches each released module from the Registry. This page describes
the module repositories first and `module-images`
[after them](#the-image-repositories).

The image contract is in [Image Contract](image-contract.md); this page covers
only how a repository is organized.

## Starting point

There are two routes.

**Fork a reference cloud repository.** Take the `terraform-*` repository
closest to your target. You inherit the rulebook, the gates, the CI workflow
and a working test suite, and you replace the cloud-specific resources. Choose
this when you are building modules for a real cloud or platform and want the
same quality bar as the reference sets.

To publish the fork under your own name, change:

- `CLOUD` and `ROLE` in the `Makefile`, and its header comment.
- The provider pins in `versions.tf`, and the provider blocks in
  `providers.tf` and the plugin in `.tflint.hcl` to match.
- `TFCAPI_LINT_ALLOW` in the `Makefile`, if you accept a `tfcapi-lint`
  warning, and `.trivyignore.yaml`, which carries ignores specific to the
  original resources.
- The README, `DESIGN.md` and `examples/`, which describe the original.

Then run `make verify`. A role you do not need is a repository you do not
fork. To ship images as well, fork
`module-images` too (see [the image repositories](#the-image-repositories)).

**Start from `terraform-noop-*`.** Each repository has one role, a handful of
files and nothing else: every resource is a `terraform_data`, there are no
providers, and the checks are format, `validate` on both runtimes and their
floors, an apply and destroy of `test/root` (every contract input), and
license headers. Choose this when you are writing a module for one site or one
platform, or when you want to grow the checks yourself. You can adopt the
reference gates later by copying `hack/`, `CONVENTIONS.md` and the Makefile
targets from a cloud repository. To build images, start from
[`module-images`](https://github.com/captf-io/module-images): the `noop-*`
images are its smallest.

!!! note

    The cloud repositories keep `CONVENTIONS.md`, `hack/tf-run.sh`,
    `hack/check-layout.sh`, `hack/check-shell.sh`, `hack/check-tags.sh`,
    `hack/testdata/`, `.gitignore`, `.licenserc.yaml`,
    `.github/workflows/ci.yml` and `.github/dependabot.yml` identical. If you
    maintain several repositories, keep them identical in yours too; nothing
    enforces it, so apply a change everywhere and `diff` against one of them.

## The layout

The tree of a reference module repository, modelled on
[`CONVENTIONS.md`](https://github.com/captf-io/terraform-aws-cluster/blob/main/CONVENTIONS.md)
section 1:

```text
terraform-<provider>-<role>/
  README.md                 what the module creates, how to develop it
  CONVENTIONS.md            the rulebook for module code
  DESIGN.md                 why the module looks the way it does
  LICENSE.md                Apache-2.0
  Makefile                  every check; `make help`
  .gitignore .licenserc.yaml .tflint.hcl .trivyignore.yaml
  .github/workflows/ci.yml  .github/dependabot.yml
  hack/                     check-layout.sh, check-tags.sh, tags.json,
                            check-shell.sh, tf-run.sh, testdata/
  examples/                 README.md, identity Secret, manifests
  *.tf  templates/*.tftpl  tests/*.tftest.hcl
                            the root module, at the repository root
```

The repository also carries the community files (`CODE_OF_CONDUCT.md`,
`CONTRIBUTING.md`, `SECURITY.md`, `CODEOWNERS`, the pull request template).
It has no `Dockerfile`, no `locks/` and no `test/smoke.sh`: nothing in it
builds an image.

`hack/testdata/` holds good and bad fixtures: `check-layout.sh` runs itself
against them, so every rule it enforces has a test. `hack/tf-run.sh` runs one
Terraform or OpenTofu action for the module in a digest-pinned container, and
is what the Makefile calls; you can run it by hand to reproduce one cell of
`make validate`.

Two things are never committed. `.gitignore` lists them:

- `.terraform/` directories and any `.terraform.lock.hcl`. No lock file is
  committed (see [Lock files and the provider
  mirror](#lock-files-and-the-provider-mirror)).
- State files (`*.tfstate*`), and the local `build/`, `.cache/` and `.tools/`
  directories the Makefile creates.

The `terraform-noop-*` repositories are lighter: `main.tf`, `variables.tf`,
`outputs.tf` and `versions.tf` at the root, a `test/root` that sets every
contract input, a `Makefile` with `help`, `fmt`, `validate`, `test` and the
license-header targets, and `hack/tf-run.sh`. They have no `CONVENTIONS.md`.

## Inside a role directory

The module sits at the repository root, one role to a repository. The full
rules are in
[`CONVENTIONS.md`](https://github.com/captf-io/terraform-aws-cluster/blob/main/CONVENTIONS.md)
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
exports have their own sections in `CONVENTIONS.md`. Each repository's
`DESIGN.md` documents the same decisions for its role.

The `terraform-noop-*` modules are simpler on purpose, with a single
`main.tf`. The one-block-per-file rule is a convention of the cloud sets,
enforced by their `check-layout.sh`; the image contract does not require it.

## Lock files and the provider mirror

Provider versions are pinned exactly in `versions.tf`, and a module repository
commits no lock file (`CONVENTIONS.md` section 5). `.gitignore` excludes
`**/.terraform.lock.hcl`, and every `init` in the Makefile and in CI resolves
the exact pins afresh, on a staged copy of the module that is thrown away
with the stage. One lock file could not serve both runtimes anyway: Terraform
drops entries for registry hosts the configuration does not use, and
OpenTofu's provider builds have different hashes. A provider upgrade is its
own commit: bump the pin, then `make verify`.

CAPTF never reads a module's lock file at run time: the controller generates
the root module, and the image's provider mirror plus the exact pin decide
what runs.

The lock files and the mirror belong to the image build, in
`module-images`. There the lock files live outside the modules, at
`locks/<runtime>/<image>.terraform.lock.hcl`, and only the module's top-level
`*.tf` files and `templates/` ship in the image. `make lock` regenerates all
of them, for the platforms `linux_amd64`, `linux_arm64` and `darwin_arm64`.
A stale lock fails the build rather than updating silently. A provider
upgrade is a bump of the pin in the module and a release, then
`make lock IMAGES=<image>` in `module-images`.

The image's `mirror` stage copies the role and its lock file and runs
`providers mirror` for `linux_amd64` and `linux_arm64`, which produces the
hermetic mirror at `/captf/providers`. See
[Building a module image](base-images.md#building-a-module-image) and
[One Dockerfile for every role](base-images.md#one-dockerfile-for-every-role).
A module with no providers, like the noop modules, has no locks. Its mirror
stage runs `tofu get` and creates an empty `/captf/providers`.

## Supporting Terraform and OpenTofu

Every module ships two images per role, one on each runtime: a `terraform`
image built `FROM` [`terraform-base`](base-images.md) and an `opentofu` image
built `FROM` `opentofu-base`. Both are built from the same module source, so
the module has to work on both. The tags are `vX.Y.Z-terraform` and
`vX.Y.Z-opentofu`.

**Version floor.** In the cloud sets every module declares
`required_version = ">= 1.5.0"`. The module repositories validate on the
floors, Terraform 1.5.7 and OpenTofu 1.6.3, as well as on the runtimes of the
base images, so a feature newer than 1.5 fails `make validate`. The tests are
the exception: they need Terraform 1.7 or OpenTofu 1.8 (mock providers) and
run only on the base images' runtimes.

**No shared lock file.** Nothing is committed, so the two runtimes cannot
disagree about one (see above). `module-images` keeps one lock file per image and
runtime.

**What keeps a module portable.** `hack/check-layout.sh` rejects these in the
module:

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

`make help` lists the targets. `make verify` runs all the checks, and is
what CI runs (`.github/workflows/ci.yml`), after linting the module with the
[tfcapi-lint GitHub Action](tfcapi-lint-ci.md) itself:

| Target | Enforces |
| --- | --- |
| `check-headers` | The Apache-2.0 license header on every source file (`.licenserc.yaml`). |
| `fmt-check` | `terraform fmt` and `tofu fmt` output, recursively. |
| `check-conventions` | `hack/check-layout.sh` (file layout, naming, forbidden blocks and functions) and `hack/check-tags.sh` (every taggable resource sets its tags from `local.tags`; `hack/tags.json` lists exempt types with a reason). |
| `shellcheck` | `hack/check-shell.sh`: shellcheck over `hack/` and every shell template, rendered with placeholders. |
| `validate` | `init` and `validate` on both current runtimes and on the floors Terraform 1.5.7 and OpenTofu 1.6.3. |
| `unit-test` | `terraform test` and `tofu test`, with mocked providers. |
| `tflint` | tflint with the terraform ruleset (preset `all`) and the cloud's ruleset, configured in `.tflint.hcl`. |
| `tfcapi-lint` | `tfcapi-lint module --role <role> --strict`. It is built from the provider repository (`PROVIDER_DIR`), or taken from `TFCAPI_LINT`, and skips when neither is available, as in CI, where the GitHub Action runs the lint instead. |
| `scan` | `trivy config` over workflows and HCL. Every ignore in `.trivyignore.yaml` needs a path and a statement of why. |

There is no `lock`, `build` or `test` target: a module repository builds no
image. Variables such as `RUNTIMES=opentofu` and `ENGINE=docker` narrow or
redirect a run. The noop repositories run a smaller `verify`: `check-headers`,
`fmt-check`, `validate` and `test`, which applies and destroys `test/root`.

!!! warning

    `PROVIDER_DIR` defaults to `../cluster-api-provider-terraform`, which is
    right when the module and the provider repository are siblings. If the
    provider repository is cloned elsewhere, `tfcapi-lint` skips without
    failing. Pass `PROVIDER_DIR=<path>` or `TFCAPI_LINT=<binary>` so the gate
    runs.

The test layers, and how to write the `*.tftest.hcl` files, are in
[Testing a Module](testing.md).

## Documenting a module

Each module's `README.md` has the H1 `terraform-<provider>-<role>`, a badge
row and a status note, an intro paragraph, then these sections, in this order
(`CONVENTIONS.md` section 17):

1. Usage: the module image, the Terraform Registry address
   `captf-io/<role>/<provider>`, and what calling the module directly implies.
2. What it creates, as a resource table.
3. Prerequisites: network, quotas, the identity's permissions, image
   requirements.
4. Inputs: the contract inputs used and a table of user variables.
5. Outputs.
6. Exports.
7. Identity Secret.
8. Lifecycle (machinepool): what updates in place and what rolls.
9. Bootstrap (machine and machinepool).
10. Tags.
11. Health.
12. Any cloud-specific sections.
13. Limitations.
14. Exceptions.
15. Examples.
16. Development: the host tools and the `make` targets.

Links in the README are absolute
(`https://github.com/captf-io/<repo>/blob/main/...`), because the Terraform
Registry renders it as the module's page, where relative links break.

**Exceptions** is where a deliberate deviation from `CONVENTIONS.md` is
recorded, with its reason. A warning that `tfcapi-lint` is allowed to emit is
listed there too, next to the `TFCAPI_LINT_ALLOW` variable in the Makefile
that permits it, and a `.trivyignore.yaml` entry carries its own statement.

`DESIGN.md` is specific to the repository's role and has exactly five
top-level sections: Scope, Decisions, Exports, Unverified and Rejected
alternatives. It records each decision with the evidence behind it, what was
rejected, and which facts have not yet been checked against a real cloud.
Decision and Unverified numbers stay stable, because code comments cite them.
Write the unverified list honestly: it tells a reader what the first real
apply is testing.

`examples/` holds a `README.md`, the identity Secret, and manifests that use
the images. The manifests pin a release tag (`vX.Y.Z-<runtime>`), never a
moving tag. The README does the same.

## The image repositories

All the images are built from one repository,
[`module-images`](https://github.com/captf-io/module-images). It holds no
module code. The module of each image is a release of a
`terraform-<provider>-<role>` repository, fetched from the Terraform Registry
at build time. The layout:

```text
module-images/
  README.md  LICENSE.md
  Makefile                  fetch, build, test, lock and the checks; `make help`
  Dockerfile.terraform      module images on the terraform-base image
  Dockerfile.opentofu       module images on the opentofu-base image
  images.json               per image: role, capacity labels, allowed warnings
  sources/versions.tf       the module release of each image (Registry blocks)
  locks/terraform/<image>.terraform.lock.hcl
  locks/opentofu/<image>.terraform.lock.hcl
  test/smoke.sh             image smoke test
  hack/                     images.sh, fetch.sh, lock.sh, build.sh
```

`sources/versions.tf` pins each image's module as a Registry module block:

```hcl title="sources/versions.tf (trimmed)"
module "aws-machine" {
  source  = "captf-io/machine/aws"
  version = "0.1.0"
}
```

The build fetches that release, keeps only the top-level `*.tf` files and
`templates/`, and writes them to `/captf/module`. Tests, READMEs, `.terraform/`
and lock files are left out. The Dockerfiles share the stages
`mirror → module → <role>` across all images.

To publish a fork's images under your own registry and name, change
`REGISTRY` in the `Makefile`, the image names in `images.json` and the
workflow, and point `sources/versions.tf` at your modules, then rerun
`make lock` and run `make verify` and `make test`. See [Releasing a
Module](releasing.md#publishing-from-a-fork).

!!! related "See also"

    - [Testing a Module](testing.md)
    - [Releasing a Module](releasing.md)
    - [Base Images](base-images.md)
    - [Image Contract](image-contract.md)
    - [tfcapi-lint](tfcapi-lint.md)
    - [Module Design Patterns](design-patterns.md)
    - [Cloud Modules](../cloud-modules/README.md)
