---
description: "Try CAPTF or test a management cluster with no cloud account: the no-op module images, what they return, and a quick start."
icon: lucide/flask-conical
subtitle: "Real plans and state, no cloud"
---

# No-op

The no-op modules implement all three roles of the
[v1alpha1 module contract](../../module-author/contract/v1alpha1/README.md)
and provision nothing. Every resource is a `terraform_data` holding the
inputs it was given, so the plans, the state and the outputs are real
while no cloud is touched and no credentials are read. Use them to try
CAPTF, to test a management cluster, or as the smallest starting point for
a module of your own. The images are built from
[`captf-io/noop-modules`](https://github.com/captf-io/noop-modules), which
holds the modules and is their only source.

<div class="grid cards" markdown>

-   :material-lan:{ .lg .middle } __Cluster__

    ---

    A stand-in load balancer, an endpoint that never resolves, one failure domain.

    [:octicons-arrow-right-24: Cluster](cluster.md)

-   :material-server:{ .lg .middle } __Machine__

    ---

    A stand-in instance per `Machine`, with a stable provider ID.

    [:octicons-arrow-right-24: Machine](machine.md)

-   :material-server-network:{ .lg .middle } __MachinePool__

    ---

    A stand-in scaling group per `MachinePool`, one provider ID per replica.

    [:octicons-arrow-right-24: MachinePool](machinepool.md)

</div>

## Images

| Role | Image | Page |
| --- | --- | --- |
| cluster | `ghcr.io/captf-io/noop-cluster` | [Cluster](cluster.md) |
| machine | `ghcr.io/captf-io/noop-machine` | [Machine](machine.md) |
| machinepool | `ghcr.io/captf-io/noop-machinepool` | [MachinePool](machinepool.md) |

The images need no Terraform provider: `terraform_data` is built into
Terraform and OpenTofu. They are built on the
[Terraform and OpenTofu base images](../../module-author/image-contract.md),
for `linux/amd64` and `linux/arm64`, with the same tags as every set (see
[Images and tags](../README.md#images-and-tags)). The modules declare
`required_version = ">= 1.5"`, which every OpenTofu release satisfies.

## Prerequisites

- **A management cluster with CAPTF installed.** See
  [Install the provider](../../getting-started/quick-start.md#1-install-the-provider).
- **An identity.** Every `TerraformCluster` names a
  `TerraformClusterIdentity`, even one whose modules read no credentials.
  The Secret behind it can hold anything: the provider's
  `templates/identity.yaml` with its placeholder keys left as they are is
  enough.

Nothing else: no network, no node image, no cloud controller manager and
no CNI.

## Quick start

Follow the [Quick Start](../../getting-started/quick-start.md), with the
published images, which its third step selects. When you generate the
cluster, set:

```sh
export TERRAFORM_CLUSTER_IMAGE=ghcr.io/captf-io/noop-cluster:opentofu
export TERRAFORM_MACHINE_IMAGE=ghcr.io/captf-io/noop-machine:opentofu
```

The `opentofu` tag is the newest release; pin a release tag such as
`vX.Y.Z-opentofu`, or a digest, in anything you keep. The `terraform` tags
run the same modules on Terraform.

## What you will see

The `TerraformCluster` and each `TerraformMachine` reach `Ready=True`, and
the `Cluster` and its `Machine`s reach phase `Provisioned`: the modules
return an endpoint and provider IDs. No `Machine` reaches `Running`, and
`KubeadmControlPlane` never reports itself initialized, because no node
ever boots or registers. The images exercise CAPTF, not Kubernetes.

!!! warning "Remediation starts after about 30 minutes"

    No `Node` ever registers, so once a `MachineHealthCheck`'s node-startup
    timeout passes, Cluster API starts remediating the `Machine`s. See
    [Remediation](../../user-guide/remediation.md).

## Exports

The cluster role's `exports` carry one key, `backend_id`: the id of its
stand-in load balancer. The machine and machinepool roles record it in
their own state, so a machine's state holds a value that exists only after
the cluster applied, as with a real set. The exports have no `schema` key.

## Tags

Each role records `captf_tags` in its resource, so the tags show in the
state and the plan. There is nothing to tag.

## Writing your own

The no-op modules are the smallest modules that meet the contract, which
makes them the starting point of
[Your First Module](../../getting-started/first-module.md). Each role page
lists the inputs it reads and the outputs it returns.
