---
description: "Work across the captf-io repositories: a shared workspace, the order of a contract change, files that must stay identical, license headers and base image bumps."
authors:
  - "The CAPTF Authors"
icon: lucide/git-merge
subtitle: "Changes that span repositories"
---

# Working Across Repositories

CAPTF lives in several repositories: the provider, two base images, six module
repositories, the website and the organization's `.github` repository. Most
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

- The module repositories build [tfcapi-lint](../module-author/tfcapi-lint.md)
  from the provider checkout. Their Makefile reads `PROVIDER_DIR`, which
  defaults to `../../cluster-api-provider-terraform`. From a module repository in a
  flat workspace that resolves above the workspace, not to the sibling. When
  the directory has no `cmd/tfcapi-lint` and `TFCAPI_LINT` is not set, the
  `tfcapi-lint` target and the image lint in `make test` print `SKIP` and
  succeed. Pass the sibling path:

    ```sh
    cd aws-modules
    make verify PROVIDER_DIR=../cluster-api-provider-terraform
    ```

    Alternatively, set `TFCAPI_LINT` to a binary you built or
    [downloaded](../module-author/tfcapi-lint.md#install).

- The README fragment sync in `.github` works on checkouts: `make readme`
  there defaults `WORKSPACE` to `..`, so it reads and writes the sibling
  repositories. See [Community files and README
  fragments](#community-files-and-readme-fragments).

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
3. **Every module repository.** Bring `aws-modules`, `azure-modules`,
   `gcp-modules`, `oci-modules`, `openstack-modules` and `noop-modules` in line
   with the new contract.

The order follows who depends on whom. The module repositories are linted by
the provider's tfcapi-lint, so they can only pass a new check once the
provider has it. The docs describe what the provider enforces and are what
module authors read, so they follow the code and precede the modules that
apply the change. The contract is `v1alpha1`, so a change is cheap now, but it
still breaks every module written against it.

## Files that must stay identical

The five cloud module repositories (`aws-modules`, `azure-modules`,
`gcp-modules`, `oci-modules`, `openstack-modules`) share a skeleton. These
files are byte-identical across all five:

| File | Holds |
| --- | --- |
| `CONVENTIONS.md` | The rulebook for module code. It says so itself: a change is a change in all five repositories. |
| `.dockerignore` | The build context filter. |
| `hack/check-layout.sh` | The check of the file layout and language subset in `CONVENTIONS.md`. |
| `hack/tf-run.sh` | The script that runs `fmt`, `lock` and `validate` for a runtime, role and floor. |
| `test/smoke.sh` | The image smoke test. |

Per-cloud values aside, these also match: the `Makefile`, `Dockerfile.opentofu`,
`Dockerfile.terraform` and `.github/workflows/build.yml`. They differ in the
cloud name, the default machine capacity and architecture, the image names, the
allowed tfcapi-lint warnings and, for OpenStack, the role list (it has no
`machinepool`). Compare them with a diff rather than by eye.

No tool enforces this. Apply a skeleton change to all five repositories, then
check it with `diff` against `aws-modules`, run from the workspace:

```sh
for r in azure gcp oci openstack; do
  for f in CONVENTIONS.md .dockerignore hack/check-layout.sh \
           hack/tf-run.sh test/smoke.sh; do
    cmp aws-modules/$f $r-modules/$f
  done
done

md5sum */CONVENTIONS.md */hack/tf-run.sh | sort
```

`cmp` prints nothing for identical files. For `Makefile`, `Dockerfile.*` and
`build.yml`, run `diff aws-modules/<file> <cloud>-modules/<file>` and confirm
the output is only the per-cloud lines. Run `make verify
PROVIDER_DIR=../cluster-api-provider-terraform` in each repository before you
push. See [Module Repository
Layout](../module-author/repository-layout.md) for what the skeleton holds
and [Testing a Module](../module-author/testing.md) for the checks.

### `noop-modules`

[`noop-modules`](https://github.com/captf-io/noop-modules) shares the
Dockerfile and workflow skeleton, but not the files above. It has no
`CONVENTIONS.md`, no `hack/` directory and no `locks/`, and its own
`.dockerignore` and `test/smoke.sh` differ from the cloud copies. Apply a change
to it when the change is to the image build, the tags or the CI jobs; skip
changes that belong to `CONVENTIONS.md`, the layout check or the lock files.
Its Makefile has only `help`, `build` and `test`, so it does not run
`make verify`.

## Community files and README fragments

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

The `.github` repository also holds the README fragments: the header, status
note and footer that every README carries between `<!-- captf:header -->`
style markers. Never edit inside the markers. Edit the templates in
[`readme/`](https://github.com/captf-io/.github/tree/main/readme), then, from
the `.github` checkout with the others beside it:

```sh
make readme         # render the banners and fill every README's blocks
make readme-check   # write nothing; fail if a banner or block is out of date
```

Commit the banners and templates in `.github` and push them first, because
READMEs load the banners from its `main` branch. Then commit the changed
README in each repository. To point the sync at another directory, set
`WORKSPACE=<dir>`.

[`readme/repos.toml`](https://github.com/captf-io/.github/blob/main/readme/repos.toml)
lists the repositories that carry the fragments. A new repository goes there,
with its kind, glyph and tagline; the
[`readme/README.md`](https://github.com/captf-io/.github/blob/main/readme/README.md)
file has the full steps.

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
do not, such as Markdown, JSON, lock files and `CODEOWNERS`. The file is
identical in the module and base repositories, including `noop-modules`, and
differs in the provider, the website and `.github`, which have different file
types. `check-headers` runs in `make verify` in the cloud module repositories
and as the `license-headers` job in each repository's CI workflow; a failing
job blocks publishing.

Run `make fix-headers` after adding a new source file, then review the diff.

## Base image bumps

Module repositories pin their base image by tag and digest, for example
`opentofu-base:1.12.6@sha256:<digest>`. See [Base
Images](../module-author/base-images.md#tags-and-pinning). The base images are
rebuilt weekly, and each module repository's `.github/dependabot.yml` has a
`docker` stanza that bumps the pin and opens a pull request with the commit
prefix `deps`. When a base image changes, each of the six module repositories
(the five clouds and `noop-modules`) gets its own pull request. Merge them all,
so that no module repository keeps shipping an old base. The five cloud
repositories carry an identical `dependabot.yml`; the `*-base` repositories
carry another.

## Commits and pull requests

Open one pull request per repository. Name the other pull requests in each
description and land them in the order of [a contract
change](#order-of-a-contract-change): provider, docs, then the module
repositories. Mark later pull requests as blocked on the earlier ones until
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
