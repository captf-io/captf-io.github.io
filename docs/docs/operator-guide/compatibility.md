---
description: The versions CAPTF is built against, what the project tests, and what it only assumes.
tags:
  - Evaluators
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/git-compare
subtitle: "Supported versions and runtimes"
---

# Compatibility

This page lists the versions CAPTF is built against and what it needs from
its environment. It separates what is **tested** from what is **assumed**,
because CAPTF is pre-alpha and has been exercised only on one local kind
cluster, never on a real cloud. The numbers come from the repository at the time of writing
(`go.mod`, `metadata.yaml`, the Makefile and the noop module images), so
check them against the tag you install.

## Versions

| Component | Version | Source |
| --- | --- | --- |
| Go | 1.26 (toolchain go1.26.8) | `go.mod`, `Makefile` |
| Cluster API | v1.14.2 (the Go module the controllers build against) | `go.mod` |
| Cluster API contract | `v1beta2` | `metadata.yaml`, the CRD label |
| controller-runtime | v0.24.1 | `go.mod` |
| Kubernetes client libraries | v0.36.5 (`k8s.io/api`, `apimachinery`, `client-go`) | `go.mod` |
| CAPTF release series | 0.1 (none published) | `metadata.yaml` |
| CAPTF API and module contract | `v1alpha1`, provisional | the CRDs, [contract](../module-author/contract/README.md) |
| cert-manager | `cert-manager.io/v1` API required; no minimum release stated | [Installation](installation.md) |
| Terraform | Any 1.x with the CLI surface below; the reference modules require `>= 1.5.0` and are validated on 1.5.7 | [image contract](../module-author/image-contract.md) |
| OpenTofu | Any 1.x with the same surface; the reference modules are validated on the floor 1.6.3 (OpenTofu has no 1.5) | the same |
| Terraform in the base image | 1.16.4 | [`terraform-base`](https://github.com/captf-io/terraform-base) `Dockerfile` |
| OpenTofu in the base image | 1.12.6 (the `-minimal` image) | [`opentofu-base`](https://github.com/captf-io/opentofu-base) `Dockerfile` |
| State file format | Version 4 only | the state reader |
| Architectures | The manager image is published for `linux/amd64` and `linux/arm64` (see [Architectures](#architectures)) | `publish.yaml`, `security.yaml` |

### Architectures

The `publish` workflow pushes the manager image as a multi-architecture
image for `linux/amd64` and `linux/arm64`: `:edge` and `:sha-<commit>` on
every push to `main`, and `:vX.Y.Z` on a release tag. The Dockerfile
cross-compiles, so the `arm64` image is built without emulation. The
`security` workflow also builds both platforms on every run, without
pushing, and scans and runs the `linux/amd64` build only. An image pushed
by the manual `make release` fallback has the host platform of the machine
that ran it; see [Releasing](../developer-guide/releasing.md#manual-fallback).
The `tfcapi-lint` release assets are built per platform by GoReleaser. The
base images are published as multi-arch indexes, and the module images build
`linux/amd64` and `linux/arm64` provider mirrors.

### Kubernetes

CAPTF links the Kubernetes client libraries at v0.36, which corresponds to
Kubernetes 1.36. It does not state a supported server range. The other
bounds are Cluster API's own: the management cluster must run a Cluster API
release that implements contract `v1beta2`. Treat Kubernetes 1.36 as the
version it is built for and anything else as unverified; the features it
uses are standard (Jobs, Leases, Secrets, validating webhooks,
`SubjectAccessReview`).

### Base images and runtimes

The reference module images build `FROM` the CAPTF base images
[`terraform-base`](https://github.com/captf-io/terraform-base) (Terraform
1.16.4) and [`opentofu-base`](https://github.com/captf-io/opentofu-base)
(OpenTofu 1.12.6). Each base is Ubuntu 26.04 with `ca-certificates`, `git`
and `openssh-client`, runs as user `captf` (65532:65532), and exposes the
runtime at `/captf/runtime`. Each module Dockerfile pins its base by tag and
digest. The noop images use the same bases; they no longer pin an upstream
runtime image directly.

Every reference module declares `required_version = ">= 1.5.0"` (the noop
modules `">= 1.5"`). The cloud module repos validate each role on both
current runtimes and on the floors Terraform 1.5.7 and OpenTofu 1.6.3.
Provider versions are pinned exactly in each role's `versions.tf`:

| Module set | Provider | Pinned version |
| --- | --- | --- |
| [`aws-modules`](https://github.com/captf-io/aws-modules) | `hashicorp/aws` | 6.67.0 |
| [`azure-modules`](https://github.com/captf-io/azure-modules) | `hashicorp/azurerm` | 5.7.0 |
| [`gcp-modules`](https://github.com/captf-io/gcp-modules) | `hashicorp/google` | 8.5.0 |
| [`oci-modules`](https://github.com/captf-io/oci-modules) | `oracle/oci` | 9.8.0 |
| [`openstack-modules`](https://github.com/captf-io/openstack-modules) | `terraform-provider-openstack/openstack` | 3.4.0 |
| [`noop-modules`](https://github.com/captf-io/noop-modules) | none (`terraform_data` only) | n/a |

OpenStack has no `machinepool` role. The pins move with the module repos, so
read the `versions.tf` of the tag you use.

### The runtime CLI

The module image supplies the `terraform` or `tofu` binary at
`/captf/runtime`. CAPTF needs the 1.x CLI surface `version`, `init`,
`validate`, `plan`, `apply`, `destroy`, `force-unlock`, `show` and `state
push`/`state list`. It does not check a minimum version. The reference
modules declare `required_version = ">= 1.5.0"`, because they use
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

### The tested combination

One combination is exercised, by the opt-in end-to-end suites on a local
kind cluster. The versions are pinned in `test/framework/versions.go` and
the Makefile of the provider:

| Component | Version |
| --- | --- |
| kind | v0.33.0 |
| Kubernetes (kind node image, by digest) | v1.36.4 |
| Cluster API (core, kubeadm bootstrap, kubeadm control plane) | v1.14.2 |
| cert-manager | v1.21.1 |
| `clusterctl` (Makefile pin) | v1.14.2 |
| Runtimes in the noop images | Terraform 1.16.4, OpenTofu 1.12.6 |

This is the only matrix that has run. Use a `clusterctl` whose version
matches the Cluster API version in `go.mod` (v1.14.2). Anything else is
unverified.

### Continuous integration

The continuous-integration workflow runs these on every push:

| Check | Covers |
| --- | --- |
| `make test-cover` and `make cover-check` | Unit tests of the controllers, runner, webhooks, linter and libraries, against fake clients, with per-package coverage floors |
| `make lint` and `make vet` | Go lint, API lint, and `go vet`, including the e2e-tagged test code |
| The `verify` targets | Generated files are current, component manifests, templates, JSON schemas, `metadata.yaml` append-only, the local clusterctl repository layout, licenses and the Prometheus rules (`promtool` check and tests) |

The workflow also builds every binary and takes a `tfcapi-lint` release
snapshot. It does not run the end-to-end suites. They are opt-in: you run
them yourself with `make e2e-foundation` and then `make e2e-noop`. The docs
checks and the release flow are also outside the workflow.

### End-to-end suites

The provider's `test/README.md` records two suites, run on a kind cluster on
rootless podman, with measurements dated 2026-10-04:

- **`make e2e-foundation`** brings up the cluster, runs `clusterctl init`
  with Cluster API core, the kubeadm bootstrap and control-plane providers,
  and CAPTF built from the working tree, and checks the components, a real
  reconcile of a `TerraformClusterIdentity`, and a stability window.
- **`make e2e-noop`** drives the published noop module images through real
  Cluster API objects, with Terraform and OpenTofu: a cluster, two machines
  and a machine pool, a scale, a drift check, a failed and a recovered apply,
  digest pinning, and deletion with a full cleanup of Secrets and Jobs.

## What is assumed

!!! warning "Beyond the suites above, nothing has been exercised"

    Treat every item in this list as unverified.

- **Anything but the tested combination.** Other Kubernetes server versions,
  cert-manager releases and Cluster API releases.
- **A management cluster that is not a single-node kind cluster.**
- **`clusterctl upgrade` and `clusterctl move`.** No suite runs either. The
  move behavior is derived from the code and `clusterctl`'s documented rules.
- **Real infrastructure providers.** The noop modules create no cloud
  resources, and no module that does has been run under CAPTF.
- **Real Terraform or OpenTofu execution against a cloud.** The noop modules
  run the real runtimes, but only the pinned ones. Other versions are assumed
  to behave.
- **The `arm64` image.** CI builds and publishes it but does not run it.
- **KubeadmControlPlane and RKE2ControlPlane integration.** The kubeadm
  providers are installed in the e2e cluster, but the suites create clusters
  with no control plane. The integration is documented against the providers'
  contracts and has not run.
- **The Docker engine path of the test environment.** Only podman has run.

If you find a version that works or does not, that is the information this
page needs. See [Known Limitations](limitations.md) and the [project
status](../index.md#project-status).

!!! related "See also"

    - [Installation](installation.md) and [Upgrades](upgrades.md).
    - [Testing](../developer-guide/testing.md) for how the suite is organized.
    - [Supporting Terraform and OpenTofu](../module-author/repository-layout.md#supporting-terraform-and-opentofu)
      for the runtime floors a module set validates on.
    - [Production Readiness](production-readiness.md).
