---
description: "Look up what the Google Cloud machinepool module creates, its inputs, outputs, health, lifecycle and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/boxes
subtitle: "Managed instance group"
---

# MachinePool

The `ghcr.io/captf-io/gcp-machinepool` image implements the
[machinepool role](../../module-author/contract/v1alpha1/machinepool.md)
for a `TerraformMachinePool` on Google Cloud. It creates one regional
managed instance group per `MachinePool`, spread over the pool's zones,
with an optional autoscaler. Pool instances are workers.

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `google_compute_region_instance_template.pool_instance_template` | Everything an instance is made of except the bootstrap data | Always |
| `google_compute_region_instance_group_manager.pool_instance_group_manager` | The group, over the pool's zones; holds the bootstrap data in its all-instances config | Always |
| `google_compute_region_autoscaler.pool_autoscaler` | The autoscaler, between the annotations' minimum and maximum | While the `MachinePool`'s autoscaler annotations enable autoscaling with a maximum above 0 |
| `terraform_data.pool_default_zones` | The cluster's zones at the first apply, pinned | Always; used when the pool names no failure domains |

A data source lists the group's members, in every state, on each refresh.
Instances run as the cluster's worker service account, with its network
tags, no external address, Shielded VM, OS Login, project-wide SSH keys
blocked and the serial console off.

## Inputs

Contract inputs it uses:

- `machinepool_name`: names of the group and its instances.
- `replicas`: the group's target size without autoscaling.
- `bootstrap_data`, `bootstrap_format`: the user data.
- `failure_domains`, `cluster_failure_domains`: the zones.
- `kubernetes_version`: fills the image placeholders.
- `node_labels`: registered by every new instance's kubelet.
- `autoscaling`: the autoscaler.
- `captf_cluster_outputs`: the cluster's exports.
- `captf_cluster`, `captf_object`, `captf_tags`: names, descriptions and
  labels.

