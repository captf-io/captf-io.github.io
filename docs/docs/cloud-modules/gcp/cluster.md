---
description: "Look up what the Google Cloud cluster module creates, its inputs, outputs, health reporting and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/network
subtitle: "VPC, firewall, load balancer"
---

# Cluster

The `ghcr.io/captf-io/gcp-cluster` image implements the
[cluster role](../../module-author/contract/v1alpha1/cluster.md) for a
`TerraformCluster` on Google Cloud. It creates the API load balancer, the
firewall rules and the node service accounts in the network you bring, and
publishes the endpoint, one failure domain per zone and the exports the
machine and machinepool roles read.

The module's source is
[`captf-io/terraform-google-cluster`](https://github.com/captf-io/terraform-google-cluster),
published on the Terraform Registry as
[`captf-io/cluster/google`](https://registry.terraform.io/modules/captf-io/cluster/google).

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `google_service_account.node_service_accounts` | Control-plane and worker node service accounts | Each one unless `control_plane_service_account` or `worker_service_account` brings it |
| `google_project_iam_member.node_project_roles` | `control_plane_roles` and `worker_roles` on the project | For the accounts the module created |
| `google_service_account_iam_member.node_service_account_users` | `roles/iam.serviceAccountUser` for the control-plane account, so the PD CSI controller can attach disks | On each account the module created |
| `google_compute_firewall.node_internal_firewall` | Every protocol between the node service accounts | Always |
| `google_compute_firewall.pod_ingress_firewalls` | Pod CIDRs to the nodes, one rule per address family | When `Cluster.spec.clusterNetwork.pods` is set |
| `google_compute_firewall.api_ingress_firewall` | API backend ports on control-plane nodes from the load balancer and Google's health checkers | Without a user endpoint |
| `google_compute_instance_group.api_instance_groups` | One unmanaged instance group per zone, the API backends | Without a user endpoint |
| `terraform_data.api_endpoint_guard` | Records what decides the endpoint and fails a plan that would change it | Without a user endpoint |
| `google_compute_address.api_address` | The internal API address, shared by both listeners | Internal endpoint (default) |
| `google_compute_region_health_check.api_region_health_checks` | One TCP health check per listener | Internal endpoint |
| `google_compute_region_backend_service.api_region_backend_services` | One `INTERNAL_MANAGED` backend service per listener, over every zone's instance group | Internal endpoint |
| `google_compute_region_target_tcp_proxy.api_region_target_tcp_proxies` | One target proxy per listener | Internal endpoint |
| `google_compute_forwarding_rule.api_forwarding_rules` | One forwarding rule per listener, on the API address | Internal endpoint |
| `google_compute_global_address.api_global_address` | The public API address | `api_load_balancer_public` |
| `google_compute_security_policy.api_security_policy` | Cloud Armor allowlist of `api_allowed_cidrs`, deny for everyone else | `api_load_balancer_public` |
| `google_compute_health_check.api_health_checks` | One TCP health check per listener | `api_load_balancer_public` |
| `google_compute_backend_service.api_backend_services` | One `EXTERNAL_MANAGED` backend service per listener | `api_load_balancer_public` |
| `google_compute_target_tcp_proxy.api_target_tcp_proxies` | One target proxy per listener | `api_load_balancer_public` |
| `google_compute_global_forwarding_rule.api_global_forwarding_rules` | One forwarding rule per listener, on the public address | `api_load_balancer_public` |

The listeners are `kube_apiserver` and, with `distribution = "rke2"`,
`rke2_supervisor` on port 9345. Backend services have a 3600-second idle
timeout: a TCP proxy's default of 30 seconds cuts idle watches and
`kubectl logs -f`.

The role reads the provider's project and region, the node subnetwork and
the proxy-only subnets through listings, and the region's zones. It does
not read the network: its self link is built from `network` and
`network_project`.

## Inputs

Contract inputs it uses:

- `captf_cluster`: names and descriptions.
- `captf_tags`: labels.
- `control_plane_endpoint`: a non-null value means no load balancer.
- `cluster_network`: `pods` for the pod firewall rules, `api_server_port`
  for the endpoint's port.

`captf_contract` is validated; `captf_object`, `kubernetes_version`,
`control_plane_initialized` and `captf_cluster_outputs` are declared and
unused.

User variables, set with `spec.variables`
([variables.tf](https://github.com/captf-io/terraform-google-cluster/blob/main/variables.tf)):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_tags` | `map(string)` | `{}` | Extra GCP labels for every labelable resource. Keys and values must already be valid GCP labels; the `captf-io_` keys are reserved for `captf_tags`, which win. At most 58 labels; keys match `^[a-z][a-z0-9_-]{0,62}$`, values `^[a-z0-9_-]{0,63}$`. |
| `api_allowed_cidrs` | `list(string)` | `[]` | Client CIDRs allowed to reach the public API endpoint, enforced by a Cloud Armor policy. Required when `api_load_balancer_public` is true; include the Cloud NAT egress addresses so nodes can reach the endpoint. |
| `api_global_access` | `bool` | `false` | Let clients in any region of the VPC reach the internal API endpoint. Off by default: only clients in the cluster's region can. |
| `api_load_balancer_public` | `bool` | `false` | Serve the API through a global external proxy load balancer instead of the internal one. Off by default; requires `api_allowed_cidrs`. |
| `control_plane_roles` | `list(string)` | `["roles/compute.instanceAdmin.v1", "roles/compute.loadBalancerAdmin", "roles/compute.securityAdmin", "roles/compute.storageAdmin", "roles/compute.viewer", "roles/logging.logWriter", "roles/monitoring.metricWriter"]` | Project roles for a module-created control-plane service account: what cloud-provider-gcp and the PD CSI controller need. Ignored with `control_plane_service_account`. |
| `control_plane_service_account` | `string` | `null` | Email of an existing service account for control-plane nodes. Null creates one with `control_plane_roles`. |
| `distribution` | `string` | `"kubeadm"` | Kubernetes distribution of the control plane: `kubeadm`, or `rke2`, which adds the RKE2 supervisor port 9345 on the API address and always uses kube-apiserver port 6443 on the nodes. |
| `network` | `string` | `null` | Name of the existing VPC network the cluster runs in. Required. |
| `network_project` | `string` | `null` | Project that owns the network: the host project of a Shared VPC. Null means the cluster's own project. Firewall rules are created here. |
| `project` | `string` | `null` | Project to create the cluster in. Null uses the provider's project: `GOOGLE_PROJECT` from the identity Secret, or the credentials' project. |
| `region` | `string` | `null` | Region of the cluster. Null uses the provider's region: `GOOGLE_REGION` from the identity Secret. |
| `subnetwork` | `string` | `null` | Name of the existing regional subnetwork, in `network`, that nodes and the internal API address use. Required. |
| `worker_roles` | `list(string)` | `["roles/logging.logWriter", "roles/monitoring.metricWriter"]` | Project roles for a module-created worker service account: logs and metrics only. Ignored with `worker_service_account`. |
| `worker_service_account` | `string` | `null` | Email of an existing service account for worker nodes. Null creates one with `worker_roles`. |
| `zones` | `list(string)` | `[]` | Zones of the region to use as failure domains. Empty means every zone of the region; set it when the machine type is not offered everywhere. |

## Outputs

| Output | Value |
| --- | --- |
| `control_plane_endpoint` | The user's endpoint when given; else the API address (internal or global) and `cluster_network.api_server_port`, 6443 by default |
| `failure_domains` | One per zone: `{name = <zone>, control_plane = true, attributes = {zone = <zone>}}`. The zones are `zones`, or every zone of the region |
| `exports` | The [exports](README.md#exports) object, schema `captf.io/gcp-cluster/v1` |
| `health` | Below |

Extra outputs, for operators and the tests:

| Output | Value |
| --- | --- |
| `api_address_id` | ID of the internal or global API address; null with a user endpoint |
| `api_backend_service_ids` | IDs of the backend services, by listener |
| `api_forwarding_rule_ids` | IDs of the forwarding rules, by listener |
| `api_instance_group_ids` | IDs of the per-zone instance groups, by zone |
| `firewall_rule_ids` | IDs of the firewall rules, by purpose |
| `node_service_account_ids` | IDs of the module-created node service accounts, by node role |
| `proxy_subnet_cidrs` | Ranges of the proxy-only subnets the API firewall rule allows |

## Health

From the cluster's own resource, the `kube_apiserver` forwarding rule:

| Situation | Contract state | Reason |
| --- | --- | --- |
| User endpoint: no load balancer | `running`, healthy | none |
| The forwarding rule exists | `running`, healthy | none |
| A refresh no longer finds the forwarding rule | `terminated` | `LoadBalancerNotFound` |

## Limitations

!!! warning "The endpoint is fixed once the load balancer exists"

    The endpoint is fixed once the load balancer exists; the endpoint guard
    refuses a later change of `api_load_balancer_public`, `network`,
    `subnetwork`, `project`, `region`, the API port or the address. Revert the
    change, or create a new cluster.

- With a user endpoint the module creates no instance groups, so
  control-plane machines join nothing.
- Removing a zone from `zones` fails while control-plane machines are still
  members of its instance group. Machine pools without their own failure
  domains keep the zones they were created with.
- With a brought worker service account and a module-created control-plane
  account, grant the control-plane account `roles/iam.serviceAccountUser`
  on the worker account yourself; the module grants it only on accounts it
  created.
- In a Shared VPC the module binds `control_plane_roles` in `project` only;
  cloud-provider-gcp also needs `roles/compute.loadBalancerAdmin` and
  `roles/compute.securityAdmin` in the host project.
- No SSH firewall rule and no external addresses: use OS Login with IAP TCP
  forwarding or a bastion of your own.
- The API address has no `prevent_destroy`, which would block deleting the
  cluster too; the endpoint guard and the
  [destructive-plan guard](../../concepts/approvals/destructive-guard.md)
  catch a replacement.

## Exceptions

- `exports.api` carries per-zone `instance_groups` instead of one
  registration target per listener keyed `kube_apiserver` and
  `rke2_supervisor`: a Google Cloud backend is an instance group, and one
  group serves both listeners.

## Example

```yaml title="terraformcluster.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformCluster
metadata:
  name: demo
  namespace: team-a
spec:
  source:
    image: ghcr.io/captf-io/gcp-cluster:v0.1.0-opentofu
  identityRef:
    name: gcp
  defaults:
    identityRef:
      name: gcp
  variables:
    network: captf-vpc
    subnetwork: captf-nodes
```
