---
description: "Build, lint, test and verify CAPTF itself: repository layout, prerequisites, conventions and running the manager against a real cluster."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "September 29, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-09-29"
authors:
  - "The CAPTF Authors"
icon: lucide/git-pull-request
subtitle: "Set up, build and send a change"
---

# Contributing

This page is for anyone changing CAPTF itself: the repository layout, the
prerequisites, the build/lint/test/verify loop, the conventions the checks
enforce, and running the manager against a real cluster.

## Repository layout

| Path | Holds |
| --- | --- |
| `api/` | The `v1alpha1` Go types: its own module in `go.work`, so the CRD types carry no dependency on controller-runtime or the manager. |
| `cmd/manager`, `cmd/runner`, `cmd/tfcapi-lint` | The three binaries. Each has an `app` package with its wiring and an `app/options` or equivalent for flags, so `main.go` stays a thin entry point. |
| `internal/` | Everything the binaries share, one package per concern: `controllers` (one subpackage per reconciled kind, plus `shared` for the common reconcile flow and `sweep` for the orphan RBAC sweep), `jobs`, `runner`, `state`, `identity`, `rbac`, `runlease`, `inputs`, `render`, `outputs`, `locks`, `conditions`, `contract`, `hash`, `ownership`, `plankey`, `webhooks`, `lint`, `feature`, `imageinspect`, `manager`, `metrics`, `strutil`. |
| `config/` | Kustomize bases: `crd`, `rbac`, `webhook`, `manager`, `certmanager`, assembled by `default`; `network-policy` and `prometheus` are separate optional overlays, and `samples` holds example custom resources. |
| `templates/` | The `clusterctl generate` templates and flavors, and the Go tests that decode them. |
| `hack/` | Build and verify tooling: pinned tool installers under `hack/tools`, the `verify-*.sh`/`check-*.sh` scripts `make verify` runs, `hack/godoccheck`, `hack/covercheck` with its per-package floors in `hack/coverage-floors.txt`, and the dev scripts behind `make run`. |
| `test/` | A third module in `go.work` for the e2e-tagged test environment and suites: `framework/` (kind, images, providers and diagnostics, unit-tested with fakes), `env/lifecycle/` (the `testenv-*` operations) and `e2e/` (the foundation and no-op suites). See [Testing](testing.md). |
| `internal/*/testdata` | Golden files and frozen fixtures that unit tests read, such as real captured Terraform and OpenTofu state under `internal/state/testdata/fixtures`. |

