---
description: "Look up what the OCI machinepool module creates, its inputs, outputs, health, lifecycle and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/boxes
subtitle: "Instance pool of nodes"
---

# MachinePool

The `ghcr.io/captf-io/oci-machinepool` image implements the
[machinepool role](../../module-author/contract/v1alpha1/machinepool.md)
for a `TerraformMachinePool` on OCI: one instance pool, launched from an
instance configuration and spread over the `MachinePool`'s failure domains,
at a fixed size or sized by OCI autoscaling.

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `oci_core_instance_configuration.pool_instance_configuration` | What every pool instance launches with | Always |
| `oci_core_instance_pool.fixed_instance_pool` | The pool, at `replicas` | `autoscaling.enabled` false |
| `oci_core_instance_pool.autoscaled_instance_pool` | The pool, sized by the autoscaler | `autoscaling.enabled` |
| `oci_autoscaling_auto_scaling_configuration.pool_autoscaling_configuration` | CPU threshold scaling within the annotations' bounds | `autoscaling.enabled` |
| `terraform_data.kubernetes_version_roll` | Replaces the pool when the Kubernetes version changes | Always |

The instances look like the [machine role](machine.md)'s workers, on the
worker subnet and network security group. The module lists the pool's
members on every refresh.

## Inputs

Contract inputs used: `captf_cluster` and `machinepool_name` (names),
`captf_cluster_outputs` (or `external_cluster_exports`), `captf_tags`,
`replicas`, `bootstrap_data`, `bootstrap_format`, `failure_domains`,
`cluster_failure_domains`, `kubernetes_version`, `node_labels` and
`autoscaling`. `captf_contract` is validated; `captf_object` is declared
and unused.

