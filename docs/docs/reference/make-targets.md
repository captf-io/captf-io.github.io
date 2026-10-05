---
description: "Look up the provider repository's make targets by workflow, what each does and when to run it, and the variables that change them."
tags:
  - Contributors
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/hammer
subtitle: "Every make target"
---

# Make Targets

The provider repository, `cluster-api-provider-terraform`, drives its build,
checks, test environment and releases with `make`. Every tool is a pinned
version that `make` installs into `hack/tools/bin` on first use, so you need
only Go, `make`, and for some targets `podman`, `python3`, `git` or `jq`.
`make` with no target, and `make help`, print the targets with their
one-line descriptions, grouped as they are here.

For how the targets fit into a contribution, see
[Contributing](../developer-guide/contributing.md#the-build-lint-test-and-verify-loop).

## The everyday loop

For most changes, run this before you push:

```sh
make lint test verify
```

| Target | What it gives you |
| --- | --- |
| `make lint` | Style and correctness findings from `golangci-lint` in every module, including the e2e-tagged test code, and from `kube-api-linter` on `api/`. |
| `make test` | The unit tests of every Go module, with the race detector. |
| `make verify` | Every other consistency check: generated files, manifests, schemas, templates, alert rules, license headers and the test-tier guard. |

After you change `api/v1alpha1` or a controller's kubebuilder markers, run
`make generate manifests` first. `make fmt` formats Go code before you
lint it.

To try a change against a real cluster, run `make testenv-up` once, then
`make testenv-reload` after each change. See
[Test environment](#test-environment).

!!! warning "`make verify` fails on unstaged changes"

    Its `verify-gen` step regenerates code and manifests, then runs
    `git diff --exit-code` over the whole tree. Stage your work (`git add`)
    before you run it, or it reports your own edits as a failure.

## Variables

Set a variable on the command line, as in `make docker-build IMG=<image>`.
Unless the table says otherwise, a variable only affects the targets named
in its row.

| Variable | Default | Effect |
| --- | --- | --- |
| `IMG` | `ghcr.io/captf-io/cluster-api-provider-terraform:dev` | The manager and runner image that `docker-build`, `docker-buildx` and `docker-push` build or push. |
| `CONTAINER_TOOL` | `podman` | The tool that builds and pushes images. `docker` works for `docker-build` and `docker-push`. `docker-buildx` needs `podman`. |
| `PLATFORMS` | `linux/amd64,linux/arm64` | The platforms of the manifest list that `docker-buildx` builds. |
| `GO_VERSION` | `1.26` | The Go version used by image builds. |
| `VERSION` | from `hack/version.sh` | The version stamped into binaries, and the tag that release targets use. It is always a valid semantic version: `v0.0.0-dev.g<commit>` before the first release tag. Release targets require `vX.Y.Z` or `vX.Y.Z-rc.N`. |
| `RELEASE_REPO` | `ghcr.io/captf-io/cluster-api-provider-terraform` | The repository of the release image. |
| `RELEASE_IMG` | `$(RELEASE_REPO):$(VERSION)` | The image `manifests-release` writes into the components file. `make release` and `publish.yaml` pass the pushed image by digest. |
| `RELEASE_DIR` | `out` | Where `manifests-release` writes its files. Release assets go to `out/release`. |
| `SKOPEO` | `skopeo` | The `skopeo` binary that `release-image-digest` runs. |
| `RUNNER_IMAGE` | `$(IMG)` | The runner image `make run` gives the manager. |
| `WEBHOOK_CERT_DIR` | `bin/dev-webhook-certs` | Where `make run` keeps its self-signed webhook certificate. |
| `ARGS` | | Extra flags that `make run` passes to the manager. |
| `GOTESTSUM_FORMAT` | `pkgname` | The `gotestsum` output format of `test-cover`. CI sets `github-actions`. |
| `TESTENV_NAME` | `captf-test-dev` | The cluster name for the `testenv-*` targets. It must start with `captf-test-`. |
| `TESTENV_ENGINE` | auto-detected | `podman` or `docker`, for the `testenv-*` and `e2e-*` targets. Auto-detection prefers `podman`. |
| `TESTENV_WORKERS` | `0` | The number of kind worker nodes for `testenv-up`, from 0 to 5. |
| `CAPTF_TESTENV_REUSE` | off | Set to `1` to make `testenv-up` reuse a matching cluster. |
| `TESTENV_ALL` | off | Set to `1` to make `testenv-down` delete every `captf-test-*` cluster. |
| `CAPTF_E2E_CLUSTER` | `captf-test-e2e` | The cluster the `e2e-*` targets use. |
| `CAPTF_E2E_REUSE` | off | Set to `1` to make `e2e-foundation` reuse an existing cluster. |
| `CAPTF_E2E_TEARDOWN` | off | Set to `1` to make `e2e-foundation` delete the cluster after a passing run. |
| `CAPTF_E2E_STABILITY` | `2m` | The length of the foundation suite's stability window. |
| `CAPTF_E2E_WORKERS` | `0` | The number of kind worker nodes for `e2e-foundation`. |
| `CAPTF_E2E_GREENLIGHT_MAX_AGE` | `24h` | How old the green light may be before `e2e-noop` rejects it. |
| `CAPTF_E2E_NOOP_BAD_DIGEST` | off | Set to `1` to run `e2e-noop`'s negative check: one machine gets a nonexistent image digest, and the suite must fail on the image pull. |

An empty value takes the default in the table.

## General

| Target | Description |
| --- | --- |
| `help` | Print every target with its description, grouped. This is the default target. |

## Development

| Target | Description |
| --- | --- |
| `generate` | Regenerate the deepcopy code for `api/` with `controller-gen`. Run it after you change an API type. |
| `manifests` | Regenerate the CRD, RBAC and webhook manifests into `config/`. Run it after you change API types or kubebuilder markers. |
| `fmt` | Format Go code with `gofmt -s` and `goimports`. |
| `vet` | Run `go vet` in every Go module, then on the `test` module's e2e-tagged code. |
| `lint` | Run `golangci-lint` in every module and on the `test` module's e2e-tagged code, then `lint-api`. |
| `lint-api` | Run `kube-api-linter` on the `api/` module. |
| `lint-fix` | Run `lint` with the auto-fixers of both linters on. |

## Test

| Target | Description |
| --- | --- |
| `test` | Run the unit tests of every Go module with `-race -count=1`. It never compiles the e2e-tagged code. |
| `test-cover` | Run the unit tests with `-race` and coverage through `gotestsum`, and write a profile and a JUnit report per module into `bin/`. CI runs this instead of `test`. |
| `cover-check` | Check each package's coverage in the `bin/cover-*.out` profiles against its floor in `hack/coverage-floors.txt`. Run it after `test-cover`. |

See [Testing](../developer-guide/testing.md#running-the-tests) for what the
tests cover, the coverage floors, and how to run one package or one test.

## Test environment

The `testenv-*` targets manage a kind cluster on `podman` (or `docker`) with
cert-manager, Cluster API and CAPTF built from your working tree. Use it to
try a change against a real API server, without a cloud. Each target runs
one operation of the e2e-tagged package `test/env/lifecycle`, with the
pinned `clusterctl` and `kustomize`. Everything for a cluster `<name>` lands
in `bin/testenv/<name>/`: its `kubeconfig`, an `env.sh` that exports
`KUBECONFIG`, a `state.json` and the diagnostics bundles.

| Target | Description |
| --- | --- |
| `testenv-up` | Build the manager image, create the kind cluster, install the providers and wait until they are ready. About 6 minutes cold. |
| `testenv-reload` | Rebuild the manager image from the tree, load it into the nodes and roll the manager Deployment over to it. Run it after each change to the manager or runner. |
| `testenv-status` | Show whether the cluster exists, its nodes, the pods that are not ready and a summary of `state.json`. |
| `testenv-logs` | Collect pod logs, events, CAPI and CAPTF objects and node logs into `bin/testenv/<name>/artifacts/<timestamp>/`. Secrets are not collected. |
| `testenv-down` | Delete the cluster. The `artifacts/` directory is kept. |

```sh
make testenv-up
source bin/testenv/captf-test-dev/env.sh
kubectl get pods -A
make testenv-reload
make testenv-down
```

Only cluster names that start with `captf-test-` are accepted, and the
targets never read `~/.kube/config`. `testenv-up` refuses an existing
cluster unless `CAPTF_TESTENV_REUSE=1` is set. For example, to run a cluster
with one worker node next to the default one:

```sh
make testenv-up TESTENV_NAME=captf-test-pool TESTENV_WORKERS=1
```

## End-to-end

The `e2e-*` targets run the opt-in e2e suites under `test/e2e/`. They need
`podman` or `docker`. `make test` never compiles them, and CI does not run
them. See
[Testing](../developer-guide/testing.md#end-to-end-tests).

| Target | Description |
| --- | --- |
| `e2e-foundation` | Build the manager from your tree and the `captf-test-e2e` cluster, check it stage by stage, and write a green light for it. Run it first. It keeps the cluster after a passing run unless `CAPTF_E2E_TEARDOWN=1`. |
| `e2e-noop` | Run the no-op data-flow suite on the green-lit cluster: Cluster API objects drive the published no-op modules, and the suite checks that data flows from the spec to the module and back and that deletion cleans up. It fails unless `e2e-foundation` passed recently. |
| `e2e-down` | Delete the e2e cluster, `captf-test-e2e` or `CAPTF_E2E_CLUSTER`. The artifacts are kept. |

## Build

| Target | Description |
| --- | --- |
| `build` | Build every `cmd/*` binary into `bin/`. |
| `manager` | Build the static manager into `bin/manager`, and check that it is statically linked. |
| `runner` | Build the static Job runner into `bin/runner`, and check that it is statically linked. |
| `run` | Build the manager and run it out of cluster against your current `kubeconfig`. It turns leader election off and makes a self-signed webhook certificate if needed. |
| `docker-build` | Build the manager and runner image `$(IMG)` for the host platform. |
| `docker-buildx` | Build a multi-architecture manifest list `$(IMG)` for `$(PLATFORMS)`, with `podman`. |
| `docker-push` | Push `$(IMG)`. A manifest list from `docker-buildx` is pushed with all its images. |

`make run` points the manager at `$(RUNNER_IMAGE)`, which is `$(IMG)` by
default. Build the image first when a Job needs a runner you changed:

```sh
make docker-build IMG=<image>
make run RUNNER_IMAGE=<image> ARGS="<flags>"
```

- `<image>` is an image reference the cluster can pull, for example
  `localhost/captf:dev` on a cluster that shares your image store.
- `<flags>` are extra manager flags. Leave out `ARGS` if you have none.

## Verify

`make verify` runs every check below. Each one also runs alone, which is
faster when only one has failed. Several need `python3`, `git` or `podman`.

| Target | Description |
| --- | --- |
| `verify` | Run all the checks in this table. |
| `verify-godoc` | Check that every declaration, parameter, return value and package has a doc comment. |
| `verify-gen` | Run `generate` and `manifests`, then fail if `git diff` shows a change. It needs `git`. |
| `verify-modules` | Check `go.work` and `go.mod` pins, and that no module uses `replace` other than the root module's `api => ./api`. |
| `verify-schemas` | Validate the contract JSON Schemas, their examples and the golden inputs and outputs. It needs `python3` with `jsonschema`. |
| `verify-components` | Check the clusterctl components built from `config/default`. |
| `verify-metadata` | Validate `metadata.yaml`, and check that `releaseSeries` only grows compared with the previous tag. |
| `verify-version` | Check that `hack/version.sh` prints a valid semantic version for every checkout state. |
| `verify-templates` | Render `templates/` with the pinned `clusterctl`. |
| `verify-local-repository` | Generate the provider and both flavors from a clusterctl local repository of the release assets, offline and without a cluster. |
| `verify-test-tiers` | Check that e2e code carries the `e2e` build tag and lives only in `test/e2e/` and `test/env/lifecycle/`. |
| `check-licenses` | Check that no MPL-2.0 dependency of `tfcapi-lint` applies Exhibit B. |
| `check-headers` | Check that every source file starts with the Apache-2.0 license header, copyright The CAPTF Authors. `.licenserc.yaml` lists the exempt files. Runs Apache SkyWalking Eyes in a container pinned by digest, with `CONTAINER_TOOL`. Part of `verify`. |
| `fix-headers` | Add the Apache-2.0 license header to every source file that lacks it. |
| `promtool-check` | Check the alert rules with `promtool`, and build the Prometheus component on `config/default`. |
| `promtool-test` | Unit-test the alert rules. |

`verify` does not run `cover-check`, which needs the profiles `test-cover`
writes. CI runs the two as separate steps.

## Release

These targets build and publish a release. Pushing a release tag is the
release: `publish.yaml` runs `release-preflight`, `release-assets` and
`release-github` for it. The targets need a clean tree with `HEAD` tagged
`$(VERSION)`. A tag never moves, so a bad release candidate gets a new one.
[Releasing](../developer-guide/releasing.md#checklist) has the full
procedure. Publishing is for maintainers.

| Target | Description |
| --- | --- |
| `release-preflight` | Check that the tree is clean, `HEAD` carries the tag `$(VERSION)`, and `metadata.yaml` only grows. |
| `release` | The manual fallback for when CI cannot run; never run it for a tag `publish.yaml` publishes. Run the preflight, build and push a host-platform manager image (unsigned), and build every asset into `out/release` with the image pinned by digest. Set `VERSION=vX.Y.Z`. |
| `release-image-digest` | Print the registry digest of `$(RELEASE_REPO):$(VERSION)`. It needs `skopeo`. |
| `manifests-release` | Build `out/infrastructure-components.yaml` for `$(RELEASE_IMG)`, and copy `metadata.yaml` and `templates/*.yaml` next to it. |
| `release-assets` | Build every release asset for `$(VERSION)` into `out/release`. It needs the git tag. |
| `release-notes` | Write `out/release/notes.md` from the commits since the previous tag. |
| `release-github` | Create the GitHub release for `$(VERSION)` from `out/release`, marked as a pre-release for `vX.Y.Z-rc.N`. This publishes; `publish.yaml` runs it on a tag push. |
| `release-lint-snapshot` | Build the `tfcapi-lint` release assets and checksums into `dist/` as a GoReleaser snapshot, to try a release without a tag. |
| `release-lint-binaries` | An alias of `release-lint-snapshot`. |
| `release-lint` | Build the `tfcapi-lint` release assets from the current git tag. |

## Tools

| Target | Description |
| --- | --- |
| `tools` | Install every pinned tool into `hack/tools/bin`. Run it once, and again after a version bump. |
| `print-%` | A pattern rule: `make print-<VARIABLE>` prints the value of any Makefile variable, with no shell quoting. `publish.yaml` uses `print-GO_VERSION` and `print-LDFLAGS` to stamp the published image exactly as `make docker-build` does. |

## Cleanup

| Target | Description |
| --- | --- |
| `clean` | Remove the build output in `bin/` and `dist/`. This also removes `bin/testenv/`, so run `testenv-down` first if you want the cluster gone. |
