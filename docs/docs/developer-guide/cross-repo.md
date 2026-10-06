---
description: "Work across the captf-io repositories: a shared workspace, the order of a contract change, module images, license headers and base image bumps."
authors:
  - "The CAPTF Authors"
icon: lucide/git-merge
subtitle: "Changes that span repositories"
---

# Working Across Repositories

CAPTF lives in several repositories: the provider, two base images, the
`module-images` repository, the 17 `terraform-<provider>-<role>` repositories, the website
and the organization's `.github` repository. Most
changes touch one of them. This page is for a change that spans more than one,
such as a contract change, a new convention for the module repositories or a
new community file. For the build, lint and test loop of the provider itself,
see [Contributing](contributing.md).

## A workspace with every repository

Clone every repository as a sibling in one directory:

```sh
mkdir captf-io && cd captf-io
gh repo list captf-io --limit 500 --json name -q '.[].name'
for r in $(gh repo list captf-io --limit 500 --json name -q '.[].name'); do
  git clone "https://github.com/captf-io/$r.git"
done
```

Two things depend on the siblings being there:

- `module-images` builds [tfcapi-lint](../module-author/tfcapi-lint.md)
  from the provider checkout. Its Makefile reads `PROVIDER_DIR`, which
  defaults to `../cluster-api-provider-terraform`, the sibling in a flat
  workspace. If the directory has no `cmd/tfcapi-lint` and `TFCAPI_LINT` is
  not set, the image lint in `make test` prints `SKIP` and succeeds. Pass the
  path explicitly when your layout differs:

    ```sh
    cd module-images
    make test PROVIDER_DIR=../cluster-api-provider-terraform
    ```

    Alternatively, set `TFCAPI_LINT` to a binary you built or
    [downloaded](../module-author/tfcapi-lint.md#install).

- A change to the [README components](readme-components.md) is applied by
  hand to the README of every checkout; `grep` across the workspace finds
  them. See [Community files and READMEs](#community-files-and-readmes).

## Order of a contract change

A change to the [module contract](../module-author/contract/README.md) lands
in this order:

1. **The provider.** The contract types and the JSON schemas live in
   `internal/contract` in
   [`cluster-api-provider-terraform`](https://github.com/captf-io/cluster-api-provider-terraform),
   and tfcapi-lint is built from the same package. Change them, the
   controllers that use them and the linter together.
2. **The docs.** Update the contract pages under `module-author/contract/`
   (and the [image contract](../module-author/image-contract.md) if a path or
   label changed) in
   [`captf-io.github.io`](https://github.com/captf-io/captf-io.github.io). See
   [Contributing to the Docs](docs-workflow.md).
3. **Every `terraform-<provider>-<role>` repository.** These 17 repositories
   hold the only copy of the module code. Bring each in line with the new
   contract and tag a release; the Terraform Registry publishes it.
4. **`module-images`.** Dependabot bumps the module versions in
   `sources/versions.tf` after each release. If a release changes providers,
   run `make lock IMAGES=<image>` and commit the locks to the Dependabot
   branch. The build verifies the SSH signature of each module's release
   tag, so a module release must be a signed annotated tag. See
   [Releasing a Module](../module-author/releasing.md).

The order follows who depends on whom. The modules are linted by
the provider's tfcapi-lint, so they can only pass a new check once the
provider has it. The docs describe what the provider enforces and are what
module authors read, so they follow the code and precede the modules that
apply the change. The contract is `v1alpha1`, so a change is cheap now, but it
still breaks every module written against it.

## Module images and module repositories

The six image repositories that once held a copy of the modules (`aws-modules`,
`azure-modules`, `gcp-modules`, `oci-modules`, `openstack-modules` and
`noop-modules`) were replaced by one repository,
[`module-images`](https://github.com/captf-io/module-images), and deleted,
along with the images they published. It holds no module code, so there is no skeleton to keep identical
across repositories. What it holds:

| Path | Holds |
| --- | --- |
| `sources/versions.tf` | One Registry `module` block for each image, pinning the module release the image contains. |
| `images.json` | The per-image build values: role, machine capacity labels and the allowed tfcapi-lint warnings. |
| `locks/<runtime>/<image>.terraform.lock.hcl` | The provider lock files for each runtime and image. |

A change to one module is made in its `terraform-<provider>-<role>`
repository, with `make verify` before you push. To try an unreleased module
change in an image, build from local checkouts, with the `terraform-*`
repositories as siblings of `module-images`:

```sh
cd module-images
make test IMAGES=aws-machine LOCAL_MODULES=..
```

A `LOCAL_MODULES` build has no release tag, so it skips the tag signature
check and says so.

The checks that gate `module-images` are `make verify` (the `images.json`,
version and lock files agree; license headers; shellcheck; trivy) and
`make test` (fetch, build and smoke-test every image on both runtimes). Narrow
a run with `CLOUDS=aws`, `RUNTIMES=opentofu` or `IMAGES=noop-machine`. See
[Testing a Module](../module-author/testing.md) for the checks.

## Community files and READMEs

Every repository carries the same copies of these files:

- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `LICENSE.md`
- `CODEOWNERS`
- `.github/pull_request_template.md`

The canonical copies are in the [`.github`
repository](https://github.com/captf-io/.github). Change them there first,
then copy the file into every other repository and push each one. No tool
copies them: check with `md5sum` that all repositories have the same file.

```sh
md5sum */CONTRIBUTING.md .github/CONTRIBUTING.md | sort
```

Every README is composed from the same [README
components](readme-components.md): a header, a badge row, a status note and
a footer. Their sources and images are in the website repository, and
nothing syncs them: change the component there first, then apply the change
to each README by hand.

## License headers

Every source file starts with the Apache-2.0 header with the copyright held by
The CAPTF Authors. Every repository, including `.github`, has the same two
targets, which run
[SkyWalking Eyes](https://github.com/apache/skywalking-eyes) in a container
(`ENGINE=podman` by default, or `docker`):

```sh
make check-headers   # fail on any source file without the header
make fix-headers     # add the header to every file missing it
```

Each repository's `.licenserc.yaml` says which files need the header and which
do not, such as Markdown, JSON, lock files and `CODEOWNERS`. The file differs
in the provider, the website and `.github`, which have different file types.
`check-headers` runs in `make verify` where a repository has one, and as the `license-headers` job in each repository's CI workflow; a failing
job blocks publishing.

Run `make fix-headers` after adding a new source file, then review the diff.

## Base image bumps

`module-images` pins each base image by tag and digest, for example
`opentofu-base:<version>@sha256:<digest>`. See [Base
Images](../module-author/base-images.md#tags-and-pinning). The base images are
rebuilt weekly, and the `.github/dependabot.yml` of `module-images` has a
`docker` stanza that bumps the pin and opens one pull request with the commit
prefix `deps`. Merging it rebuilds every image on the new base and publishes
new digests under the same `vX.Y.Z-<runtime>` tags. The same file has a
`terraform` stanza that bumps the module versions in `sources/versions.tf`
daily.

## Commits and pull requests

Open one pull request per repository. Name the other pull requests in each
description and land them in the order of [a contract
change](#order-of-a-contract-change): provider, docs, then the `terraform-*` module repositories, then `module-images`. Mark later pull requests as blocked on the earlier ones until
those merge.

Commit style, the checks to run before you push and the licensing terms are in
[CONTRIBUTING.md](https://github.com/captf-io/.github/blob/main/CONTRIBUTING.md):
subject `<subsystem>: <summary>` in the imperative, at most about 50
characters; a body that explains why; refactors apart from features.

!!! related "See also"

    - [Contributing](contributing.md)
    - [Contributing to the Docs](docs-workflow.md)
    - [Releasing](releasing.md)
    - [Base Images](../module-author/base-images.md)
    - [tfcapi-lint](../module-author/tfcapi-lint.md)
    - [Module Repository Layout](../module-author/repository-layout.md)
    - [Repositories and Images](../reference/repositories.md)
