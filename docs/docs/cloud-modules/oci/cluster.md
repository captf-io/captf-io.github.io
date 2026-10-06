---
description: "Look up what the OCI cluster module creates, its inputs, outputs, health reporting and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/network
subtitle: "VCN, subnets, load balancer"
---

# Cluster

The `ghcr.io/captf-io/module-images/oci-cluster` image implements the
[cluster role](../../module-author/contract/v1alpha1/cluster.md) for a
`TerraformCluster` on OCI. It creates the nodes' network security groups,
the API network load balancer and the control-plane nodes' instance
identity on the VCN you bring, and publishes the endpoint, the failure
domains and the ids the machine and machinepool roles need.

The module's source is
[`captf-io/terraform-oci-cluster`](https://github.com/captf-io/terraform-oci-cluster),
published on the Terraform Registry as
[`captf-io/cluster/oci`](https://registry.terraform.io/modules/captf-io/cluster/oci).

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `oci_core_network_security_group.control_plane_nsg` and its rules | Control-plane nodes: everything from both node NSGs, the API backend ports from the load balancer NSG, ICMP 3/4 (path MTU) from the VCN, SSH from `ssh_allowed_cidrs` | Always |
| `oci_core_network_security_group.worker_nsg` and its rules | Workers: everything from both node NSGs, ICMP 3/4 from the VCN, NodePorts 30000-32767 from `nodeport_allowed_cidrs`, SSH from `ssh_allowed_cidrs` | Always |
| `oci_network_load_balancer_network_load_balancer.api_load_balancer` | The API endpoint, private unless `api_load_balancer_public` | No `control_plane_endpoint` input |
| `oci_core_network_security_group.api_load_balancer_nsg` and its rules | The API ports from the VCN and `api_allowed_cidrs`, forwarded to the control-plane NSG | Same |
| `oci_network_load_balancer_backend_set.api_backend_sets`, `oci_network_load_balancer_listener.api_listeners` | `kube-apiserver`, and `rke2-supervisor` on 9345 with RKE2; TCP health checks | Same |
| `terraform_data.api_endpoint_guard` | Fails any plan that would move the endpoint | Same |
| `oci_identity_dynamic_group.node_dynamic_group` | The control-plane instances, by defined tag, in the tenancy | `node_identity.enabled` (default) |
| `oci_identity_policy.node_policy` | What the cloud controller manager and CSI controller need | Same |

It lists the subnets and VCNs of the network compartment and picks the
cluster's by OCID, reads the region's availability domains (and, in
fault-domain mode, the fault domains), and reads the tenancy's region
subscriptions to find the home region, where IAM writes go. Every subnet
must be found, `AVAILABLE`, in one VCN, and regional or in the
control-plane subnet's availability domain; these checks are preconditions,
so a destroy skips them.

The node policy grants the dynamic group, in the cluster's compartment,
`read instance-family`, `manage load-balancers`,
`manage network-load-balancers` and `manage volume-family`, plus
`use virtual-network-family` in each network compartment. A statement about
the root compartment reads `in tenancy`.

## Inputs

Contract inputs used: `captf_cluster` (names), `captf_tags`,
`control_plane_endpoint` (skips the load balancer) and `cluster_network`
(`api_server_port`). `captf_contract` is validated; `captf_object`,
`kubernetes_version`, `control_plane_initialized` and
`captf_cluster_outputs` are declared and unused.

User variables, from
[variables.tf](https://github.com/captf-io/terraform-oci-cluster/blob/main/variables.tf):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_tags` | `map(string)` | `{}` | Extra free-form tags for every taggable resource. At most 4 entries; keys 1 to 100 printable ASCII characters without periods or spaces and not starting with `captf_io/` (case-insensitive), values at most 256. |
| `api_allowed_cidrs` | `list(string)` | `[]` | CIDRs that may reach the API endpoint besides the VCN's own; required with a public load balancer. |
| `api_load_balancer_private_ip` | `string` | `null` | Private IPv4 address of the load balancer, from its subnet; `null` lets OCI pick. |
| `api_load_balancer_public` | `bool` | `false` | Give the load balancer a public IP; requires `api_allowed_cidrs`. |
| `api_load_balancer_reserved_public_ip_id` | `string` | `null` | OCID of a reserved public IP for a public load balancer. |
| `api_load_balancer_subnet_id` | `string` | `null` | Subnet of the load balancer; `null` uses `control_plane_subnet_id`. A public load balancer needs a public subnet. |
| `compartment_id` | `string` | `null` | Required. Compartment of every cluster resource, machines and pools included. |
| `control_plane_subnet_id` | `string` | `null` | Required. Subnet of the control-plane nodes; its VCN is the cluster's. |
| `distribution` | `string` | `"kubeadm"` | `kubeadm` or `rke2`: RKE2 adds the supervisor listener on 9345 and puts the kube-apiserver backends on 6443. |
| `failure_domain_mode` | `string` | `"auto"` | `availability_domain`, `fault_domain` (of one availability domain), or `auto`. |
| `home_region` | `string` | `null` | The tenancy's home region for IAM writes; `null` looks it up. |
| `ignore_defined_tags` | `list(string)` | `[]` | Tag-default keys (`<namespace>.<key>`) to leave alone, besides `Oracle-Tags.CreatedBy` and `Oracle-Tags.CreatedOn`. At most 98 entries (the provider allows 100, and those two take the rest). |
| `network_compartment_id` | `string` | `null` | Compartment of the VCN and its subnets; `null` uses `compartment_id`. |
| `node_identity` | `object({enabled = optional(bool, true), defined_tag = optional(object({namespace = string, key = string})), allow_compartment_wide = optional(bool, false)})` | `{}` | Instance-principal identity for the control-plane nodes. `defined_tag` scopes the dynamic group to this cluster's control-plane instances; it is required unless `enabled = false` or `allow_compartment_wide = true`. |
| `node_policy_compartment_id` | `string` | `null` | Where the node policy is attached; `null` uses `compartment_id`. Set an ancestor of both when the VCN is in another compartment. |
| `nodeport_allowed_cidrs` | `list(string)` | `[]` | CIDRs that may reach worker NodePorts (TCP and UDP). |
| `region` | `string` | `null` | Required. Region identifier, such as `us-ashburn-1`; machines and pools inherit it. |
| `ssh_allowed_cidrs` | `list(string)` | `[]` | CIDRs that may reach the nodes on SSH. |
| `tenancy_id` | `string` | `null` | Tenancy of the dynamic group; `null` reads the identity's `OCI_TENANCY_OCID` file. |
| `worker_subnet_id` | `string` | `null` | Subnet of the workers, in the same VCN; `null` uses `control_plane_subnet_id`. |

## Outputs

| Output | Value |
| --- | --- |
| `control_plane_endpoint` | The `control_plane_endpoint` input when given; otherwise the load balancer's IPv4 address (public when `api_load_balancer_public`, else private) and the API port |
| `failure_domains` | One entry per availability domain, or per fault domain of the one availability domain; all accept control-plane machines |
| `exports` | Schema `captf.io/oci-cluster/v1`; see [Exports](README.md#exports) |
| `health` | From the load balancer's lifecycle state (below) |
| `api_load_balancer_id` | Extra: OCID of the network load balancer; `null` with a user endpoint |
| `node_dynamic_group_id` | Extra: OCID of the dynamic group, for your own policy statements |
| `node_policy_id` | Extra: OCID of the node policy |

An availability domain's failure domain name is the part after its tenancy
prefix (`Uocm:US-ASHBURN-AD-1` becomes `US-ASHBURN-AD-1`), the zone the OCI
cloud controller manager reports. Fault domains keep OCI's names
(`FAULT-DOMAIN-1`). An AD-specific control-plane subnet confines the cluster
to the fault domains of its availability domain.

## Health

| Load balancer state | Contract state | Reason |
| --- | --- | --- |
| `ACTIVE`, `UPDATING` (each backend change updates it) | `running` | none |
| `CREATING` | `pending` | `LoadBalancerCreating` |
| `FAILED` | `degraded` | `LoadBalancerFailed` |
| `DELETING`, `DELETED`, or gone from state | `terminated` | `LoadBalancerNotFound` |
| anything else | `unknown` | `UnknownState` |

With a user-supplied endpoint there is no load balancer to observe, and the
cluster reports `running`.

## Limitations

!!! danger "Control-plane metadata holds the cluster's CA keys"

    The policy lets
    control-plane instances read any instance's metadata in the compartment,
    so control-plane nodes of another cluster there can read this cluster's
    keys. Keep one compartment per cluster, and block pod access to the
    metadata service on control-plane nodes.

- **The endpoint is fixed** once the load balancer exists: the endpoint
  guard refuses any change to the inputs behind it (see
  [API endpoint](README.md#api-endpoint)).
- **The policy covers the compartment.** Control-plane nodes can manage
  every load balancer and volume in it. Workers get no OCI permissions.
- **The cloud controller manager needs no `manage security-lists`** only
  with `securityListManagementMode: None`; open Service NodePorts with
  `nodeport_allowed_cidrs`.
- **A deleted node NSG** leaves the cluster's exports incomplete until the
  next cluster apply recreates it. Machines and pools re-rendered in the
  meantime fail their exports checks.
- **IAM changes propagate within minutes**, so the first nodes may retry
  their first OCI calls.
- **The dynamic group goes in the Default identity domain**, through the
  classic IAM API.

## Exceptions

- Two rules are open by default besides node-to-node traffic and the API
  port from the load balancer: ICMP type 3 code 4 from the VCN, so path MTU
  discovery works, and, with a user-supplied endpoint, the API backend ports
  from the VCN and `api_allowed_cidrs`, since that endpoint reaches the
  nodes directly.
- With the network gone, the network security groups carry a placeholder
  VCN id, because OpenTofu's destroy still evaluates required arguments.
  Any other plan stops at the subnet checks first.

## Example

```yaml title="terraformcluster.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformCluster
metadata:
  name: demo
spec:
  source:
    image: ghcr.io/captf-io/module-images/oci-cluster:v0.1.0-opentofu
  identityRef:
    name: oci
  defaults:
    identityRef:
      name: oci
  variables:
    compartment_id: ocid1.compartment.oc1..<id>
    region: us-ashburn-1
    control_plane_subnet_id: ocid1.subnet.oc1.iad.<id>
    worker_subnet_id: ocid1.subnet.oc1.iad.<id>
    node_identity:
      defined_tag:
        namespace: captf
        key: cluster
```
