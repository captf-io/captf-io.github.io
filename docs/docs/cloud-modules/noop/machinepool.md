---
title: "No-op MachinePool Module"
description: "The no-op machinepool role: the stand-in scaling group it records, the contract inputs it reads, and the provider IDs and instances it returns."
icon: lucide/boxes
subtitle: "A stand-in group per MachinePool"
---

# No-op MachinePool Module

The no-op machinepool module stands in for one native scaling group per
`MachinePool`. Its image is `ghcr.io/captf-io/module-images/noop-machinepool`.

The module's source is
[`captf-io/terraform-noop-machinepool`](https://github.com/captf-io/terraform-noop-machinepool),
published on the Terraform Registry as
[`captf-io/machinepool/noop`](https://registry.terraform.io/modules/captf-io/machinepool/noop).

## What it creates

One `terraform_data` resource, `group`, holding the inputs below. Like the
machine role, it decodes `bootstrap_data` as user data would be, and the
decoded value stays sensitive.

## Inputs

The module declares the contract inputs only; it has no variables of its
own, so `spec.variables` has nothing to set.

| Input | Use |
| --- | --- |
| `captf_contract` | Declared, as the contract requires |
| `captf_cluster`, `captf_object`, `captf_tags` | Recorded; the object's name also names the provider IDs |
| `captf_cluster_outputs` | Its `backend_id` is recorded |
| `machinepool_name` | Recorded |
| `replicas` | The group's size: one provider ID per replica |
| `bootstrap_data` | Decoded and recorded, as user data would be |
| `bootstrap_format`, `failure_domains`, `cluster_failure_domains`, `kubernetes_version`, `node_labels` | Recorded |
| `autoscaling` | Declared, as the contract requires, but not read |

## Outputs

| Output | Value |
| --- | --- |
| `provider_id` | `noop-group:///<namespace>/<name>`, stable per `TerraformMachinePool` |
| `provider_id_list` | `noop:///<namespace>/<name>/<i>` for each replica `<i>`, sorted |
| `replicas` | `replicas` |
| `instances` | One `running` instance per provider ID |
| `health` | Always running and healthy |

## Autoscaling

The module always sets the group's size from `replicas`, so it has nothing
to leave to an autoscaler: it accepts `autoscaling` and ignores it. A real
module that hands the size to its cloud's autoscaler reads it; see
[Machine Pools](../../user-guide/machine-pools.md).

## Health

The module always reports `running` and healthy.

## Example

```yaml title="terraformmachinepool.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachinePool
metadata:
  name: demo-pool-0
  labels:
    cluster.x-k8s.io/cluster-name: demo
spec:
  source:
    image: ghcr.io/captf-io/module-images/noop-machinepool:opentofu
```
