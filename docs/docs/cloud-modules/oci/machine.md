---
description: "Look up what the OCI machine module creates, its inputs, outputs, health, lifecycle and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/server
subtitle: "One compute instance"
---

# Machine

The `ghcr.io/captf-io/oci-machine` image implements the
[machine role](../../module-author/contract/v1alpha1/machine.md) for a
`TerraformMachine` on OCI: one compute instance per `Machine`, placed in the
Machine's failure domain on the cluster's subnet and network security group
and, for a control-plane machine, registered in the API load balancer.

The module's source is
[`captf-io/terraform-oci-machine`](https://github.com/captf-io/terraform-oci-machine),
published on the Terraform Registry as
[`captf-io/machine/oci`](https://registry.terraform.io/modules/captf-io/machine/oci).

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `oci_core_instance.node_instance` | The node and its boot volume | Always |
| `oci_network_load_balancer_backend.api_backends` | The instance in each API backend set (`kube-apiserver`, and `rke2-supervisor` with RKE2) | `control_plane` and a module-owned endpoint |

The instance is named `machine_name`, the first key the OCI cloud controller
manager looks a node up by. It runs `image_id` on `VM.Standard.E5.Flex` with
2 OCPUs and 16 GB by default, on a 100 GiB boot volume that is encrypted at
rest (with `boot_volume_kms_key_id` when set) and in transit, and that goes
with the instance when it terminates. It has no public IP and no SSH key
unless you ask, and instance metadata v1 is off. A control-plane machine
carries the cluster's control-plane defined tag, which the node dynamic
group matches; a worker carries the worker tag.

## Inputs

Contract inputs used: `captf_cluster_outputs` (or
`external_cluster_exports`), `captf_tags`, `machine_name`,
`bootstrap_data`, `bootstrap_format`, `failure_domain` and `control_plane`.
`captf_contract` is validated; `captf_cluster`, `captf_object` and
`kubernetes_version` are declared and unused: the image carries the
version.

User variables, from
[variables.tf](https://github.com/captf-io/terraform-oci-machine/blob/main/variables.tf):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_nsg_ids` | `list(string)` | `[]` | Extra network security groups for the VNIC, after the cluster's; at most 4 (a VNIC holds 5 and the cluster's group is always one). |
| `additional_tags` | `map(string)` | `{}` | Extra free-form tags for the instance and its VNIC. At most 4 entries; keys 1 to 100 printable ASCII characters without periods or spaces and not starting with `captf_io/` (case-insensitive), values at most 256. |
| `boot_volume_kms_key_id` | `string` | `null` | Vault key for the boot volume; `null` uses Oracle-managed keys. |
| `boot_volume_size_gib` | `number` | `100` | Boot volume size, 50 to 32768. |
| `external_cluster_exports` | `any` | `null` | The cluster's exports when the `TerraformCluster` is externally managed. |
| `ignore_defined_tags` | `list(string)` | `[]` | Tag-default keys (`<namespace>.<key>`) to leave alone. At most 98 entries (the provider allows 100; two are the `Oracle-Tags` entries). |
| `image_id` | `string` | `null` | Required. Node image OCID in the cluster's region. |
| `memory_gib` | `number` | `16` | Memory of a flexible shape; ignored for fixed shapes; at least 1. |
| `ocpus` | `number` | `2` | OCPUs of a flexible shape (one OCPU is two vCPUs on x86); ignored for fixed shapes. |
| `preemptible` | `bool` | `false` | Preemptible capacity; workers only. |
| `public_ip` | `bool` | `false` | A public IP on the VNIC; needs a public subnet. |
| `pv_encryption_in_transit` | `bool` | `true` | Encrypt boot volume traffic in transit. |
| `shape` | `string` | `"VM.Standard.E5.Flex"` | Compute shape. |
| `ssh_authorized_keys` | `list(string)` | `[]` | SSH public keys for the image's default user. |
| `subnet_id` | `string` | `null` | Subnet of the VNIC; `null` uses the cluster's control-plane or worker subnet. |

The image's `io.captf.capacity` label (`{"cpu":"4","memory":"16Gi"}`,
`amd64`) describes the default shape, for Cluster Autoscaler scale from
zero. A template that changes the shape needs an image built with matching
labels.

## Outputs

| Output | Value |
| --- | --- |
| `provider_id` | `oci://<instance OCID>`, the format the OCI cloud controller manager writes (`ProviderName() + "://" + InstanceID`, [ccm.go](https://github.com/oracle/oci-cloud-controller-manager/blob/v1.36.0/pkg/cloudprovider/providers/oci/ccm.go)) |
| `addresses` | `InternalIP` (the primary private IP) and `ExternalIP` (the public IP, when there is one), as the cloud controller manager reports them |
| `failure_domain` | The requested failure domain, or the one picked from `machine_name` |
| `interruptible` | `true` for a preemptible instance |
| `health` | From the instance's lifecycle state (below) |

A requested failure domain must be one of the cluster's; the instance goes
to its availability domain and, in fault-domain mode, its fault domain.
Without one, the module picks from the sorted names by the sha256 of
`machine_name`, so a new plan never moves the machine.

## Health

| Instance state | Contract state | Reason |
| --- | --- | --- |
| `PROVISIONING`, `STARTING` | `pending` | `InstanceProvisioning`, `InstanceStarting` |
| `RUNNING`, `MOVING` (live migration) | `running` | none |
| `CREATING_IMAGE` | `unknown` | `InstanceCreatingImage` |
| `STOPPING`, `STOPPED` | `stopped` | `InstanceStopping`, `InstanceStopped` |
| `TERMINATING`, `TERMINATED`, or gone from state | `terminated` | `InstanceNotFound` |
| anything else | `unknown` | `UnknownState` |

The provider drops a `TERMINATED` instance from state when it reads it; the
instance is counted, so the module still reads that as `terminated`.

## Lifecycle

A machine never updates in place. A change to its bootstrap data or SSH keys
replaces the instance (the provider forces it), which is what an immutable
`Machine` expects; CAPI rolls machines through a new template instead.
Destroying a control-plane machine removes its load balancer backends with
it.

## Bootstrap

- **Delivery.** `metadata.user_data` is `bootstrap_data` unchanged, since
  OCI takes user data base64-encoded: cloud-config (CABPK's Jinja header
  included), Ignition and gzipped cloud-config alike. Gzipped Ignition is
  refused.
- **Size.** Instance metadata, user data and SSH keys together, may hold
  32,000 bytes; a precondition stops a larger payload.
- **Who can read it.** The instance itself through its metadata service,
  and any principal that may read instances in the compartment through the
  OCI API. The cluster's node policy grants that to control-plane instances
  only, which hold the cluster's keys anyway. A control-plane payload holds
  the cluster's CA keys; OCI has no store the module stages it in yet.

## Limitations

- **Preemptible capacity** is refused for control-plane machines.
- **Backend registration** follows the instance once it is `RUNNING`, a
  network load balancer work request that typically takes a minute or two;
  the backend takes traffic once its TCP health check passes. That is
  inside the time `kubeadm init` and `join` take, but not yet verified.

## Exceptions

- `display_name` is `machine_name` rather than a hashed name: the cloud
  controller manager matches nodes by it.
- The control-plane payload is not staged in a secret store; it goes in
  instance metadata, as [Bootstrap](#bootstrap) describes. OCI Vault secrets
  read by the instance principal could serve as the store.

## Example

```yaml title="terraformmachinetemplate.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachineTemplate
metadata:
  name: demo-md-0
spec:
  template:
    spec:
      source:
        image: ghcr.io/captf-io/oci-machine:v0.1.0-opentofu
      variables:
        image_id: ocid1.image.oc1.iad.<id>
        boot_volume_size_gib: 200
```

Set `provider-id: oci://{{ v1.instance_id }}` and `cloud-provider: external`
in the bootstrap configuration's `kubeletExtraArgs`, as the cluster repository's
[example](https://github.com/captf-io/terraform-oci-cluster/blob/main/examples/cluster-kubeadm.yaml)
does.
