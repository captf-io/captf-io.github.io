---
description: "Look up what the Azure machinepool module creates, its inputs, outputs, health, lifecycle and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/boxes
subtitle: "Virtual machine scale set"
---

# MachinePool

The `ghcr.io/captf-io/module-images/azure-machinepool` image implements the
[machinepool role](../../module-author/contract/v1alpha1/machinepool.md) on
Azure: one uniform Linux virtual machine scale set of worker nodes per
`MachinePool`, in the cluster's resource group, with an Azure Autoscale
setting that holds its capacity (or, with `autoscaler` set to `external`, no
setting). See [Machine Pools](../../user-guide/machine-pools.md)
for the objects to create.

The module's source is
[`captf-io/terraform-azure-machinepool`](https://github.com/captf-io/terraform-azure-machinepool),
published on the Terraform Registry as
[`captf-io/machinepool/azure`](https://registry.terraform.io/modules/captf-io/machinepool/azure).

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `azurerm_linux_virtual_machine_scale_set.pool_scale_set` | The workers: manual upgrades, no overprovisioning, no single placement group, in the worker subnet, security groups and identity, with termination notifications | Always |
| `azurerm_monitor_autoscale_setting.pool_autoscale_setting` | Holds the scale set's capacity: pinned to `replicas`, or between the autoscaling bounds with CPU rules | Always, except with autoscaling enabled and `autoscaler` `external` |
| `terraform_data.pool_default_zones` | The cluster's zones as of the first apply, kept for a pool without its own failure domains | Always (used without `failure_domains`) |

Without exports (an externally managed cluster and no
`external_cluster_exports`) the scale set and autoscale setting are not
created and a precondition fails.

The `Microsoft.Insights` resource provider is needed for the autoscale
setting, so not while autoscaling is enabled with `autoscaler` `external`.

## Inputs

Contract inputs used: `captf_cluster_outputs` (the cluster's exports),
`captf_tags`, `machinepool_name`, `replicas`, `bootstrap_data`,
`bootstrap_format`, `failure_domains`, `cluster_failure_domains`,
`kubernetes_version`, `node_labels` and `autoscaling`. `captf_contract` is
validated; `captf_cluster` and `captf_object` are not used.

User variables, set with `spec.variables` on the `TerraformMachinePool`
([variables.tf](https://github.com/captf-io/terraform-azure-machinepool/blob/main/variables.tf)):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `accelerated_networking` | `bool` | `true` | Accelerated networking on the instances' NICs |
| `additional_tags` | `map(string)` | `{}` | Extra Azure tags on the scale set and autoscale setting (when it exists). Keys starting with `captf.io_` or `captf.io/` (any case) are rejected; at most 44. Keys 1 to 512 characters without `< > % & \ ? /`, values at most 256. |
| `autoscaler` | `string` | `"native"` | With autoscaling enabled, what sets the capacity: `native` (this module's Azure Autoscale setting) or `external` (no autoscale setting; a scaler outside the module, such as the Kubernetes Cluster Autoscaler, sets it within `autoscaling.min` and `max`). No effect while autoscaling is disabled |
| `autoscaling_scale_in_cpu_percent` | `number` | `25` | With autoscaling and `autoscaler` `native`, scale in by one instance below this average CPU over 10 minutes; a whole number from 1 to 100, and must be below the scale-out threshold. Ignored when `autoscaler` is `external` |
| `autoscaling_scale_out_cpu_percent` | `number` | `75` | With autoscaling and `autoscaler` `native`, scale out by one instance above this average CPU over 10 minutes; a whole number from 1 to 100. Ignored when `autoscaler` is `external` |
| `boot_diagnostics` | `bool` | `true` | Keep the serial console logs in Azure-managed storage |
| `encryption_at_host` | `bool` | `false` | Encrypt temporary disks and caches on the host too; needs the `EncryptionAtHost` feature |
| `external_cluster_exports` | `any` | `null` | Exports (schema `captf.io/azure-cluster/v1`) for an externally managed `TerraformCluster` |
| `image_id` | `string` | `null` | Required. A managed image, Compute Gallery image (version), or community or shared gallery image (version) ID. `{version}` and `{semver}` become the pool's version, `v1.31.4` and `1.31.4`, without any `+suffix` |
| `ip_forwarding` | `bool` | `false` | IP forwarding on the NICs, for CNIs that route pod addresses natively |
| `os_disk_size_gib` | `number` | `128` | OS disk size per instance, 30 to 4095 GiB |
| `os_disk_storage_account_type` | `string` | `"Premium_LRS"` | `Standard_LRS`, `StandardSSD_LRS`, `StandardSSD_ZRS`, `Premium_LRS` or `Premium_ZRS` |
| `spot` | `bool` | `false` | Spot instances, deleted on eviction, at most the on-demand price |
| `trusted_launch` | `bool` | `false` | Secure boot and vTPM; needs a generation 2 image built for trusted launch |
| `vm_size` | `string` | `"Standard_D4s_v5"` | Azure VM size of the instances |

## Outputs

| Output | Value |
| --- | --- |
| `provider_id` | `azure:///subscriptions/<subscription>/resourceGroups/<group, lowercase>/providers/Microsoft.Compute/virtualMachineScaleSets/<scale set>`; changes when a new generation replaces the scale set |
| `provider_id_list` | Every instance the scale set lists, whatever its power state, as `<provider_id>/virtualMachines/<instance ID>`, the format cloud-provider-azure writes to the Node |
| `replicas` | The scale set's capacity as last refreshed, whichever scaler set it; `null` once the scale set is gone |
| `instances` | Per instance: `provider_id`, `instance_id`, `addresses` (`InternalIP`, `Hostname`), `failure_domain` (its zone) and `state` |
| `health` | See Health |
| `autoscale_setting_id` | Extra: the autoscale setting's ARM ID; `null` while autoscaling is enabled with `autoscaler` `external` |
| `dropped_node_labels` | Extra: `node_labels` keys left out because the kubelet may not set them on itself |
| `scale_set_id`, `scale_set_name` | Extra: the current scale set's ARM ID and name |

The scale set is named `<machinepool_name, made valid, at most 41
characters>-<8 hex characters>`, and its instances' hostnames start with
that name; cloud-provider-azure finds an instance by its hostname, so name
the Nodes after it (`nodeRegistration.name: '{{
ds.meta_data["local_hostname"] }}'`).

## Health

The module lists the scale set first and reads its instances only when the
listing finds it. Each instance's power state maps like a
[machine's](machine.md#health); the pool follows the
[shared order](../shared-behavior.md#health):

| Azure state | Contract state | Reason |
| --- | --- | --- |
| Scale set gone (a refresh dropped it) | `terminated` | `ScaleSetNotFound` |
| Capacity 0 | `running`, healthy | none |
| Not listed yet (first apply, new generation) or no instances | `pending` | `NoMembers`; `provider_id_list` is `[]` until the next refresh |
| Some instance stopped, deallocated or in an unknown state | the worst of `degraded`, `stopped`, `unknown` | `<reason>:<hostname>` per instance |
| Instances starting, or the count off the capacity | `running`, not healthy | `PowerState/starting:<hostname>` per instance, `ScalingInProgress` |
| Every instance running at capacity | `running`, healthy | none |

Azure lists an instance until it is deleted, so no instance maps to
`terminated`: a deleted instance leaves `provider_id_list`.

## Lifecycle

| Change | Effect |
| --- | --- |
| `bootstrap_data` (a token rotation, about every 7.5 minutes), `node_labels`, `image_id`, `vm_size`, `os_disk_size_gib`, `accelerated_networking`, `ip_forwarding`, `boot_diagnostics`, `encryption_at_host`, the exports, tags | The scale set's model updates in place; new instances use it, running ones are left alone |
| `replicas`, autoscaling disabled | The autoscale setting pins the new capacity; Azure Autoscale applies it within about a minute |
| `autoscaling`, `autoscaling_scale_*_cpu_percent` | The autoscale setting gets the new bounds and rules (with `autoscaler` `external`, no setting exists and nothing changes in Azure) |
| `autoscaler`, with autoscaling enabled | The autoscale setting is created or deleted; the scale set and its capacity stay |
| `kubernetes_version`, compared verbatim (a `+rke2rN` bump included) | A new scale set at the current capacity, then the old one is deleted |
| `failure_domains`, `spot`, `trusted_launch`, `os_disk_storage_account_type` | A new scale set, as for a version change: Azure cannot change these on a scale set |
| `cluster_failure_domains` | Nothing: a pool without its own `failure_domains` keeps the cluster's zones as of its first apply |

The provider turns off `roll_instances_when_required` and
`reimage_on_manual_upgrade`: with azurerm's defaults every token rotation
would reimage every instance. So nothing rolls by itself, and a version
change creates a new scale set with `create_before_destroy`; the pool
briefly needs twice its quota. There is no drain: pools have no Machines.
Scheduled Events announce every deletion 5 minutes ahead, for a termination
handler that drains.

## Bootstrap

- **Delivery.** As for the [machine role](machine.md#bootstrap): custom
  data, `cloud-config` in a MIME multipart message after a boot hook, and
  Ignition unchanged (gzipped Ignition fails a precondition). The boot hook
  writes `/etc/kubernetes/azure.json` for the worker identity when the file
  is absent and renders the node labels as the
  [shared behavior](../shared-behavior.md#machine-pools) describes; Ignition
  with labels left to render fails a precondition.
- **Size limit.** 65,535 bytes of custom data, 87,380 base64 characters; a
  precondition stops a larger message.
- **Who can read it.** As for the machine role: not through the instance
  metadata service or a read of the scale set; on the node only root; and
  the pool's state Secret on the management cluster.

## Limitations

!!! warning "Keep pools to about 200 instances"

    A scale set holds at most 1,000 instances, but every refresh reads each
    instance's NICs with one Azure call; keep pools to about 200 instances, or
    raise `spec.membershipRefreshIntervalSeconds`.

- Workers only: the control plane uses the [machine role](machine.md).
- Changes reach new instances only; a version change is the way to roll the
  pool.
- Capacity changes go through Azure Autoscale (or, with `autoscaler`
  `external`, the outside scaler) and take about a minute to reach the scale
  set; `replicas` follows at the next refresh.
- The scale set read fails if an instance disappears between listing it and
  reading its NICs; the next refresh succeeds.
- Azure public cloud only.

## Exceptions

- **`pool/autoscaling-ignore-changes`**, a `tfcapi-lint` warning, is allowed:
  the scale set ignores changes to `instances`, its desired count, which the
  check's pattern does not know, and the capacity is held outside the scale
  set: by Azure Autoscale in fixed mode and with `autoscaler` `native`, by an
  outside scaler with `autoscaler` `external`.
- **Version rolls by generation.** The roll is a new scale set name with
  `create_before_destroy`, not `terraform_data.kubernetes_version_roll`: a
  replacement under the same name would collide with the old scale set.
- **Other replacements.** `failure_domains`, `spot`, `trusted_launch` and
  `os_disk_storage_account_type` replace the scale set, because azurerm
  5.7.0 cannot update them in place.
- **`replicas` is `null` once the scale set is gone:** the capacity is then
  unknown, and an empty `provider_id_list` with an unknown capacity keeps
  Cluster API's guard against deleting every Node engaged.
- The `membership_excludes_terminated` test asserts that stopped and
  deallocated instances stay members, since Azure has no terminated instance
  state; the `ScaleSetNotFound` reading has no test.

## Example

```yaml title="terraformmachinepool.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachinePool
metadata:
  name: demo-pool-0
  namespace: team-a
  labels:
    cluster.x-k8s.io/cluster-name: demo
spec:
  source:
    image: ghcr.io/captf-io/module-images/azure-machinepool:v0.1.0-opentofu
  variables:
    image_id: /communityGalleries/ClusterAPI-f72ceb4f-5159-4c26-a0fe-2ea738f0d019/images/capi-ubun2-2404/versions/{semver}
    autoscaling_scale_out_cpu_percent: 70
```

### Use with the Kubernetes Cluster Autoscaler

To let the Cluster Autoscaler's azure cloud provider scale the pool instead
of Azure Autoscale (two scalers on one scale set would fight):

- Keep the `MachinePool`'s autoscaler min and max annotations, as in
  [Machine Pools](../../user-guide/machine-pools.md#autoscale-with-the-kubernetes-cluster-autoscaler):
  they put the module in autoscaling mode and bound `replicas`.
- Set `autoscaler: external` in `spec.variables`: the module then creates no
  autoscale setting and never resets the capacity (the scale set ignores
  `instances`), and `replicas` follows what the scaler sets.
- Tag the scale set for the Cluster Autoscaler's auto-discovery through
  `additional_tags`, for example `k8s.io_cluster-autoscaler_enabled`,
  `k8s.io_cluster-autoscaler_<cluster name>`, and `min` and `max` tags
  matching the annotations. These keys pass the `additional_tags` validation
  (no reserved prefix, no `/`; at most 44 tags). The tag names are the
  Cluster Autoscaler's, not verified in the module repository.
- Prefer tag-based discovery to a static scale set name: the scale set's
  name changes with each generation (a Kubernetes version change creates a
  new scale set), and the tags move with it.

Switching `autoscaler` from `native` to `external` deletes the autoscale
setting; whether the scale set's capacity then stays at its last value is
not verified. The Cluster Autoscaler driving a pool has not been run against
a live cluster.
