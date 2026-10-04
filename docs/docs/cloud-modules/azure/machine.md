---
description: "Look up what the Azure machine module creates, its inputs, outputs, health, lifecycle and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "Steven Crothers"
icon: lucide/server
subtitle: "One virtual machine"
---

# Machine

The `ghcr.io/captf-io/azure-machine` image implements the
[machine role](../../module-author/contract/v1alpha1/machine.md) on Azure:
one Linux VM per `Machine`, control plane or worker, in the cluster's
resource group. `control_plane` picks the subnet, identity and security
groups, and registers a control-plane VM with the API load balancer before
it boots.

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `azurerm_network_interface.node_network_interface` | The VM's NIC in the control-plane or worker subnet, with accelerated networking by default | Always |
| `azurerm_network_interface_security_group_association.node_security_group_association` | Puts the NIC under its role's network security group | Always |
| `azurerm_network_interface_application_security_group_association.node_application_security_group_association` | Makes the NIC a member of its role's application security group | Always |
| `azurerm_network_interface_backend_address_pool_association.api_backend_pool_association` | Registers the NIC in the API backend pool, in this machine's own state, so destroy deregisters it | Control-plane machines, unless the endpoint is your own |
| `azurerm_linux_virtual_machine.node_virtual_machine` | The node, with password login and VM extensions off and a user-assigned identity | Always |

The VM is created after the associations, so it boots in its security
groups and, on the control plane, behind the load balancer. Without exports
(an externally managed cluster and no `external_cluster_exports`) the role
creates nothing and fails a precondition.

## Inputs

