---
title: "Testing the CAPTF Provider"
description: "What make test runs, the unit, envtest and e2e tiers, coverage floors, golden files, the test environment, and how to run one package or one test."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "September 29, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-09-29"
authors:
  - "The CAPTF Authors"
icon: lucide/flask-conical
subtitle: "Run unit and cluster tests"
---

# Testing

This page describes CAPTF's test suite: what `make test` runs, its tiers,
the envtest tier, the end-to-end test environment, coverage floors, golden files, and running
less than the whole suite.

## Running the tests

`make test` runs `go test -race -count=1 ./...` in every module (`.`, `api`
and `test`). That is the unit tier, and nothing it runs creates a
Kubernetes cluster, calls a real cloud API, or invokes `terraform` or
`tofu`.

- Controllers and webhooks run against the controller-runtime fake client,
  never a real API server. Behavior the fake client cannot show (CEL rules,
  the admission chain, write conflicts) is covered by the separate
  [envtest tier](#the-envtest-tier), which `make test` does not run.
- Job execution is faked the same way: a reconciler test asserts on the
  `batch/v1.Job` CAPTF would create, and a runner test drives the runner's
  own logic directly, without a pod ever starting.
- `internal/state`, `internal/outputs` and `internal/locks` instead read
  real `kubernetes`-backend state:
  [`internal/state/testdata/fixtures`](https://github.com/captf-io/cluster-api-provider-terraform/blob/main/internal/state/testdata/fixtures/README.md)
  holds state Secrets and lock Leases captured once from real Terraform and
  OpenTofu runs, checked in as frozen data. Regenerating them needs a
  capture setup that does not exist in this repository; treat those files
  as read-only.
- `go test ./templates/` decodes every shipped `templates/*.yaml` object
  strictly into its API type and checks the values `hack/verify-templates.sh`
  renders; it also runs CAPI's own `ClusterClass` admission webhook and
  topology generator, applying the class patches, against
  `clusterclass-noop.yaml`.
- The packages under `test/framework` (kind, images, providers, waits,
  diagnostics) are unit-tested with fakes. They never start a process or
  touch `podman`.

## Test tiers

| Tier | What | How it runs |
| --- | --- | --- |
| Unit | Everything above, including reconcilers driven through several packages at once against the fake client, such as `internal/controllers/shared`'s `TestBringUpJobCount`, which reconciles a whole cluster bring-up and asserts the resulting Job count. | `make test`, `make test-cover` and CI, always. |
| Envtest | `internal/envtest/`, build tag `envtest`: the CRDs' CEL rules, the admission chain and write conflicts against a real kube-apiserver and etcd, with no kubelet and no controllers. | `make test-envtest` and the CI `envtest` job. |
| E2E | `test/e2e/...` and `test/env/lifecycle`, against a real kind cluster on `podman` or `docker`. | Only through the `testenv-*` and `e2e-*` targets, or `go test -tags=e2e` with `-run`. CI does not run them yet. |

Three guards keep the tiers apart:

- **The build tag.** Every Go file under `test/e2e/` and
  `test/env/lifecycle/` starts with `//go:build e2e`, and every one under
  `internal/envtest/` with `//go:build envtest`, so `go test ./...`
  never compiles them. `make verify-test-tiers` (part of `make verify`, and
  of CI) guards both tiers: it fails if a file in those directories lacks
  its tag, or if any other Go file uses it.
  `hack/verify-test-tiers_test.sh` tests that script against fixtures; it
  is not part of `make test`, and `verify-test-tiers` runs it first.
- **`-run`.** Each e2e package's `TestMain` refuses to run unless `-run`
  selects a test, so a bare `go test -tags=e2e ./...` does nothing.
- **Compiled without running.** `make vet` and `make lint` add a
  `-tags envtest` pass over `internal/envtest` and a `-tags e2e` pass over the
  `test` module, so tagged code cannot rot unnoticed.

Besides `go test`, two `make verify` checks exercise the release assets
without a real cloud: `make verify-templates` renders `templates/` with the
pinned `clusterctl`, and `make verify-local-repository` runs `clusterctl
generate provider` and `generate cluster` against a local repository of
the release assets, offline. `hack/check-metadata_test.sh` and
`hack/version_test.sh` test `hack/check-metadata.sh` and `hack/version.sh`
against fixtures under `hack/testdata`; `make verify-metadata` and `make
verify-version` run them before the check itself.

## The envtest tier

`make test-envtest` runs the suite in `internal/envtest/` (build tag
`envtest`, with `-race`) against a real kube-apiserver and etcd. It lives in the
root module, not `test/`, because it needs `internal/` packages. It takes
about half a minute and needs no container engine.

- `setup-envtest` (pinned in `hack/tools/versions.mk`, v0.24.1) downloads
  kube-apiserver and etcd for `ENVTEST_K8S_VERSION` (1.36.2) into
  `bin/envtest`. A CI cache keyed on `hack/tools/versions.mk` keeps them
  between runs.
- The suite starts three API servers: one with the CRDs only, one with the
  CRDs and the real webhooks, and a second webhook server that one test
  stops, to check the fail-open and fail-closed behavior.
- There is no kubelet and no controller manager. Reconciles are driven by
  hand, and minimal Cluster API `Machine` and `Cluster` CRDs in
  `internal/envtest/testdata/crds/` stand in for the real ones.
- It checks what the fake client cannot: the CEL rules on the CRDs answer with
  a real `422 Invalid` (and answer before the webhooks), the webhook chain
  denies as expected, and optimistic-lock conflicts (a finalizer or annotation
  removal against a concurrent writer) come back as `Conflict`.

## End-to-end tests

The e2e tier needs `podman` or `docker`, and network access on the first
run to download the pinned kind, Cluster API and cert-manager assets. Every
version and image is pinned in `test/framework/versions.go`. The suites run
the pinned noop images; to test your own module images end to end, see
[Testing a Module](../module-author/testing.md#end-to-end).

### The test environment

`make testenv-up` builds the manager image from your working tree and
brings up a kind cluster with cert-manager, Cluster API (core, kubeadm
bootstrap and kubeadm control plane) and CAPTF. It takes about 6 minutes
cold and about 15 seconds when it reuses a cluster. Work in a loop:

```sh
make testenv-up
source bin/testenv/captf-test-dev/env.sh
kubectl get pods -A
make testenv-reload
make testenv-logs
make testenv-down
```

`env.sh` points `KUBECONFIG` at the test cluster. `testenv-reload`
rebuilds the image and rolls the manager over to it; `testenv-logs` writes
a diagnostics bundle without Secrets; `testenv-down` deletes the cluster and
keeps the artifacts. Everything for a cluster lives in
`bin/testenv/<name>/`. [Make Targets](../reference/make-targets.md#test-environment)
lists the targets and their variables.

The environment is built so it cannot touch anything else on your host:

- Cluster names must start with `captf-test-`, and `testenv-down` only ever
  deletes such clusters.
- The nodes join a dedicated `captf-test` network, not kind's default one.
- It never reads `~/.kube/config`; every child process gets the cluster's
  own kubeconfig.
- It never changes host sysctls or limits, and it never deletes a cluster
  implicitly: `testenv-up` refuses an existing one unless
  `CAPTF_TESTENV_REUSE=1`.

### The e2e suites

| Target | Suite | What it proves |
| --- | --- | --- |
| `make e2e-foundation` | `TestFoundation` in `test/e2e/foundation` | In six ordered stages, a failed one stopping the run: the `captf-test-e2e` cluster builds, the base components and the CAPTF install are healthy, a real reconcile of a `TerraformClusterIdentity` works and the cluster holds still for a stability window, then a green light is written. |
| `make e2e-noop` | `TestNoop` in `test/e2e/noop` | The published no-op modules, driven through real Cluster API objects, move data end to end with no cloud: the CAPI spec into the module inputs, the outputs into CAPTF status and on into CAPI, the cluster's exports into the machine and pool inputs, the pinned digests into every later Job, and deletion into a full cleanup. |
| `make e2e-down` | | Deletes the e2e cluster; the artifacts are kept. |

Run `e2e-foundation` first. `e2e-noop` fails at once, and never skips,
unless the foundation suite's green light is still valid: the cluster
exists, its pins and manager image match this build, every stage passed,
and the light is younger than `CAPTF_E2E_GREENLIGHT_MAX_AGE` (24 hours by
default). The foundation suite keeps a passing cluster for later tests
unless `CAPTF_E2E_TEARDOWN=1`, and on failure it keeps the cluster too and
writes a diagnostics bundle into `bin/testenv/<name>/artifacts/`. Each
`e2e-noop` run uses a fresh namespace `e2e-noop-<suffix>` and removes what
it created. Set `CAPTF_E2E_NOOP_BAD_DIGEST=1` to run its negative check
instead, in which one machine gets a nonexistent image digest and the
suite must fail on the image pull.

`test/README.md` in the provider repository has the full stage-by-stage
description, the variables and the allowlists of known-benign log lines.

## Coverage

`make test-cover` runs the unit tests with `-race` and
`-covermode=atomic` through `gotestsum`, and writes a profile and a JUnit
report per module into `bin/`. `make cover-check` then reads the profiles
and fails when a package falls below its floor in
`hack/coverage-floors.txt` (the checker is `hack/covercheck`). CI runs both
and writes the per-package table to the job summary.

```sh
make test-cover
make cover-check
go tool cover -html=bin/cover-root.out -o bin/cover.html
```

The floors are a ratchet, set per package:

- A `default` line sets the floor for every package without its own line,
  currently 80 percent.
- A `<package> <percent>` line sets one package's floor. Packages are import
  paths relative to the module path.
- A `<package> exempt` line reports a package but never gates it. Each
  entry carries its reason in a comment; the `cmd/*` packages are exempt
  because the logic they call lives in their `app` packages.

When a package's coverage rises, raise its floor in the same change. Never
lower a floor or add an exemption without a reason on the line.

## Golden files

Several packages pin an exact rendered output as a checked-in file and
compare against it on every run, rather than asserting field by field:

| Package | What it pins |
| --- | --- |
| `internal/contract` | The rendered JSON of fully populated contract inputs. |
| `internal/jobs` | The `batch/v1.Job` of every operation, as YAML. |
| `internal/outputs` | Rendered output fixtures. |
| `internal/render` | The generated root module. |
| `cmd/tfcapi-lint` | Its `--json` output. |

Run the affected test with `UPDATE_SNAPSHOTS=1` to rewrite its golden files.
`make verify-schemas` also validates the golden inputs and outputs of
`internal/contract` and `internal/outputs` against the contract schemas.

!!! warning "Read the diff before committing a rewrite"

    Read the diff before committing it: a passing rewrite is not the same as
    a correct one.

## Running one package, or one test

```sh
go test -race ./internal/jobs/...
go test -race -run TestGoldenJobs ./internal/jobs/...
UPDATE_SNAPSHOTS=1 go test ./internal/jobs/... -run TestGoldenJobs
```

`go.work` makes the `api` module's tests reachable from the repository
root too: `go test ./api/...` needs no `cd`. The `test` module's unit tests
run from its own directory: `cd test && go test ./framework/...`.

!!! related "See also"

    - [Contributing](contributing.md)
    - [Writing Documentation](documentation.md)
    - [Releasing](releasing.md)
