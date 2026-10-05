---
description: "Look up what the Azure cluster module creates, its inputs, outputs, health reporting and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/network
subtitle: "VNet, security group, LB"
---

# Cluster

The `ghcr.io/captf-io/azure-cluster` image implements the
[cluster role](../../module-author/contract/v1alpha1/cluster.md) on Azure.
It creates one resource group for the cluster and, in it, the API server
load balancer, the nodes' network security groups and application security
groups, and the nodes' managed identities with their role assignments. It
publishes the endpoint, one failure domain per availability zone, and the
[exports](README.md#exports) the machine and pool roles read.

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `azurerm_resource_group.cluster_resource_group` | The cluster's own group: scope of the node identities' rights, home of what cloud-provider-azure creates for Services | Always |
| `azurerm_user_assigned_identity.node_identities` | Managed identities of control-plane and worker nodes | Per role, unless you bring one (`control_plane_identity_id`, `worker_identity_id`) |
| `azurerm_role_assignment.node_role_assignments` | Contributor on the group and Network Contributor on the node subnets for the control-plane identity; AcrPull on each of `container_registry_ids` | For the identities the module creates |
| `azurerm_network_security_group.node_security_groups` | One per role, attached to each node's NIC | Always |
| `azurerm_network_security_rule.node_security_rules` | SSH denied unless from `ssh_allowed_cidrs`; all traffic between nodes; the API server ports and a final deny of the virtual network on the control plane | Always; the SSH allow only with `ssh_allowed_cidrs`, the CIDR allow only with `api_allowed_cidrs` |
| `azurerm_application_security_group.node_application_security_groups` | Name control-plane and worker NICs in the rules | Always |
| `azurerm_availability_set.control_plane_availability_set` | Spreads control-plane VMs over fault domains | In a region without availability zones |
| `azurerm_public_ip.api_public_ip` | Static Standard public IP of the endpoint | With `api_load_balancer_public` |
| `azurerm_lb.api_load_balancer` | Standard load balancer of the endpoint | Without a user endpoint |
| `azurerm_lb_backend_address_pool.api_backend_pool` | Control-plane machines join it from their own state | Without a user endpoint |
| `azurerm_lb_probe.api_probes` | HTTPS `/readyz` (kubeadm) or TCP probe, every 5 seconds | One per listener, without a user endpoint |
| `azurerm_lb_rule.api_rules` | The endpoint port to the kube-apiserver, and 9345 to 9345 with RKE2 | One per listener, without a user endpoint |
| `terraform_data.api_endpoint_guard` | Records what fixes the endpoint and fails a later plan that would move it | Without a user endpoint |

It reads the identity's tenant and subscription, and finds the brought
virtual network and any brought identities through subscription-wide
listings that come back empty instead of failing, so a network deleted
first never blocks a destroy ([Shared Behavior](../shared-behavior.md#destroy)).
Every other plan stops at a precondition naming what is missing.

## Inputs

Contract inputs used: `captf_cluster` (names), `captf_tags` (tags),
`control_plane_endpoint` (a user endpoint skips the load balancer) and
`cluster_network.api_server_port` (the endpoint port, default 6443; the
kube-apiserver backend port too with kubeadm, while RKE2's is always 6443).
`captf_contract` is validated; `captf_object`, `captf_cluster_outputs`,
`kubernetes_version` and `control_plane_initialized` are not used.

User variables, set with `spec.variables` on the `TerraformCluster`
([variables.tf](https://github.com/captf-io/azure-modules/blob/main/cluster/variables.tf)):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_tags` | `map(string)` | `{}` | Extra Azure tags on every taggable resource. Keys starting with `captf.io_` or `captf.io/` (any case) are rejected; at most 44 |
| `admin_ssh_public_key` | `string` | `null` | Required. OpenSSH public key (`ssh-rsa` or `ssh-ed25519`) of every node's admin user: Azure Linux VMs need a key or a password, and the module invents neither. SSH stays closed unless `ssh_allowed_cidrs` opens it |
| `api_allowed_cidrs` | `list(string)` | `[]` | IPv4 CIDRs, besides the virtual network, allowed to reach the API server ports. Required with `api_load_balancer_public`: include the management cluster's egress and the nodes' NAT gateway addresses |
| `api_load_balancer_private_ip` | `string` | `null` | Static private IPv4 address of the internal frontend, in the control-plane subnet. `null` takes a dynamic address, stable for the load balancer's life |
| `api_load_balancer_public` | `bool` | `false` | Put the API load balancer on a public IP |
| `api_server_hairpin_workaround` | `bool` | `true` | Control-plane nodes send their own traffic for the frontend to their local API server while it is ready ([API endpoint](README.md#api-endpoint)) |
| `container_registry_ids` | `list(string)` | `[]` | Azure Container Registry IDs the identities this module creates may pull from (AcrPull) |
| `control_plane_identity_id` | `string` | `null` | Existing user-assigned identity for control-plane nodes. It needs Contributor on the cluster's resource group and Network Contributor on the node subnets, which you grant |
| `distribution` | `string` | `"kubeadm"` | `kubeadm` or `rke2`. RKE2 adds the supervisor port 9345 to the load balancer and the control-plane security group, probes the API server with TCP, and fixes the kube-apiserver backend port at 6443 |
| `resource_group_name` | `string` | `null` | Name of the cluster's resource group, lowercase, because cloud-provider-azure lowercases it in provider IDs. `null` derives `captf-<namespace>-<cluster>-<hash>` |
| `ssh_allowed_cidrs` | `list(string)` | `[]` | IPv4 CIDRs allowed to reach SSH on every node, for example an Azure Bastion subnet. Empty: SSH is denied, between nodes too |
| `subnet_id` | `string` | `null` | Required. Existing subnet for control-plane nodes and the internal frontend, and for workers without `worker_subnet_id` |
| `worker_identity_id` | `string` | `null` | Existing user-assigned identity for worker nodes |
| `worker_subnet_id` | `string` | `null` | Existing subnet for worker nodes, in the same virtual network as `subnet_id`. `null` uses `subnet_id` |
| `zones` | `list(string)` | `[]` | Availability zones to publish as failure domains. Empty uses every zone of the region |

Subnet, identity and registry IDs are matched case-insensitively and
rebuilt with Azure's canonical segment names. Give resource group and
resource names in the casing Azure shows (`az network vnet subnet show
--query id`): role assignment scopes are compared case-sensitively.

## Outputs

| Output | Value |
| --- | --- |
| `control_plane_endpoint` | The user endpoint, or the frontend address (private, or the public IP) and the endpoint port |
| `failure_domains` | One entry per zone of the region (or of `zones`), eligible for the control plane; `[]` in a region without zones |
| `exports` | See [Exports](README.md#exports) |
| `health` | See Health |
| `api_load_balancer_id` | Extra: the load balancer's ARM ID; `null` with a user endpoint |
| `resource_group_id` | Extra: the resource group's ARM ID |

## Health

Cluster health comes from the cluster's own resources, never from the
control-plane nodes behind the load balancer.

| Azure state | Contract state | Reason |
| --- | --- | --- |
| Load balancer and frontend address present, or the resource group with a user endpoint | `running`, healthy | none |
| Load balancer or its frontend address gone | `terminated` | `LoadBalancerNotFound` |
| Resource group gone | `terminated` | `ResourceGroupNotFound` |

## Limitations

!!! warning "Destroy fails while cloud-provider-azure resources remain"

    Destroy fails while cloud-provider-azure's load balancers, public IPs or
    disks are still in the resource group: delete the cluster's
    `LoadBalancer` Services and `PersistentVolumes` first, or remove what is
    left by hand.

- The network, its egress, DNS and peering are yours.
- Azure public cloud only.
- The endpoint is an IP address; there is no DNS name.
- With `distribution = "rke2"` the endpoint port cannot be 9345, the
  supervisor's.

## Exceptions

None: `tfcapi-lint module --strict` passes without allowed warnings. The
tests cannot cover the `terminated` readings, because a mock provider never
drops a resource on refresh.

## Example

```yaml title="terraformcluster.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformCluster
metadata:
  name: demo
  namespace: team-a
spec:
  source:
    image: ghcr.io/captf-io/azure-cluster:v0.1.0-opentofu
  identityRef:
    name: azure
  defaults:
    identityRef:
      name: azure
  variables:
    subnet_id: /subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/network/providers/Microsoft.Network/virtualNetworks/hub/subnets/nodes
    admin_ssh_public_key: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample ops@example.com
```