Contract inputs used: `captf_cluster_outputs` (the cluster's exports),
`captf_tags`, `machine_name`, `bootstrap_data`, `bootstrap_format`,
`failure_domain`, `kubernetes_version` (fills `{version}` and `{semver}` in
`image_id`) and `control_plane`. `captf_contract` is validated;
`captf_cluster` and `captf_object` are not used.

User variables, set with `spec.template.spec.variables` on the
`TerraformMachineTemplate`
([variables.tf](https://github.com/captf-io/azure-modules/blob/main/machine/variables.tf)):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `accelerated_networking` | `bool` | `true` | Accelerated networking on the NIC; turn it off for a `vm_size` without it |
| `additional_tags` | `map(string)` | `{}` | Extra Azure tags on the VM and NIC. Keys starting with `captf.io_` or `captf.io/` (any case) are rejected; at most 44 |
| `boot_diagnostics` | `bool` | `true` | Keep the serial console log in Azure-managed storage. It shows boot output, which may include kubeadm's join command |
| `encryption_at_host` | `bool` | `false` | Encrypt temporary disks and caches on the host too; needs the `EncryptionAtHost` feature on the subscription. Managed disks are encrypted at rest either way |
| `external_cluster_exports` | `any` | `null` | Exports (schema `captf.io/azure-cluster/v1`) for an externally managed `TerraformCluster` |
| `image_id` | `string` | `null` | Required. A managed image, Compute Gallery image (version), or community or shared gallery image (version) ID. `{version}` and `{semver}` become the Machine's version, `v1.31.4` and `1.31.4`, without any `+suffix` |
| `ip_forwarding` | `bool` | `false` | IP forwarding on the NIC, for CNIs that route pod addresses natively |
| `os_disk_size_gib` | `number` | `128` | OS disk size, 30 to 4095 GiB |
| `os_disk_storage_account_type` | `string` | `"Premium_LRS"` | `Standard_LRS`, `StandardSSD_LRS`, `StandardSSD_ZRS`, `Premium_LRS` or `Premium_ZRS`; premium needs a `vm_size` with premium storage |
| `spot` | `bool` | `false` | A Spot VM, deallocated on eviction, at most the on-demand price, reported interruptible. A control-plane machine with `spot` fails a precondition |
| `trusted_launch` | `bool` | `false` | Secure boot and vTPM; needs a generation 2 image built for trusted launch, which the CAPZ reference images are not |
| `vm_size` | `string` | `"Standard_D4s_v5"` | Azure VM size. The image's capacity labels describe the default: 4 CPUs, 16 GiB, amd64 |

Community and shared gallery IDs are case-sensitive in azurerm 5.7.0:
`/communityGalleries/<gallery>/images/<image>/versions/<version>`.

## Outputs

| Output | Value |
| --- | --- |
| `provider_id` | `azure:///subscriptions/<subscription>/resourceGroups/<group, lowercase>/providers/Microsoft.Compute/virtualMachines/<VM name>`, the format [cloud-provider-azure](https://github.com/kubernetes-sigs/cloud-provider-azure/blob/release-1.34/pkg/provider/azure_standard.go) writes to the Node |
| `addresses` | `InternalIP`, the NIC's private address, and `Hostname`, the VM name |
| `failure_domain` | The VM's zone: the requested failure domain, else one picked from the `sha256` of `machine_name`; `null` without zones |
| `interruptible` | `true` for a Spot VM |
| `health` | See Health |
| `network_interface_id` | Extra: the NIC's ARM ID |
| `virtual_machine_id` | Extra: the VM's ARM ID |

cloud-provider-azure finds the VM by the Node's name, so the Node must be
named after the VM: set `nodeRegistration.name: '{{
ds.meta_data["local_hostname"] }}'` in the KubeadmConfig, as the examples
do. The VM and its hostname are `machine_name` when Azure accepts it (at
most 64 lowercase letters, digits and inner hyphens); any other name is
made valid, cut to 55 characters and suffixed with `-` and 8 hex characters
of its `sha256`. In a region without zones, control-plane VMs join the
cluster's availability set.

## Health

The module lists the VM first and reads its power state only when the
listing finds it, because Azure's VM read fails on a missing VM, which
would fail every refresh and destroy.

| Azure state | Contract state | Reason |
| --- | --- | --- |
| Power state `running` | `running`, healthy | none |
| `starting`, or no power state yet | `pending` | `PowerState/starting`, `PowerState/unknown` |
| `stopping`, `stopped`, `deallocating`, `deallocated` | `stopped` | `PowerState/<state>` |
| Any other power state | `unknown` | `UnknownState` |
| In the state but not listed yet (the first apply; listings lag) | `pending` | `VirtualMachineNotListed` |
| Gone (a refresh dropped it) | `terminated` | `VirtualMachineNotFound` |

The first apply therefore reports `pending`; the controller's next refresh,
30 seconds later, reads the power state. An evicted Spot VM is deallocated,
reports `stopped`, and a `MachineHealthCheck` replaces it.

## Bootstrap

- **Delivery.** The bootstrap data goes in the VM's custom data, never in
  user data, which Azure shows to every process on the node through the
  instance metadata service. `cloud-config` data is wrapped in a MIME
  multipart message: a boot hook first, then the payload as an opaque
  base64 part, never decoded by the module (`application/x-gzip` when it is
  gzipped). The boot hook writes `/etc/kubernetes/azure.json` for the node's
  identity when the file is absent and, on control-plane nodes, starts the
  [hairpin workaround](README.md#api-endpoint). Ignition goes in unchanged;
  gzipped Ignition fails a precondition.
- **Size limit.** Azure takes 65,535 bytes of custom data, 87,380 base64
  characters; a precondition stops a larger message. Compress the payload
  (CAPRKE2 `gzipUserData`) if a control-plane payload grows too big.
- **Who can read it.** Azure keeps custom data out of the instance metadata
  service and does not return it when the VM is read; on the node it sits in
  files only root reads. Like every input, it is also stored in the
  machine's state Secret on the management cluster. With `boot_diagnostics`
  on, the serial console log, readable by anyone who may read the VM's boot
  diagnostics, shows boot output.

## Limitations

- One NIC, one OS disk and no data disk: etcd shares the OS disk.
- No public IP; nodes reach the internet through the subnet's egress.
- Azure public cloud only.
- An image for `{semver}` must exist in the gallery for every version you
  roll to.

## Exceptions

None: `tfcapi-lint module --strict` passes without allowed warnings. One
trivy finding is ignored with its reason: AZU-0068 on the NIC, whose
security group is attached by a separate association resource. The tests
cannot cover the `terminated` reading, because a mock provider never drops
a resource on refresh.

## Example

```yaml title="terraformmachinetemplate.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachineTemplate
metadata:
  name: demo-md-0
  namespace: team-a
spec:
  template:
    spec:
      source:
        image: ghcr.io/captf-io/azure-machine:v0.1.0-opentofu
      variables:
        image_id: /communityGalleries/ClusterAPI-f72ceb4f-5159-4c26-a0fe-2ea738f0d019/images/capi-ubun2-2404/versions/{semver}
        vm_size: Standard_D8s_v5
        spot: true
```