User variables, set with `spec.variables` on the `TerraformMachinePool`
([variables.tf](https://github.com/captf-io/gcp-modules/blob/main/machinepool/variables.tf)):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_network_tags` | `list(string)` | `[]` | Extra network tags for the pool's instances, on top of the cluster's node and role tags. Each at most 63 characters: lowercase letters, digits and `-`. |
| `additional_tags` | `map(string)` | `{}` | Extra GCP labels for the pool's instances, their boot disks and the instance template. Keys and values must already be valid GCP labels; the `captf-io_` keys are reserved for `captf_tags`, which win. At most 58 labels; keys match `^[a-z][a-z0-9_-]{0,62}$`, values `^[a-z0-9_-]{0,63}$`. |
| `autoscaling_initialization_seconds` | `number` | `300` | Seconds a new instance needs to boot and join before the autoscaler reads its CPU; 300 covers image boot, cloud-init and kubeadm join. A whole number, 0 or more. |
| `autoscaling_target_cpu_percent` | `number` | `60` | Average CPU utilization, in percent, the autoscaler keeps the pool at while the `MachinePool`'s autoscaler annotations enable autoscaling. 60 leaves headroom for a node to fail. Greater than 0 and at most 100. |
| `boot_disk_kms_key_id` | `string` | `null` | Cloud KMS key (`projects/.../cryptoKeys/...`) that encrypts the boot disks. Null uses Google-managed encryption; the Compute Engine service agent needs encrypt and decrypt on the key. |
| `boot_disk_size_gib` | `number` | `50` | Boot disk size in GiB: room for the image, container images and logs. A whole number, at least 10. |
| `boot_disk_type` | `string` | `"pd-balanced"` | Boot disk type. `pd-balanced` suits the default N2 machine type; C3, N4 and newer series need `hyperdisk-balanced`. |
| `can_ip_forward` | `bool` | `false` | Let the instances send and receive packets for other addresses, as CNIs that route pod CIDRs through GCP routes need. |
| `external_cluster_exports` | `any` | `null` | Exports (schema `captf.io/gcp-cluster/v1`) to use when the `TerraformCluster` is externally managed and `captf_cluster_outputs` is `{}`. Ignored otherwise. |
| `image` | `string` | `null` | Boot image: a name, `projects/<p>/global/images/<image>` or a self link, with a version placeholder (below) so a `kubernetes_version` change rolls the pool. Required. |
| `machine_type` | `string` | `"n2-standard-4"` | Machine type of the pool's instances: 4 vCPU and 16 GiB by default. |
| `secure_boot` | `bool` | `true` | Shielded VM Secure Boot. Turn it off only for images whose kernel modules are unsigned (some GPU drivers). |
| `spot` | `bool` | `false` | Run the pool on Spot VMs: cheaper, preemptible at any time; a preempted instance stops and the group repairs it. |

With `kubernetes_version` set, `image` must contain `{version}`
(`v1.33.4`), `{semver}` (`1.33.4`), `{slug}` (`v1-33-4`) or `{fullslug}`
(`v1-33-4-rke2r1`), and `{fullslug}` when the version has a `+rke2rN`
suffix: only `{fullslug}` keeps the suffix, so only it makes a suffix-only
upgrade change the image.

## Outputs

| Output | Value |
| --- | --- |
| `provider_id` | The group's ID, `projects/<p>/regions/<r>/instanceGroupManagers/<name>` |
| `provider_id_list` | `gce://<project>/<zone>/<instance>` of every member, in any state, except members being deleted (`DEPROVISIONING`), sorted |
| `replicas` | The group's target size as observed: the autoscaler's while it scales; 0 once the group is gone |
| `instances` | Per member: `provider_id`, `instance_id` (the instance name), `addresses = []`, `failure_domain` (zone), `state` |
| `health` | Below |

Stopped members (`TERMINATED`) stay in `provider_id_list`: dropping one
would make Cluster API delete its Node. The member listing carries no
addresses.

Extra outputs: `autoscaler_id`, `dropped_node_labels` (keys of
`node_labels` the kubelet may not set on itself), `instance_group_manager_id`
and `instance_template_id`.

## Health

Each member's status maps as on the [Machine](machine.md#health) page. The
pool's health, in this order:

| Situation | Contract state | Reason |
| --- | --- | --- |
| The group no longer exists | `terminated` | `InstanceGroupNotFound` |
| Target size 0, and no autoscaler minimum above 0 still to reach | `running`, healthy | none |
| No members yet | `pending` | `NoMembers` |
| A member degraded, stopped or unknown | The worst of those three | `<reason>:<instance>` per affected member, then per starting member, plus `ScalingInProgress` while the count differs |
| Otherwise | `running`, healthy only when every member runs and the count equals the target size | The starting members, plus `ScalingInProgress` while the count differs |

An autoscaled group is created empty and grows to its minimum, so until a
member exists it reports `pending`, not "scaled to zero".

## Lifecycle

| Change | What happens |
| --- | --- |
| `bootstrap_data` (rotates about every 7.5 minutes with kubeadm) | The all-instances metadata updates in place: a refresh that never restarts or replaces an instance; new instances boot with the current data |
| `kubernetes_version` | The placeholder changes the image, so a new instance template is created and the group's proactive update replaces every instance, one surge instance per zone at a time, none removed first |
| `node_labels` | The all-instances metadata updates in place: new instances register the new labels; existing ones keep theirs |
| `replicas`, without autoscaling | The group's target size |
| `replicas`, with autoscaling | Ignored: the target size is left to the autoscaler |
| Autoscaling on or off | Creates or deletes the autoscaler; a maximum of 0 means no autoscaler and a target size of 0 |
| `failure_domains` | Replaces the group, and every instance at once |
| The cluster's zones | Nothing: a pool without its own failure domains keeps the zones of its first apply |
| `captf_tags`, `additional_tags` | The all-instances config relabels every instance in place; the template keeps its creation labels |
| `machine_type`, `boot_disk_*`, `spot`, `secure_boot`, `additional_network_tags`, `can_ip_forward` | A new instance template; the group updates instances with the least disruptive action Compute Engine allows, which may replace them |

Nothing drains an instance first: `MachinePool` Machines are out of scope
for the contract.

## Bootstrap

The bootstrap data lives in the group's all-instances config, as the
instance metadata key `user-data`.

| Format | Labels to register | Sent as |
| --- | --- | --- |
| `cloud-config` | None | The base64 data, with `user-data-encoding=base64` |
| `cloud-config` | Some | A MIME multipart message: a `text/cloud-boothook` part with the shared node-labels script, then the data as a base64 part (`application/x-gzip` when gzipped) |
| Ignition | None | The decoded data; gzipped Ignition is refused |
| Ignition | Some | Refused: Ignition has no boothook to register them |

The node labels script is the one every CAPTF pool shares; see
[Shared Behavior](../shared-behavior.md#machine-pools). The user data must
fit the 256 KB instance metadata value limit. Pool data holds a join token,
not key material: it is readable by anyone with `compute.instances.get` in
the project and by anything on the node that reaches the metadata server.

## Limitations

!!! warning "Changing failure_domains replaces the group at once"

    Changing `failure_domains` replaces the group at once. A pool without
    them keeps the cluster's zones of its first apply, even if the cluster
    later drops one.

- A pool holds at most 500 instances, the one page the member listing
  returns; a precondition checks `replicas` or the autoscaler's maximum.
- The group keeps zones balanced and may delete an instance to rebalance;
  nothing drains it.
- Ignition pools cannot register `node_labels`.
- The template and its boot disks keep the labels of the template's
  creation: their labels force replacement, so they are not updated.

## Exceptions

- **Any instance template change rolls the pool.** Every template argument
  forces a new template, so a change of `machine_type`, `boot_disk_*`,
  `spot`, `secure_boot`, `additional_network_tags` or `can_ip_forward`
  updates instances with the least disruptive action Compute Engine allows,
  which may replace them.
- **A version change rolls through the image name**, not a version trigger:
  a template change that only touches metadata is applied as a refresh and
  rolls nothing. So `image` needs a version placeholder, and `{fullslug}`
  for versions with a `+rke2rN` suffix.
- **The autoscaler's count is kept without `ignore_changes`** (the allowed
  `tfcapi-lint` warning `pool/autoscaling-ignore-changes`): the group's
  target size is null while an autoscaler runs, which leaves the observed
  value alone, and `replicas` otherwise.

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
    image: ghcr.io/captf-io/gcp-machinepool:v0.1.0-opentofu
  variables:
    image: projects/my-images/global/images/capi-ubuntu-2404-{slug}
```
