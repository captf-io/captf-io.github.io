---
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
lives in its own repository, implements the
[v1alpha1 module contract](../module-author/contract/v1alpha1/README.md),
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
    been applied to a real cloud. Each repository's `DESIGN.md` lists the
    facts the first real apply must confirm. Read it before you rely on a
    module, and pin a release tag.

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

| Cloud | Repository | Roles | Provider |
| --- | --- | --- | --- |
| [AWS](aws/README.md) | [`captf-io/aws-modules`](https://github.com/captf-io/aws-modules) | cluster, machine, machinepool | `hashicorp/aws` 6.67.0 |
| [Google Cloud](gcp/README.md) | [`captf-io/gcp-modules`](https://github.com/captf-io/gcp-modules) | cluster, machine, machinepool | `hashicorp/google` 8.5.0 |
| [Azure](azure/README.md) | [`captf-io/azure-modules`](https://github.com/captf-io/azure-modules) | cluster, machine, machinepool | `hashicorp/azurerm` 5.7.0 |
| [OCI](oci/README.md) | [`captf-io/oci-modules`](https://github.com/captf-io/oci-modules) | cluster, machine, machinepool | `oracle/oci` 9.8.0 |
| [OpenStack](openstack/README.md) | [`captf-io/openstack-modules`](https://github.com/captf-io/openstack-modules) | cluster, machine | `terraform-provider-openstack/openstack` 3.4.0 |
| [No-op](noop/README.md) | [`captf-io/noop-modules`](https://github.com/captf-io/noop-modules) | cluster, machine, machinepool | None: `terraform_data` is built in |

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

Every role is published as `ghcr.io/captf-io/<cloud>-<role>`, for example
`ghcr.io/captf-io/aws-machine`, for `linux/amd64` and `linux/arm64`, in two
flavours: one built FROM
[`terraform-base`](https://github.com/captf-io/terraform-base) and one FROM
[`opentofu-base`](https://github.com/captf-io/opentofu-base) (see [Base
Images](../module-author/base-images.md)). The tags name
the runtime (`<version>-terraform`, `<version>-opentofu`). Each image carries a mirror of the providers its role needs, so a Job
never downloads a provider at run time.

| Tag | Meaning |
| --- | --- |
| `vX.Y.Z-opentofu`, `vX.Y.Z-terraform` | Release `vX.Y.Z` on that runtime; never moves |
| `opentofu`, `terraform` | The newest release on that runtime |
| `edge-opentofu`, `edge-terraform` | The newest build of `main` |

Pin a release tag, or a digest, in anything you keep. The examples in each
cloud repository pin `v0.1.0-opentofu`.

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

## Using the modules

1. Read the cloud page for the prerequisites and the identity Secret.
2. Create the identity Secret and the `TerraformClusterIdentity`.
3. Generate a cluster from the repository's `examples/cluster-kubeadm.yaml`
   with `clusterctl generate yaml --from`, filling in the network ids and
   the node image.
4. Install the CNI and the cloud controller manager in the workload cluster
   once its API server answers.

The no-op set skips all of this: see its [quick start](noop/README.md#quick-start).

Module settings beyond the contract inputs are ordinary module variables,
set with `spec.variables` or `spec.variablesFrom`; see
[Module Variables](../user-guide/variables.md). Each role page lists them.

## Forking a module

Each repository is built to be forked. Its `CONVENTIONS.md` is the rule
book the five repositories share; `make verify` checks most of it: the file
layout, tags on every resource, `terraform validate` and `tofu validate`
(including the oldest validated runtimes, Terraform 1.5.7 and OpenTofu 1.6.3), the unit tests, tflint,
[`tfcapi-lint`](../module-author/tfcapi-lint.md), shellcheck and a trivy
scan. To make a fork your own, change the registry and image names in the
`Makefile` and the workflow, run `make lock`, then `make verify`.

The no-op modules are the smallest modules that meet the contract, and the
starting point of [Your First Module](../getting-started/first-module.md).

[Shared Behavior](shared-behavior.md) describes what all five sets have in
common.
