---
title: "CAPTF Cloud Reference Modules"
description: "Reference Terraform and OpenTofu module sets for AWS, Google Cloud, Azure, OCI and OpenStack, and a no-op set, with their images, tags and conventions."
status: new
tags:
  - Cloud modules
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/cloud
subtitle: "Five clouds and a no-op set"
---

# Cloud Modules

The CAPTF project maintains reference modules for five clouds: AWS, Google
Cloud, Azure, Oracle Cloud Infrastructure (OCI) and OpenStack. Each set
has one repository for each role, implements the
[v1alpha1 module contract](../module-author/contract/v1alpha1/README.md)
and ships as module images you reference from a `TerraformCluster`,
`TerraformMachineTemplate` or `TerraformMachinePool`. They are meant to be
used as they are, and to be forked as the starting point for your own
modules.

A sixth set, [No-op](noop/README.md), provisions nothing: it runs real
plans and keeps real state with no cloud and no credentials, for trying
CAPTF and testing a management cluster.

!!! warning "Status: pre-release"

    The five cloud sets pass static analysis, mocked unit
    tests on Terraform and OpenTofu, and image smoke tests, but none has yet
    been applied to a real cloud. Each role repository's `DESIGN.md` lists the
    facts the first real apply must confirm. Read it before you rely on a
    module, and pin a release tag. Images are signed with cosign: see
    [verifying a signature](../module-author/releasing.md#what-ci-publishes).

## The modules

<div class="grid cards" markdown>

-   :fontawesome-brands-aws:{ .lg .middle } __AWS__

    ---

    Network Load Balancer, security groups, IAM roles and an S3 bootstrap bucket; EC2 instances and Auto Scaling groups.

    [:octicons-arrow-right-24: AWS](aws/README.md)

-   :fontawesome-brands-google:{ .lg .middle } __Google Cloud__

    ---

    Proxy Network Load Balancer, firewall rules and service accounts; Shielded VMs and managed instance groups.

    [:octicons-arrow-right-24: Google Cloud](gcp/README.md)

-   :fontawesome-brands-microsoft:{ .lg .middle } __Azure__

    ---

    Standard load balancer, network security groups and a resource group; VMs and scale sets.

    [:octicons-arrow-right-24: Azure](azure/README.md)

-   :material-cloud-outline:{ .lg .middle } __OCI__

    ---

    Network security groups, a network load balancer and a dynamic group; compute instances and instance pools.

    [:octicons-arrow-right-24: OCI](oci/README.md)

-   :material-layers-triple-outline:{ .lg .middle } __OpenStack__

    ---

    Octavia load balancer, security groups and a server group; Nova servers. No machinepool role.

    [:octicons-arrow-right-24: OpenStack](openstack/README.md)

-   :material-flask-outline:{ .lg .middle } __No-op__

    ---

    Real plans, state and outputs with nothing provisioned: try CAPTF or test a management cluster without a cloud.

    [:octicons-arrow-right-24: No-op](noop/README.md)

-   :material-source-merge:{ .lg .middle } __Shared Behavior__

    ---

    What all five sets have in common: endpoint, traffic, identities, bootstrap data, health, tags and destroy.

    [:octicons-arrow-right-24: Shared Behavior](shared-behavior.md)

</div>

| Cloud | Images | Roles | Provider |
| --- | --- | --- | --- |
| [AWS](aws/README.md) | [`captf-io/module-images`](https://github.com/captf-io/module-images) | cluster, machine, machinepool | `hashicorp/aws` 6.67.0 |
| [Google Cloud](gcp/README.md) | [`captf-io/module-images`](https://github.com/captf-io/module-images) | cluster, machine, machinepool | `hashicorp/google` 8.5.0 |
| [Azure](azure/README.md) | [`captf-io/module-images`](https://github.com/captf-io/module-images) | cluster, machine, machinepool | `hashicorp/azurerm` 5.7.0 |
| [OCI](oci/README.md) | [`captf-io/module-images`](https://github.com/captf-io/module-images) | cluster, machine, machinepool | `oracle/oci` 9.8.0 |
| [OpenStack](openstack/README.md) | [`captf-io/module-images`](https://github.com/captf-io/module-images) | cluster, machine | `terraform-provider-openstack/openstack` 3.4.0 |
| [No-op](noop/README.md) | [`captf-io/module-images`](https://github.com/captf-io/module-images) | cluster, machine, machinepool | None: `terraform_data` is built in |

All the images are built by one repository,
[`captf-io/module-images`](https://github.com/captf-io/module-images), which
holds no module code. The code of each role lives in its own repository,
`captf-io/terraform-<provider>-<role>`, and is published on the Terraform
Registry as `captf-io/<role>/<provider>`, for example
[`captf-io/cluster/aws`](https://registry.terraform.io/modules/captf-io/cluster/aws).
The provider is `aws`, `azure`, `google`, `oci`, `openstack` or `noop`; the
images and the cloud pages keep the name `gcp` for Google Cloud.

| Cloud | Role repositories | Registry addresses |
| --- | --- | --- |
| AWS | [`terraform-aws-cluster`](https://github.com/captf-io/terraform-aws-cluster), [`-machine`](https://github.com/captf-io/terraform-aws-machine), [`-machinepool`](https://github.com/captf-io/terraform-aws-machinepool) | `captf-io/cluster/aws`, `captf-io/machine/aws`, `captf-io/machinepool/aws` |
| Google Cloud | [`terraform-google-cluster`](https://github.com/captf-io/terraform-google-cluster), [`-machine`](https://github.com/captf-io/terraform-google-machine), [`-machinepool`](https://github.com/captf-io/terraform-google-machinepool) | `captf-io/cluster/google`, `captf-io/machine/google`, `captf-io/machinepool/google` |
| Azure | [`terraform-azure-cluster`](https://github.com/captf-io/terraform-azure-cluster), [`-machine`](https://github.com/captf-io/terraform-azure-machine), [`-machinepool`](https://github.com/captf-io/terraform-azure-machinepool) | `captf-io/cluster/azure`, `captf-io/machine/azure`, `captf-io/machinepool/azure` |
| OCI | [`terraform-oci-cluster`](https://github.com/captf-io/terraform-oci-cluster), [`-machine`](https://github.com/captf-io/terraform-oci-machine), [`-machinepool`](https://github.com/captf-io/terraform-oci-machinepool) | `captf-io/cluster/oci`, `captf-io/machine/oci`, `captf-io/machinepool/oci` |
| OpenStack | [`terraform-openstack-cluster`](https://github.com/captf-io/terraform-openstack-cluster), [`-machine`](https://github.com/captf-io/terraform-openstack-machine) | `captf-io/cluster/openstack`, `captf-io/machine/openstack` |
| No-op | [`terraform-noop-cluster`](https://github.com/captf-io/terraform-noop-cluster), [`-machine`](https://github.com/captf-io/terraform-noop-machine), [`-machinepool`](https://github.com/captf-io/terraform-noop-machinepool) | `captf-io/cluster/noop`, `captf-io/machine/noop`, `captf-io/machinepool/noop` |

You can call a module from your own Terraform, but it is a CAPTF root
module first: it configures its own provider block, which takes no `count`,
`for_each` or `depends_on` and reads its credentials from the environment;
it pins its providers exactly; and it needs the `captf_*` contract inputs.
Each repository's README says how in its Usage section.

OpenStack has no machinepool role: it has no native scaling group, and a
`MachineDeployment` of individual machines covers the same need.

Each role is a separate image:

- **cluster** creates what one workload cluster needs around its nodes: the
  security rules, the API server load balancer and, except on OpenStack, the
  node identities. It
  publishes the API endpoint, the failure domains and the ids the other
  roles need (its `exports`).
- **machine** creates one instance for one `Machine` and registers
  control-plane instances with the API load balancer.
- **machinepool** creates one native scaling group (an Auto Scaling group, a
  managed instance group, a scale set or an instance pool) for one
  `MachinePool`.

The no-op roles create none of this: each records its inputs in its state
and returns placeholder outputs.

None of them creates a network. You bring the network, the subnets and the
egress path, and the modules make nodes in them.

## Images and tags

Every role is published as `ghcr.io/captf-io/module-images/<cloud>-<role>`, for example
`ghcr.io/captf-io/module-images/aws-machine`, for `linux/amd64` and `linux/arm64`, in two
flavours: one built FROM
[`terraform-base`](https://github.com/captf-io/terraform-base) and one FROM
[`opentofu-base`](https://github.com/captf-io/opentofu-base) (see [Base
Images](../module-author/base-images.md)). The tags name
the runtime (`<version>-terraform`, `<version>-opentofu`). Each image carries a mirror of the providers its role needs, so a Job
never downloads a provider at run time.

Images are published under `module-images/` rather than at the top level
of `ghcr.io/captf-io/`. GitHub has no API to grant a repository's workflow
write access to a package it did not create, so `module-images` publishes
packages under its own name, which its workflow creates and owns; adding an
image needs no package settings. The earlier top-level images, such as
`ghcr.io/captf-io/aws-machine`, and the `<cloud>-modules` repositories that
built them have been deleted.

The image version is the module release: `vX.Y.Z-<runtime>` contains release
`vX.Y.Z` of the module, fetched from the Terraform Registry.

| Tag | Meaning |
| --- | --- |
| `vX.Y.Z-opentofu`, `vX.Y.Z-terraform` | Module release `vX.Y.Z` on that runtime; rebuilt if the image changes |
| `opentofu`, `terraform` | The newest module release on that runtime |

Both forms are rebuilt, with a new digest, when the image changes without a
module release, for example after a base image bump. Pin a release tag, or a
digest for an image that must not change, in anything you keep. The examples in each
cloud's module repository pin `v0.1.0-opentofu`. [Releasing a
Module](../module-author/releasing.md) covers how these tags are published
and which reference to pin.

## What you bring

The no-op set needs only the identity. Every cloud set needs all of these:

- **A network.** The VPC, VNet, VCN or network, its subnets, and an egress
  path (NAT gateway, Cloud NAT, router) exist before the cluster. Each cloud
  page lists what the subnets need.
- **Node images.** Images built for Cluster API, such as the
  [image-builder](https://github.com/kubernetes-sigs/image-builder) images,
  with cloud-init and a kubelet that runs with `--cloud-provider=external`.
- **A cloud controller manager and a CNI** in the workload cluster: the
  nodes stay `NotReady` and tainted until both run. The modules set up what
  the cloud controller manager needs (node identities, tags, provider IDs)
  but do not install it; on Azure they also write its configuration file
  on each node. On OpenStack you also supply its credentials.
- **An identity.** A `TerraformClusterIdentity` whose Secret holds the
  cloud credentials the provider reads; each cloud page shows the keys. See
  [Identities and Credentials](../user-guide/identities.md).

The modules read the network you bring with data sources; [Building on
Existing State](../module-author/existing-state.md#read-infrastructure-that-already-exists)
shows the pattern and how to build on it.

## Using the modules

1. Read the cloud page for the prerequisites and the identity Secret.
2. Create the identity Secret and the `TerraformClusterIdentity`.
3. Generate a cluster from the cluster repository's `examples/cluster-kubeadm.yaml`
   with `clusterctl generate yaml --from`, filling in the network ids and
   the node image.
4. Install the CNI and the cloud controller manager in the workload cluster
   once its API server answers.

The no-op set skips all of this: see its [quick start](noop/README.md#quick-start).

Module settings beyond the contract inputs are ordinary module variables,
set with `spec.variables` or `spec.variablesFrom`; see
[Module Variables](../user-guide/variables.md). Each role page lists them.

## Forking a module

Each repository is built to be forked. To change a module, fork its role
repository (`terraform-<provider>-<role>`): its `CONVENTIONS.md` is the rule
book every cloud role repository shares, and `make verify` checks most of
it: the file layout, tags on every resource, `terraform validate` and
`tofu validate` (including the oldest validated runtimes, Terraform 1.5.7
and OpenTofu 1.6.3), the unit tests, tflint,
[`tfcapi-lint`](../module-author/tfcapi-lint.md), shellcheck and a trivy
scan. To build your own module images, fork
[`module-images`](https://github.com/captf-io/module-images), point
`sources/versions.tf` at your modules, change the registry and image names,
run `make lock`, then `make verify` and `make test`.
[Module Repository Layout](../module-author/repository-layout.md#starting-point)
walks through forking a set or starting from the no-op modules.

The no-op modules are the smallest modules that meet the contract, and the
starting point of [Your First Module](../getting-started/first-module.md).

[Shared Behavior](shared-behavior.md) describes what all five sets have in
common.
