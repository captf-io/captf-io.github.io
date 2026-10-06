---
description: "Look up what the OpenStack cluster module creates, its inputs, outputs, health reporting and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/network
subtitle: "Network, router, Octavia LB"
---

# Cluster

The `ghcr.io/captf-io/module-images/openstack-cluster` image implements the
[cluster role](../../module-author/contract/v1alpha1/cluster.md) for a
`TerraformCluster` on OpenStack. On the subnet you bring, it creates the
security groups of the nodes, the Octavia load balancer behind the
Kubernetes API, and a server group that spreads the control plane, and
publishes them to the machines through its `exports`.

The module's source is
[`captf-io/terraform-openstack-cluster`](https://github.com/captf-io/terraform-openstack-cluster),
published on the Terraform Registry as
[`captf-io/cluster/openstack`](https://registry.terraform.io/modules/captf-io/cluster/openstack).

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `openstack_networking_secgroup_v2.node_security_group` | Every node: all traffic from the cluster's nodes, NodePorts from the subnet, optional SSH, egress | Always |
| `openstack_networking_secgroup_v2.control_plane_security_group` | Control-plane nodes, on top of the node group: the API backend ports from the subnet | Always |
| `openstack_networking_secgroup_rule_v2.node_ingress_rules` | `any-from-nodes`, `nodeports-tcp`, `nodeports-udp`, one `ssh-from-<cidr>` per `ssh_allowed_cidrs` entry | Always |
| `openstack_networking_secgroup_rule_v2.node_egress_rules` | Egress anywhere, IPv4 and IPv6 | Always |
| `openstack_networking_secgroup_rule_v2.control_plane_ingress_rules` | `kube_apiserver-from-subnet`, and `rke2_supervisor-from-subnet` (TCP 9345) | Always; the second with `distribution = "rke2"` |
| `openstack_lb_loadbalancer_v2.api_load_balancer` | Octavia load balancer, VIP on `subnet_id` | Without a supplied endpoint |
| `openstack_lb_listener_v2.api_listeners` | TCP listeners: kube-apiserver; the RKE2 supervisor on 9345 | With the load balancer; the second with `rke2` |
| `openstack_lb_pool_v2.api_pools` | The pools control-plane machines join | One per listener |
| `openstack_lb_monitor_v2.api_monitors` | TCP health monitors | One per pool |
| `openstack_networking_floatingip_v2.api_floating_ip` | Floating IP on the VIP port, the endpoint host | With `api_load_balancer_public` |
| `openstack_compute_servergroup_v2.control_plane_server_group` | Server group of the control-plane machines | Unless `control_plane_server_group_policy` is `null` |
| `terraform_data.api_endpoint_guard` | Fails a plan that would move the endpoint | With the load balancer |

It reads the subnet (CIDR, address family, network, region) only while a
listing of visible subnets still shows it, so a destroy runs after the
subnet is gone; every other plan then fails a precondition naming
`subnet_id`. It reads Nova's available zones when `availability_zones` is
empty, and the load balancer's provisioning status for health.

## Inputs

Contract inputs used: `captf_contract` (validated), `captf_cluster`
(resource names, `captf-<namespace>-<name>-<hash>`), `captf_tags`,
`control_plane_endpoint` (non-null means no load balancer) and
`cluster_network` (`api_server_port` sets the API port, `pods` the
allowed address pairs). `captf_object`, `kubernetes_version` and
`control_plane_initialized` are declared and unused.

User variables, set in `TerraformCluster.spec.variables`
([Module Variables](../../user-guide/variables.md); source:
[variables.tf](https://github.com/captf-io/terraform-openstack-cluster/blob/main/variables.tf)):

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_tags` | `map(string)` | `{}` | Extra tags on every resource. At most 44; keys follow the Nova metadata key rule and must not start with `captf.io:`; keys are 1 to 255 characters; each `<key>=<value>` fits in 255 characters |
| `api_allowed_cidrs` | `list(string)` | `[]` | Clients the API listeners accept, of the subnet's address family. Empty: any client that can route to the VIP. Required with `api_load_balancer_public`; refused with the `ovn` provider. The node subnet is always added |
| `api_load_balancer_public` | `bool` | `false` | Put a floating IP on the VIP and use it as the endpoint |
| `availability_zones` | `list(string)` | `[]` | Nova zones to report as failure domains. At most 100 names, each 1 to 256 characters. Empty: every available zone |
| `control_plane_server_group_policy` | `string` | `"soft-anti-affinity"` | `soft-anti-affinity`, `anti-affinity`, or `null` for no server group |
| `distribution` | `string` | `"kubeadm"` | `kubeadm` or `rke2`, which adds the supervisor listener on 9345 |
| `floating_ip_pool` | `string` | `null` | External network for the floating IP. Required with `api_load_balancer_public` |
| `loadbalancer_provider` | `string` | `"amphora"` | Octavia provider; `null` takes the cloud's default |
| `node_allowed_address_cidrs` | `list(string)` | `[]` | Extra source CIDRs every node port may send from, for example a kube-vip address |
| `pod_address_pairs` | `bool` | `false` | Add the pod CIDRs to every node port's allowed address pairs, for CNIs that route pods without encapsulation |
| `provider_id_format` | `string` | `"default"` | `default` (`openstack:///<id>`) or `regional` (`openstack://<region>/<id>`); must match the cloud controller manager's `OS_CCM_REGIONAL` |
| `region` | `string` | `null` | OpenStack region; `null` takes the identity's region |
| `ssh_allowed_cidrs` | `list(string)` | `[]` | CIDRs allowed on TCP 22 of every node |
| `subnet_id` | `string` | `null` | **Required.** UUID of the subnet for the VIP and every node |

## Outputs

| Output | Value |
| --- | --- |
| `control_plane_endpoint` | The VIP, or the floating IP with `api_load_balancer_public`, on the API port; the supplied endpoint when one is given |
| `failure_domains` | One entry per availability zone, all eligible for the control plane, no attributes |
| `exports` | See [Exports](README.md#exports) |
| `health` | See below |
| `api_load_balancer_id` | Not a contract output: the Octavia load balancer's UUID, `null` without one |

## Health

From the load balancer's Octavia `provisioning_status`, re-read on every
refresh; `operating_status` follows the members, which are down during
every normal control-plane bring-up, and is not used.

| Octavia state | Contract state | Reason |
| --- | --- | --- |
| `ACTIVE` | `running`, healthy | none |
| `PENDING_UPDATE` | `running`, healthy | none: the load balancer keeps serving while a member is added |
| `PENDING_CREATE` | `pending` | `LoadBalancerPendingCreate` |
| `ERROR` | `degraded` | `LoadBalancerError` |
| `PENDING_DELETE` | `terminated` | `LoadBalancerPendingDelete` |
| `DELETED` | `terminated` | `LoadBalancerDeleted` |
| deleted outside Terraform | `terminated` | `LoadBalancerNotFound` |
| anything else | `unknown` | `LoadBalancerStatusUnknown` |

With a supplied endpoint the health is `running` and healthy: there is no
load balancer to observe.

## Limitations

!!! warning "Switching to a supplied endpoint plans the load balancer's destruction"

    On a cluster whose module created
    the load balancer plans its destruction; only the
    [destructive-plan guard](../../concepts/approvals/destructive-guard.md)
    stops it.

- **The endpoint is fixed.** `subnet_id`, `api_load_balancer_public`,
  `floating_ip_pool`, `cluster_network.api_server_port` and
  `loadbalancer_provider` cannot change once the load balancer exists.
- **No hosted control planes.** With no endpoint supplied, the module
  always creates a load balancer and reports its endpoint, which Cluster
  API copies first, so a control-plane provider that sets the endpoint
  itself later is not supported.
- **Failure domains follow availability.** Without `availability_zones`, a
  zone Nova marks unavailable drops out at the next refresh: pin the list
  for production clusters.
- **Rule changes replace rules.** Every security group rule attribute
  forces a new rule, so a changed CIDR plans a delete and a create, which
  the destructive-plan guard holds for approval.
- **A deleted subnet.** Plans other than a destroy fail a precondition
  until `subnet_id` names an existing subnet; a destroy still runs.
- **Octavia providers.** The module is designed for the amphora provider.
  The OVN provider rejects `api_allowed_cidrs`, so `api_load_balancer_public`
  is amphora-only, and it keeps client addresses, so only clients on the
  node subnet or in the node group pass the control-plane security group.
  See [API endpoint](README.md#api-endpoint).

## Exceptions

- NodePorts are open from the node subnet, beyond the API port: Octavia
  load balancers for Services of type `LoadBalancer` source-NAT from the
  subnet, and the alternative, the cloud controller manager's
  `manage-security-groups`, edits the node ports' groups behind the machine
  role.
- No `tfcapi-lint` warning is allowed.

## Example

```yaml title="terraformcluster.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformCluster
metadata:
  name: demo
spec:
  source:
    image: ghcr.io/captf-io/module-images/openstack-cluster:v0.1.0-opentofu
  identityRef:
    name: openstack
  defaults:
    identityRef:
      name: openstack
  variables:
    subnet_id: 5c1d7a0e-2b4f-4e83-9a61-0d8f3b2c4e71
```