The no-op demo modules are not in this repository: they live in
the per-role `terraform-<provider>-<role>` repositories, for example
[captf-io/terraform-noop-cluster](https://github.com/captf-io/terraform-noop-cluster),
which publish to the Terraform Registry. Their gate is `make verify`.
[captf-io/module-images](https://github.com/captf-io/module-images) builds the
images from the released modules. See [Repositories
and Images](../reference/repositories.md#terraform-module-repositories).

The documentation lives in a separate repository,
[captf-io/captf-io.github.io](https://github.com/captf-io/captf-io.github.io),
with the rest of captf.io, published at
[https://captf.io/docs/](https://captf.io/docs/); see
[Writing Documentation](documentation.md).

Each Go module (`.`, `api` and `test`) is listed in `go.work`. `hack/verify-modules.sh`
(`make verify`) checks that none carries a `replace` directive, except the
root module's `api => ./api` (which tools that ignore `go.work` need), and that
they agree on the Kubernetes and controller-runtime versions they share.
Because `api` only exists inside the workspace, `go mod tidy` run from the
repository root does not update its `go.mod`; add or bump one of its
dependencies by editing `api/go.mod`'s `require` block directly, then run
`go mod tidy` inside `api/` with `GOWORK=off`.

!!! info "Before you begin"

    - Go, matching the version `go.work` declares, `make`, `git`, `jq` and `curl`.
    - `podman` (the default `CONTAINER_TOOL`) or `docker`, to build images.
    - `python3`, with the `jsonschema` and `PyYAML` packages, for
      `make verify-schemas`, `make verify-metadata`, `make promtool-check`,
      `make promtool-test` and `make release-assets`.
    - `podman` or `docker`, running, for the [test
      environment](testing.md#end-to-end-tests) (`make testenv-up` and the
      `e2e-*` targets).

Everything else — `controller-gen`, `kustomize`, `golangci-lint` (plus its
kube-api-linter build), `clusterctl`, `promtool`, `goreleaser`, `goimports` and
`gotestsum` — is a pinned binary `make` downloads for you.

## The build, lint, test and verify loop

1. Install the pinned tools once: `make tools`. Each lands in
   `hack/tools/bin` as `<name>-<version>`, plus an unversioned symlink;
   bumping a version in the `Makefile` re-downloads it.
2. After changing `api/v1alpha1` or a controller's markers, regenerate the
   deepcopy code and the CRD/RBAC/webhook manifests: `make generate
   manifests`. `make verify-gen` (part of `make verify`) fails if either is
   stale.
3. Format and lint: `make fmt lint`. `fmt` runs `gofmt -s` and `goimports
   -local github.com/captf-io/cluster-api-provider-terraform`; `lint` runs
   `golangci-lint` (`.golangci.yml`) in every module, then kube-api-linter
   (`.golangci-kal.yml`) on `api/`. `lint` and `vet` also check the `test`
   module's e2e-tagged code. `make lint-fix` reruns both linters with
   their auto-fixers.
4. Run the unit tests: `make test`. See
   [Testing](testing.md) for what it covers and how to run less than
   everything. CI runs `make test-cover` and `make cover-check` instead,
   which also enforce a coverage floor per package.
5. Before sending a change, run `make verify`: every check listed in
   [Make Targets](../reference/make-targets.md#verify), including that
   generated code is current and that e2e code stays out of the default
   test run. A change to
   anything the documentation's reference pages describe (a flag,
   a condition, an event, a metric, an annotation, a field of a kind) also
   needs that page updated in `captf-io/captf-io.github.io`: see
   [Reference pages](documentation.md#reference-pages).
6. `make build` compiles every `cmd/*` binary to `bin/`; never to the
   repository root. To see a change work, run the manager against a
   cluster: see [Running the manager](#running-the-manager).

The full target list, grouped the same way, is in
[Make Targets](../reference/make-targets.md).

## Conventions

- **Commits**: an imperative subject in `<subsystem>: <summary>` form, such
    as `runner: name the exit codes` — check `git log` for the subsystem names already in use.
- **License header**: every source file carries the full Apache-2.0 header
    with the copyright line "Copyright <year> The CAPTF Authors."
    `make check-headers` fails on a file without it and is part of
    `make verify`; CI runs it in the `license-headers` job, so it needs a
    container engine (`CONTAINER_TOOL`). `make fix-headers` adds the header to
    every file missing it. `.licenserc.yaml` defines the header and lists the
    files that are exempt. `hack/boilerplate.go.txt` is the header
    `controller-gen` writes on `api/v1alpha1/zz_generated.deepcopy.go`.
- **Documentation comments**: `hack/godoccheck` (`make verify-godoc`, part of
    `make verify`) enforces one rule per declaration and one per package,
    everywhere except generated files and `hack/tools`:
    - Every function, method and type has a doc comment starting with its
      name; every interface method and top-level `const` or `var` group
      needs only a doc comment, not one starting with its name.
    - Every named parameter is mentioned by name in that comment. Receivers,
      parameters named `_`, and a `Test`/`Benchmark`/`Fuzz` function's
      conventional `*testing.T`/`*testing.B`/`*testing.F` parameter are exempt.
    - A function or method that returns anything says what it returns, using
      "return", "returns", "returned" or "reports".
    - Every non-generated, non-external-test package has a `doc.go` whose
      package comment is a real overview of at least 400 characters.
- **Generated code**: `zz_generated.deepcopy.go` and the CRD/RBAC/webhook
    manifests come from `make generate manifests`. Never hand-edit a
    generated file: `make verify-gen` fails when the deepcopy code or the
    manifests no longer match their source. The documentation's reference
    pages are written by hand (see
    [Reference pages](documentation.md#reference-pages)).
- **Test tiers**: code that needs a real cluster carries the `e2e` build
    tag and lives only in `test/e2e/` or `test/env/lifecycle/`;
    `make verify-test-tiers` fails otherwise. See [Testing](testing.md).
- **Coverage**: a package's coverage must not fall below its floor in
    `hack/coverage-floors.txt`. When a package's coverage rises, raise its
    floor in the same change; never lower one without a reason on its line.

## Common changes

Each change below also needs its reference page in
`captf-io/captf-io.github.io`
updated by hand, in the same change; run `tools/check_reference.py` there,
with `--provider` pointed at this checkout, to list any name a page is
missing (see
[Reference pages](documentation.md#reference-pages)).

- **Adding a manager flag**: register it in `cmd/manager/app/options/options.go`,
    then document it in [Manager Flags](../reference/manager-flags.md).
- **Adding a condition reason**: condition types, their reasons and each
    reason's doc comment live in `api/v1alpha1/conditions_consts.go`;
    `ConditionReasons` returns the full type-to-reason table, and every
    reason constant must be in it. A reason is set from
    `internal/conditions` when it applies across controllers, or from
    `internal/controllers/shared` when it belongs to one reconcile flow.
    Afterward, run `make generate manifests` to regenerate the CRD schema
    and the deepcopy code, and document the reason in
    [Conditions](../reference/conditions.md). `make verify-gen` and
    `make test` fail until the generated files and the reason table are
    complete.

    An event reason follows the same shape: it lives in
    `internal/controllers/shared/events.go`, or `internal/runner/events.go`
    for a runner event, with a doc comment. Document it in
    [Events](../reference/events.md). A `tfcapi-lint` check ID in
    `internal/lint` needs a doc comment too, and an entry in
    [tfcapi-lint CLI](../reference/tfcapi-lint-cli.md#checks).

## Running the manager

There are two ways to run the manager you are changing. Both need a
cluster that has the CAPTF CRDs, cert-manager and Cluster API.

- **The test environment** is the closest to a real install. `make
  testenv-up` builds the manager image from your tree, creates a kind
  cluster and installs cert-manager, Cluster API and CAPTF. After a change,
  `make testenv-reload` rebuilds the image and rolls the manager
  Deployment over to it. `make testenv-logs` collects diagnostics and
  `make testenv-down` deletes the cluster. The same image is the runner
  image, so a change under `internal/runner` or `cmd/runner` reaches Jobs
  on the next reload.
- **`make run`** builds `bin/manager` and runs it on your machine against
  the cluster in your current `kubeconfig`, with leader election off and a
  self-signed webhook certificate in `bin/dev-webhook-certs`. It is quick,
  but the Jobs it creates run the image in `RUNNER_IMAGE` (default `IMG`),
  not your working tree: run `make docker-build` and make that image
  available to the cluster first when you change the runner. Pass extra
  manager flags with `ARGS`.

!!! warning "Point `make run` at a cluster you can break"

    `make run` uses whatever cluster your current `kubeconfig` context
    names. The test environment never reads `~/.kube/config`; it writes its
    own `bin/testenv/<name>/kubeconfig` and an `env.sh` that exports it.

!!! related "See also"

    - [Testing](testing.md)
    - [Releasing](releasing.md)
    - [Working Across Repositories](cross-repo.md) for a change that spans
      more than one repository.
    - [Writing Documentation](documentation.md), [Contributing to the
      Docs](docs-workflow.md) and [Updating the Website](website.md) for
      changes to captf.io itself.
