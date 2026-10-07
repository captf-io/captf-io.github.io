---
title: "No-op Cluster Module"
description: "The no-op cluster role: the stand-in resource it records, the contract inputs it reads, and the endpoint, failure domain and exports it returns."
icon: lucide/network
subtitle: "A stand-in load balancer"
---

# No-op Cluster Module

The no-op cluster module stands in for what a real cluster module creates
around a workload cluster's nodes. Its image is
`ghcr.io/captf-io/module-images/noop-cluster`.

The module's source is
[`captf-io/terraform-noop-cluster`](https://github.com/captf-io/terraform-noop-cluster),
published on the Terraform Registry as
[`captf-io/cluster/noop`](https://registry.terraform.io/modules/captf-io/cluster/noop).

## What it creates

One `terraform_data` resource, `load_balancer`, the stand-in for a load
balancer and a network. It holds the inputs below, so a change to any of
them shows as a change in the plan. Its id feeds the `exports`, so
machines receive a value that exists only after this module applied.

## Inputs

The module declares the contract inputs only; it has no variables of its
own, so `spec.variables` has nothing to set.

| Input | Use |
| --- | --- |
| `captf_contract` | Declared, as the contract requires |
| `captf_cluster`, `captf_object` | Recorded; the object's name also names the default endpoint |
| `captf_tags` | Recorded |
| `control_plane_endpoint` | Returned as the endpoint when set |
| `kubernetes_version`, `control_plane_initialized`, `cluster_network` | Recorded |

## Outputs

| Output | Value |
| --- | --- |
| `control_plane_endpoint` | `control_plane_endpoint` when set; otherwise host `noop-<name>.invalid`, port `6443` |
| `failure_domains` | One failure domain, `fd1`, eligible for the control plane |
| `exports` | `{ backend_id = "noop-backend-<id>" }`, the stand-in load balancer's id |
| `health` | Always running and healthy |

The `.invalid` top-level domain never resolves (RFC 2606), so the default
endpoint is valid and stable but reaches nothing.

## Health

The module always reports `running` and healthy: there is no
infrastructure to check.

## Limitations

- **The endpoint reaches nothing.** No load balancer exists behind it.
- **One failure domain.** Machines and pools all land in `fd1`.

## Example

```yaml title="terraformcluster.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformCluster
metadata:
  name: demo
spec:
  source:
    image: ghcr.io/captf-io/module-images/noop-cluster:opentofu
  identityRef:
    name: noop
  defaults:
    identityRef:
      name: noop
```