User variables, from
[variables.tf](https://github.com/captf-io/oci-modules/blob/main/machinepool/variables.tf):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_nsg_ids` | `list(string)` | `[]` | Extra network security groups for the VNICs, after the cluster's worker NSG; at most 4. |
| `additional_tags` | `map(string)` | `{}` | Extra free-form tags for every pool resource; at most 4. |
| `autoscaled` | `bool` | `false` | Must equal `autoscaling.enabled`: the deliberate second switch for a mode change, which replaces the pool. |
| `autoscaling_cool_down_seconds` | `number` | `300` | Minimum time between two scaling actions; 300 is OCI's minimum. |
| `autoscaling_scale_in_cpu_percent` | `number` | `30` | Remove an instance below this CPU utilization. |
| `autoscaling_scale_out_cpu_percent` | `number` | `70` | Add an instance above this CPU utilization. |
| `boot_volume_kms_key_id` | `string` | `null` | Vault key for the boot volumes; `null` uses Oracle-managed keys. |
| `boot_volume_size_gib` | `number` | `100` | Boot volume size, 50 to 32768. |
| `external_cluster_exports` | `any` | `null` | The cluster's exports when the `TerraformCluster` is externally managed. |
| `ignore_defined_tags` | `list(string)` | `[]` | Tag-default keys (`<namespace>.<key>`) to leave alone. |
| `image_id` | `string` | `null` | Required. Node image OCID in the cluster's region; a new image reaches new instances only. |
| `memory_gib` | `number` | `16` | Memory of a flexible shape; ignored for fixed shapes. |
| `ocpus` | `number` | `2` | OCPUs of a flexible shape; ignored for fixed shapes. |
| `preemptible` | `bool` | `false` | Preemptible capacity. |
| `public_ip` | `bool` | `false` | A public IP on every instance; needs a public subnet. |
| `pv_encryption_in_transit` | `bool` | `true` | Encrypt boot volume traffic in transit. |
| `shape` | `string` | `"VM.Standard.E5.Flex"` | Compute shape. |
| `ssh_authorized_keys` | `list(string)` | `[]` | SSH public keys for the image's default user. |
| `subnet_id` | `string` | `null` | Subnet of the instances; `null` uses the cluster's worker subnet. |

## Outputs

| Output | Value |
| --- | --- |
| `provider_id` | OCID of the instance pool |
| `provider_id_list` | `oci://<instance OCID>` of every member, whatever its health, sorted; an instance `TERMINATING` or `TERMINATED` is not a member |
| `replicas` | The pool's size as OCI reports it (`actual_size`): `replicas`, or what the autoscaler decided; not the running count |
| `instances` | Per member: `provider_id`, `instance_id`, `failure_domain` (mapped back from its availability and fault domain), `state`, and `addresses = []` |
| `health` | Below |
| `dropped_node_labels` | Extra: `node_labels` keys left out because NodeRestriction forbids a kubelet to set them |

## Health

The pool follows the order in [Shared Behavior](../shared-behavior.md#health).
On OCI:

| Situation | Contract state | Reason |
| --- | --- | --- |
| Pool gone from state, `TERMINATING` or `TERMINATED` | `terminated` | `PoolNotFound` |
| Member `PROVISIONING`, `STARTING` | `running` while others run; `pending` only with no members | `InstanceProvisioning:<OCID>`, `InstanceStarting:<OCID>`; `NoMembers` |
| Member `CREATING_IMAGE` | `unknown` | `InstanceCreatingImage:<OCID>` |
| Member `STOPPING`, `STOPPED` | `stopped` | `InstanceStopping:<OCID>`, `InstanceStopped:<OCID>` |
| Member in any other state | `unknown` | `UnknownState:<OCID>` |
| Member count below the desired size | `running` | `ScalingInProgress` |

Members `RUNNING` or `MOVING` are running.

## Lifecycle

| Change | Effect |
| --- | --- |
| `bootstrap_data` (a rotation, about every 7.5 minutes with kubeadm), `node_labels`, the image or another instance setting | A new instance configuration, created before the old one goes; the pool switches to it in place. Running instances stay. |
| `kubernetes_version`, compared verbatim (a `+rke2rN` bump included) | The pool is replaced, new before old: the new pool comes up at the current size, then the old one and its instances go. `provider_id` changes. |
| `replicas`, autoscaling off | The pool resizes in place. |
| `replicas`, autoscaling on | Nothing: the autoscaler owns the size. |
| `autoscaling.min` or `max` | The autoscaling configuration is replaced; the pool stays. |
| `autoscaling.enabled` on or off | Refused until `autoscaled` matches; then the pool is replaced, every instance at once. |
| `failure_domains` | The pool's placement updates in place; existing instances stay where they are. |

## Bootstrap

- **Delivery.** A cloud-config payload becomes the second part of a MIME
  multipart whose first part is a `text/cloud-boothook` script with the
  shared node-labels fragment (see
  [Shared Behavior](../shared-behavior.md#machine-pools)). The payload is
  an opaque base64 part, `text/plain` so cloud-init detects cloud-config and
  CABPK's Jinja header, or `application/x-gzip` for a gzipped payload. An
  Ignition payload passes through unchanged; with node labels, or gzipped,
  it is refused.
- **Size.** Instance metadata may hold 32,000 bytes, the boothook part
  included; a precondition stops a larger payload.
- **Who can read it.** As for the [machine role](machine.md#bootstrap):
  the instance itself, and principals that may read instances in the
  compartment. Pool instances are workers, whose join token is the only
  secret in the payload.

## Limitations

!!! warning "Scale-in, a version roll or a mode switch does not drain nodes"

    A scale-in, a version roll or a mode switch terminates
    instances without draining them: MachinePool Machines are out of scope.
    OCI's pre-termination lifecycle action only delays termination, so it is
    not configured.

- **No addresses** in `instances`: the pool's member list carries none.
- **Autoscaling down to 0** is refused (`min` must be at least 1) until it
  is verified. Autoscaling needs the Compute Instance Monitoring plugin on
  the image.
- **Existing members keep** their labels and bootstrap settings; only new
  members get a new instance configuration.

## Exceptions

- `tfcapi-lint` warns `pool/autoscaling-ignore-changes`, allowed in the
  repository's Makefile: the check knows desired-count attributes by name,
  and an OCI pool's is `size`, which it does not list. The autoscaled pool
  does ignore `size`.
- Switching autoscaling on or off replaces the pool and all its instances:
  OCI pools have no minimum or maximum to pin, so one pool resource cannot
  serve both modes. The `autoscaled` variable makes the switch deliberate.

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
    image: ghcr.io/captf-io/oci-machinepool:v0.1.0-opentofu
  variables:
    image_id: ocid1.image.oc1.iad.<id>
```

For an autoscaled pool, add `autoscaled: true` to the variables and both
autoscaler annotations to the `MachinePool`:

```yaml
metadata:
  annotations:
    cluster.x-k8s.io/cluster-api-autoscaler-node-group-min-size: "2"
    cluster.x-k8s.io/cluster-api-autoscaler-node-group-max-size: "10"
```
