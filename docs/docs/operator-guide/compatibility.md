---
description: The versions CAPTF is built against, what the project tests, and what it only assumes.
tags:
  - Evaluators
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "Steven Crothers"
icon: lucide/git-compare
subtitle: "Supported versions and runtimes"
---

# Compatibility

This page lists the versions CAPTF is built against and what it needs from
its environment. It separates what is **tested** from what is **assumed**,
because CAPTF is pre-alpha and has never run against a live management
cluster. The numbers come from the repository at the time of writing
(`go.mod`, `metadata.yaml`, the Makefile and the noop module images), so
check them against the tag you install.

## Versions

| Component | Version | Source |
| --- | --- | --- |
| Go | 1.26 (toolchain go1.26.8) | `go.mod`, `Makefile` |
| Cluster API | v1.14.2 (the Go module the controllers build against) | `go.mod` |
| Cluster API contract | `v1beta2` | `metadata.yaml`, the CRD label |
| controller-runtime | v0.24.1 | `go.mod` |
| Kubernetes client libraries | v0.36.3 (`k8s.io/api`, `apimachinery`, `client-go`) | `go.mod` |
| CAPTF release series | 0.1 (none published) | `metadata.yaml` |
| CAPTF API and module contract | `v1alpha1`, provisional | the CRDs, [contract](../module-author/contract/README.md) |
| cert-manager | `cert-manager.io/v1` API required; no minimum release stated | [Installation](installation.md) |
| Terraform | Any 1.x with the CLI surface below; modules require `>= 1.5` | [image contract](../module-author/image-contract.md) |
| OpenTofu | Any 1.x with the same surface; modules require `>= 1.5` | the same |
| Terraform in the noop images | 1.16.4, pinned by digest | [`noop-modules`](https://github.com/captf-io/noop-modules) `Dockerfile.terraform` |
| OpenTofu in the noop images | 1.12.6, pinned by digest | [`noop-modules`](https://github.com/captf-io/noop-modules) `Dockerfile.opentofu` |
| State file format | Version 4 only | the state reader |
| Architectures | `linux/amd64` and `linux/arm64` image builds | the Makefile's `PLATFORMS` |

### Kubernetes

CAPTF links the Kubernetes client libraries at v0.36, which corresponds to
Kubernetes 1.36. It does not state a supported server range. The other
bounds are Cluster API's own: the management cluster must run a Cluster API
release that implements contract `v1beta2`. Treat Kubernetes 1.36 as the
version it is built for and anything else as unverified; the features it
uses are standard (Jobs, Leases, Secrets, validating webhooks,
`SubjectAccessReview`).

### The runtime CLI

The module image supplies the `terraform` or `tofu` binary at
`/captf/runtime`. CAPTF needs the 1.x CLI surface `version`, `init`,
`validate`, `plan`, `apply`, `destroy`, `force-unlock`, `show` and `state
push`/`state list`. It does not check a minimum version. The reference
modules declare `required_version = ">= 1.5"`, because they use
`terraform_data` and `plantimestamp()`. CAPTF reads the state through
the Kubernetes backend and only accepts state file version 4. OpenTofu
client-side state encryption is unsupported. See [Image
Contract](../module-author/image-contract.md) and [Runtime
Environment](../module-author/runtime-environment.md).

### Cluster API providers

CAPTF is an infrastructure provider. Pairing it with a control-plane and
bootstrap provider is covered by [Control-Plane
Integration](../module-author/control-planes/README.md): KubeadmControlPlane
and RKE2ControlPlane are the documented ones. That documentation is derived
from those providers' contracts, not from a live run.

## What is tested

The continuous-integration workflow runs these on every push:

| Check | Covers |
| --- | --- |
| `make test-cover` and `make cover-check` | Unit tests of the controllers, runner, webhooks, linter and libraries, against fake clients, with per-package coverage floors |
| `make lint` and `make vet` | Go lint, API lint, and `go vet`, including the e2e-tagged test code |
| The `verify` targets | Generated files are current, component manifests, templates, JSON schemas, `metadata.yaml` append-only, the local clusterctl repository layout, licenses and the Prometheus rules (`promtool` check and tests) |

The workflow also builds every binary and takes a `tfcapi-lint` release
snapshot. It does not run the end-to-end suites: `make e2e-foundation` and
`make e2e-noop` run them on a local kind cluster that pulls the published
no-op images, and you run them yourself. The docs checks and the release
flow are also outside the workflow.

## What is assumed

!!! warning "Nothing below has been exercised against a live system"

    Treat every item in this list as unverified.

- **A real management cluster.** No `clusterctl init`, `upgrade` or `move`
  has run end to end; the move behavior is derived from the code and
  `clusterctl`'s documented rules.
- **Real Terraform or OpenTofu execution under CAPTF.** The runner is unit
  tested against recorded plan and state JSON. Other versions of the runtime
  than the pinned noop ones are assumed to behave.
- **Real infrastructure providers.** The noop modules create no cloud
  resources, and no module that does has been run under CAPTF in CI.
- **Kubernetes server versions other than 1.36, cert-manager releases, and
  Cluster API releases other than the one built against.**
- **The `arm64` image.** It is built by the Makefile; no CI job runs it.
- **KubeadmControlPlane and RKE2ControlPlane integration.** Documented
  against their contracts; not run.

If you find a version that works or does not, that is the information this
page needs. See [Known Limitations](limitations.md) and the [project
status](../index.md#project-status).

!!! related "See also"

    - [Installation](installation.md) and [Upgrades](upgrades.md).
    - [Testing](../developer-guide/testing.md) for how the suite is organized.
    - [Production Readiness](production-readiness.md).
