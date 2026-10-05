---
description: "Build a workload cluster on an OpenStack network you bring: the images, prerequisites, identity Secret, quick start, endpoint, exports and tags."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/container
subtitle: "Octavia LB, Nova servers"
---

# OpenStack

The OpenStack modules provision a cluster on a network and subnet you
bring. The cluster role creates the node and control-plane security groups,
an Octavia load balancer for the Kubernetes API (internal by default) and a
Nova server group that spreads the control plane; the machine role creates
one Nova server per `Machine` on a Neutron port of that subnet and adds
control-plane servers to the API pools before they boot. The code lives in
two repositories, one per role:
[`terraform-openstack-cluster`](https://github.com/captf-io/terraform-openstack-cluster) and
[`terraform-openstack-machine`](https://github.com/captf-io/terraform-openstack-machine),
published on the Terraform Registry as
[`captf-io/cluster/openstack`](https://registry.terraform.io/modules/captf-io/cluster/openstack) and
[`captf-io/machine/openstack`](https://registry.terraform.io/modules/captf-io/machine/openstack).
The images are built by
[`captf-io/module-images`](https://github.com/captf-io/module-images),
which pins a release of these modules for each image.
The modules are pre-release; see the status note in
[Cloud Modules](../README.md).

OpenStack has no machinepool role: it has no native scaling group, so use a
`MachineDeployment` of individual machines.

<div class="grid cards" markdown>

-   :material-lan:{ .lg .middle } __Cluster__

    ---

    The API endpoint, security rules, node identities and exports of one workload cluster.

    [:octicons-arrow-right-24: Cluster](cluster.md)

-   :material-server:{ .lg .middle } __Machine__

    ---

    One instance per `Machine`, registered with the API load balancer.

    [:octicons-arrow-right-24: Machine](machine.md)

</div>

## Images

| Role | Image | Page |
| --- | --- | --- |
| cluster | `ghcr.io/captf-io/openstack-cluster` | [Cluster](cluster.md) |
| machine | `ghcr.io/captf-io/openstack-machine` | [Machine](machine.md) |

The machine image carries no `io.captf.capacity` or `io.captf.node-info`
label: `flavor_name` has no default, so there is no default node size to
describe. For Cluster Autoscaler scale-from-zero, set the
`capacity.cluster-autoscaler.kubernetes.io/*` annotations on the
`MachineDeployment` instead.

## Prerequisites

- **Network.** An existing Neutron network and subnet, IPv4 or IPv6, with
  DHCP and a router, routed to wherever the nodes pull images from. The
  management cluster must reach the subnet: the API endpoint is an internal
  VIP on it unless you make it public. A public endpoint also needs an
  external network to take the floating IP from, and a gateway on the
  subnet's router.
- **Services.** Nova, Neutron with security groups and resource tags,
  Glance, and Octavia with the amphora provider. Octavia API 2.12 or later
  for `api_allowed_cidrs`.
- **Permissions.** An application credential of a user with the `member`
  role in the project. Clouds still on Octavia's legacy policy also require
  `load-balancer_member`. The credential needs no unrestricted flag: the
  modules create no credentials.
- **Node images.** A Glance image with cloud-init (or Ignition) and the
  kubelet, kubeadm or RKE2 and container runtime your bootstrap provider
  expects, for example one built with
  [image-builder](https://image-builder.sigs.k8s.io/capi/providers/openstack).
  The image must take its hostname from the metadata service or config
  drive, so that the Node name equals the server name.
- **Cloud controller manager.** Install the
  [OpenStack cloud controller manager](https://github.com/kubernetes/cloud-provider-openstack)
  in the workload cluster, with a `cloud.conf` and a second, dedicated
  application credential you supply: the modules create no node identity.
  The cluster repository's
  [`examples/cloud-controller-manager.yaml`](https://github.com/captf-io/terraform-openstack-cluster/blob/main/examples/cloud-controller-manager.yaml)
  delivers both with a ClusterResourceSet. Keep its `manage-security-groups`
  off: it would edit the node ports' security groups behind the machine
  role. For volumes, install
  [Cinder CSI](https://github.com/kubernetes/cloud-provider-openstack/tree/master/docs/cinder-csi-plugin)
  with the same `cloud.conf`.

## Identity Secret

The provider reads its credentials from a `clouds.yaml` file in the
identity Secret; the provider block sets nothing but the region. See
[Identities and Credentials](../../user-guide/identities.md) for how the
keys reach a Job.

| Key | Example | Purpose |
| --- | --- | --- |
| `OS_CLOUD` | `openstack` | The `clouds.yaml` entry to use |
| `OS_CLIENT_CONFIG_FILE` | `/var/run/captf/credentials/clouds.yaml` | Where the provider finds `clouds.yaml` |
| `clouds.yaml` | an application credential entry | Mounted as a file at that path |
| `cacert.pem` | PEM bundle | Optional: a private CA, named by `cacert` in `clouds.yaml` |

The plain `OS_AUTH_URL`, `OS_APPLICATION_CREDENTIAL_ID`,
`OS_APPLICATION_CREDENTIAL_SECRET`, `OS_REGION_NAME` and `OS_CACERT` keys
work too.

```yaml title="identity.yaml"
apiVersion: v1
kind: Secret
metadata:
  name: openstack
  namespace: captf-system
type: Opaque
stringData:
  OS_CLOUD: openstack
  OS_CLIENT_CONFIG_FILE: /var/run/captf/credentials/clouds.yaml
  clouds.yaml: |
    clouds:
      openstack:
        auth_type: v3applicationcredential
        auth:
          auth_url: https://keystone.example.com:5000/v3
          application_credential_id: <application-credential-id>
          application_credential_secret: <application-credential-secret>
        region_name: RegionOne
        interface: public
        identity_api_version: 3
---
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformClusterIdentity
metadata:
  name: openstack
spec:
  secretRef:
    name: openstack
    namespace: captf-system
  allowedNamespaces:
    list:
    - team-a
```

## Quick start

The cluster repository's
[`examples/`](https://github.com/captf-io/terraform-openstack-cluster/tree/main/examples)
holds clusterctl templates for each step.

1. Create the identity from `examples/identity.yaml`:

    ```sh
    export NAMESPACE=team-a OPENSTACK_AUTH_URL=https://keystone.example.com:5000/v3 \
      OPENSTACK_APPLICATION_CREDENTIAL_ID=<id> OPENSTACK_APPLICATION_CREDENTIAL_SECRET=<secret>
    clusterctl generate yaml --from examples/identity.yaml | kubectl apply -f -
    ```

2. Put the cloud controller manager's manifests in a ConfigMap and apply
   `examples/cloud-controller-manager.yaml`, with a second application
   credential; the file's header has the commands.
3. Generate the cluster from `examples/cluster-kubeadm.yaml`: a
   `TerraformCluster`, a `KubeadmControlPlane` of three machines and a
   `MachineDeployment` of two, with health checks for both.

    ```sh
    export CLUSTER_NAME=demo KUBERNETES_VERSION=v1.33.1 \
      OPENSTACK_SUBNET_ID=<subnet uuid> OPENSTACK_CONTROL_PLANE_FLAVOR=m1.large \
      OPENSTACK_FLAVOR=m1.large OPENSTACK_IMAGE_NAME=ubuntu-2404-kube-v1.33.1
    clusterctl generate yaml --from examples/cluster-kubeadm.yaml | kubectl apply -n "$NAMESPACE" -f -
    ```

4. Install a CNI once the API server answers. Nodes keep the
   `node.cloudprovider.kubernetes.io/uninitialized` taint until the cloud
   controller manager runs.

## API endpoint

The [shared behavior](../shared-behavior.md#the-api-endpoint) applies; on
OpenStack:

- **Internal.** The endpoint is the Octavia load balancer's VIP on
  `subnet_id`, one TCP listener per port: kube-apiserver on
  `Cluster.spec.clusterNetwork.apiServerPort`, and with RKE2 the supervisor
  on 9345. Listener idle timeouts are an hour, so watches, `kubectl exec`
  and `logs -f` survive.
- **Public.** `api_load_balancer_public = true` puts a floating IP from
  `floating_ip_pool` on the VIP port and makes it the endpoint host. It
  needs `api_allowed_cidrs`, which restricts the listeners; the node subnet
  is always added to them.
- **Hairpin.** The amphora provider source-NATs every client to its own
  address on the node subnet, so a control-plane node reaches itself
  through the VIP, and the control-plane security group admits the API
  port from the subnet. Through a public endpoint, nodes reach the floating
  IP via their router, which source-NATs them to its gateway address: put
  that address in `api_allowed_cidrs`, or the first control-plane node
  never reaches itself. The ovn provider rejects `api_allowed_cidrs` (a
  precondition stops that combination) and its hairpin is not verified.
- **Endpoint guard.** `terraform_data.api_endpoint_guard` records
  `subnet_id`, `api_load_balancer_public`, `floating_ip_pool`,
  `cluster_network.api_server_port` and the load balancer's actual
  provider, and fails a later plan that would change one.

## Exports

Schema `captf.io/openstack-cluster/v1`. Machines receive it as
`captf_cluster_outputs`.

| Key | Value |
| --- | --- |
| `schema` | `captf.io/openstack-cluster/v1` |
| `region` | The cluster's region, the machines' provider region |
| `network_id` | Network of `subnet_id` |
| `subnet_id` | `subnet_id` |
| `failure_domains` | One key per availability zone, each an empty object |
| `distribution` | `kubeadm` or `rke2` |
| `provider_id_format` | `default` or `regional` |
| `security_group_ids` | `control_plane` (control-plane and node group) and `worker` (node group) lists |
| `control_plane_server_group_id` | The server group control-plane machines join, or `null` |
| `node_allowed_address_cidrs` | The allowed address pairs of every node port |
| `api` | The endpoint `host` and `port`, and `pools` keyed `kube_apiserver` and `rke2_supervisor`, each `{id, port}` with the backend port; `null` with a supplied endpoint |

## Tags

The `captf_tags` keys and `additional_tags` map `/` to `:` in the key
(`captf.io:cluster`). Neutron and Octavia resources carry them as
`"<key>=<value>"` strings in `tags`; the Nova server carries them as
metadata, because a Nova tag holds at most 60 characters and no `/`. A pair
longer than 255 characters fails a precondition instead of being cut.

Not taggable in provider 3.4.0: security group rules, health monitors and
server groups. The boot-from-volume root volume is untagged too: Nova
creates it from the server's block device mapping, which takes no metadata.

??? note "Design notes"

    - **Bring your own network.** The modules create no network, subnet or
      router, so a cluster fits whatever network design the cloud already has.
    - **No node identity.** An application credential belongs to the user
      Terraform runs as, Keystone limits what one credential can create, and
      the secret would sit in state; so you supply the cloud controller
      manager's `cloud.conf`.
    - **Amphora by default.** Its source NAT gives the hairpin path the
      contract requires; `loadbalancer_provider = null` takes the cloud's
      default instead.
    - **Health from Octavia's provisioning status.** Cluster health reads the
      load balancer's `provisioning_status`, never `operating_status`, which
      follows the members.
    - **No image lookup.** The server takes `image_id` or `image_name`
      directly, and later image changes are ignored: a Glance data source would
      fail every refresh and destroy once the image is rotated out, and the
      provider rebuilds a server in place when its image changes.
    - **Register before boot.** The server depends on its pool members, so a
      control-plane machine is in the API pools before it boots.
    - **Bootstrap in user data.** OpenStack has no instance identity to fetch a
      staged payload with, so the control-plane payload, with the cluster CA
      keys, is readable from the metadata service; see
      [Machine](machine.md#bootstrap).

The evidence for each is in the roles' `DESIGN.md`:
[cluster](https://github.com/captf-io/terraform-openstack-cluster/blob/main/DESIGN.md) and
[machine](https://github.com/captf-io/terraform-openstack-machine/blob/main/DESIGN.md).

!!! warning "Not yet verified"

    - Octavia ovn provider: hairpin from a member to its own VIP, and the
      `SOURCE_IP_PORT` pool method.
    - Octavia tag limits, assumed equal to Neutron's.
    - How often a server refresh, and so a drift Job or destroy, fails while a
      server is in a transient Nova state (`REBOOT`, a resize, `RESCUE`).
    - The cloud controller manager's `manage-security-groups` editing node
      ports' groups.
    - Cinder and Nova availability zone names that differ, for boot volumes.
    - Octavia returning a listener's allowed CIDRs in sorted order.
    - Nodes reaching a public endpoint source-NATed to the router's gateway
      address.
    - The kubeadm templates' Node name equaling the server name; Nova cuts
      hostnames to 63 characters.
    - The cloud controller manager v1.34.1 manifests with the control-plane
      node selector changed to `""`.
    - Neutron's ML2/OVN driver counting allowed address pairs as security group
      members, which native pod routing relies on.
