---
description: "Build a workload cluster in an Azure virtual network you bring: the images, prerequisites, identity Secret, quick start, endpoint, exports and tags."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/cloudy
subtitle: "Standard LB, VMs, scale sets"
---

# Azure

The Azure modules run a Kubernetes cluster on Azure virtual machines. The
cluster role creates one resource group per cluster, holding the API
server's Standard load balancer, the nodes' network security groups,
application security groups and managed identities with their role
assignments. The machine role creates one Linux VM per Machine, and the
machinepool role one virtual machine scale set per MachinePool. The source
is one repository per role:
[`terraform-azure-cluster`](https://github.com/captf-io/terraform-azure-cluster),
[`terraform-azure-machine`](https://github.com/captf-io/terraform-azure-machine) and
[`terraform-azure-machinepool`](https://github.com/captf-io/terraform-azure-machinepool),
published on the Terraform Registry as
[`captf-io/cluster/azure`](https://registry.terraform.io/modules/captf-io/cluster/azure),
[`captf-io/machine/azure`](https://registry.terraform.io/modules/captf-io/machine/azure) and
[`captf-io/machinepool/azure`](https://registry.terraform.io/modules/captf-io/machinepool/azure).
The images are built from
[`captf-io/azure-modules`](https://github.com/captf-io/azure-modules).
The modules are pre-release; read the status note in
[Cloud Modules](../README.md) first.

<div class="grid cards" markdown>

-   :material-lan:{ .lg .middle } __Cluster__

    ---

    The API endpoint, security rules, node identities and exports of one workload cluster.

    [:octicons-arrow-right-24: Cluster](cluster.md)

-   :material-server:{ .lg .middle } __Machine__

    ---

    One instance per `Machine`, registered with the API load balancer.

    [:octicons-arrow-right-24: Machine](machine.md)

-   :material-server-network:{ .lg .middle } __MachinePool__

    ---

    One native scaling group per `MachinePool`.

    [:octicons-arrow-right-24: MachinePool](machinepool.md)

</div>

## Images

| Role | Image | Page |
| --- | --- | --- |
| cluster | `ghcr.io/captf-io/azure-cluster` | [Cluster](cluster.md) |
| machine | `ghcr.io/captf-io/azure-machine` | [Machine](machine.md) |
| machinepool | `ghcr.io/captf-io/azure-machinepool` | [MachinePool](machinepool.md) |

The images carry `hashicorp/azurerm` 5.7.0, pinned exactly.

## Prerequisites

- **Network.** A virtual network with a subnet for the nodes, and
  optionally a second subnet in the same network for workers, in the
  subscription the identity works in. Nodes get no public IP, so the
  subnets need an egress path, such as a NAT gateway or a firewall, to the
  image registries and Azure's endpoints. With the default internal API
  endpoint, the management cluster must reach the control-plane subnet
  (through peering or a VPN, for example).
- **Resource providers** registered in the subscription:
  `Microsoft.Compute`, `Microsoft.Network`, `Microsoft.ManagedIdentity`,
  `Microsoft.Authorization` and `Microsoft.Insights` (autoscale settings).
  The modules never register them.
- **Permissions** of the identity's service principal:
    - Contributor on the subscription: the cluster role creates a resource
      group, and joins the subnets, which must be in the same subscription.
      Narrow Contributor, and the network's resource group needs Network
      Contributor.
    - Role Based Access Control Administrator on the subscription, best with
      a condition that limits it to assigning Contributor, Network
      Contributor and AcrPull: the cluster role grants the node identities.
    - Managed Identity Operator on any node identity you bring, so the
      machine and pool roles can attach it.
- **Node images.** A Linux image built for Cluster API, with kubeadm, the
  kubelet, a container runtime, cloud-init, `curl` and `iptables`. The
  [CAPZ reference images](https://capz.sigs.k8s.io/self-managed/custom-images)
  work:
  `/communityGalleries/ClusterAPI-f72ceb4f-5159-4c26-a0fe-2ea738f0d019/images/capi-ubun2-2404/versions/{semver}`.
- **In the workload cluster:**
  [cloud-provider-azure](https://cloud-provider-azure.sigs.k8s.io/install/)
  (the cloud controller manager and cloud-node-manager), with
  `--configure-cloud-routes=false` for an overlay CNI, and the
  [Azure Disk CSI driver](https://github.com/kubernetes-sigs/azuredisk-csi-driver)
  for persistent volumes. Both read `/etc/kubernetes/azure.json`, which the
  modules write on every node from cloud-config bootstrap data.

## Identity Secret

The Secret holds the azurerm provider's environment variables:

| Key | Value |
| --- | --- |
| `ARM_TENANT_ID` | The Microsoft Entra tenant of the service principal |
| `ARM_SUBSCRIPTION_ID` | The subscription the cluster and its network live in |
| `ARM_CLIENT_ID` | The service principal's application (client) ID |
| `ARM_CLIENT_SECRET` | Its client secret |
| `ARM_USE_CLI` | `"false"`: the images have no Azure CLI |

For a client certificate, set `ARM_CLIENT_CERTIFICATE_PATH` to a file under
`/var/run/captf/credentials/` and `ARM_CLIENT_CERTIFICATE_PASSWORD` instead
of `ARM_CLIENT_SECRET`. From
[`examples/identity.yaml`](https://github.com/captf-io/terraform-azure-cluster/blob/main/examples/identity.yaml):

```yaml title="identity.yaml"
apiVersion: v1
kind: Secret
metadata:
  name: azure
  namespace: captf-system
type: Opaque
stringData:
  ARM_TENANT_ID: 00000000-0000-0000-0000-000000000000
  ARM_SUBSCRIPTION_ID: 00000000-0000-0000-0000-000000000000
  ARM_CLIENT_ID: 00000000-0000-0000-0000-000000000000
  ARM_CLIENT_SECRET: replace-me
  ARM_USE_CLI: "false"
---
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformClusterIdentity
metadata:
  name: azure
spec:
  secretRef:
    name: azure
    namespace: captf-system
  allowedNamespaces:
    list:
    - team-a
```

See [Identities and Credentials](../../user-guide/identities.md) for how
the Secret reaches the Jobs.

## Quick start

1. Create the identity from the cluster repository's example:

    ```sh
    export NAMESPACE=team-a AZURE_TENANT_ID=... AZURE_SUBSCRIPTION_ID=... \
      AZURE_CLIENT_ID=... AZURE_CLIENT_SECRET=...
    clusterctl generate yaml --from examples/identity.yaml | kubectl apply -f -
    ```

2. Generate the cluster from
   [`examples/cluster-kubeadm.yaml`](https://github.com/captf-io/terraform-azure-cluster/blob/main/examples/cluster-kubeadm.yaml):
   a KubeadmControlPlane of three, a MachineDeployment of two and a
   MachinePool of two. Quote the image ID so the shell keeps the braces:

    ```sh
    export CLUSTER_NAME=demo KUBERNETES_VERSION=v1.34.1
    export AZURE_SUBNET_ID=/subscriptions/<id>/resourceGroups/network/providers/Microsoft.Network/virtualNetworks/hub/subnets/nodes
    export AZURE_SSH_PUBLIC_KEY="$(cat ~/.ssh/id_ed25519.pub)"
    export AZURE_IMAGE_ID='/communityGalleries/ClusterAPI-f72ceb4f-5159-4c26-a0fe-2ea738f0d019/images/capi-ubun2-2404/versions/{semver}'
    clusterctl generate yaml --from examples/cluster-kubeadm.yaml | kubectl apply -n "$NAMESPACE" -f -
    ```

3. Once the first control-plane node answers, install a CNI (for example
   Calico with VXLAN) and cloud-provider-azure in the workload cluster.
   cloud-provider-azure sets each Node's provider ID; only then do the
   Machines get their Nodes and the workers join.

The KubeadmConfigs in the example name each Node after its VM
(`nodeRegistration.name: '{{ ds.meta_data["local_hostname"] }}'`), which
cloud-provider-azure needs to find the VM.

## API endpoint

- **Internal** (the default): a Standard load balancer frontend in the
  control-plane subnet, zone-redundant where the region has zones, with a
  dynamic address unless `api_load_balancer_private_ip` sets one.
- **Public** (`api_load_balancer_public = true`): a static Standard public
  IP. Include the management cluster's egress and the nodes' NAT gateway
  addresses in `api_allowed_cidrs`: the load balancer keeps the client's
  source address, so the control plane's security group sees them.
- **Probes.** HTTPS `GET /readyz` every 5 seconds with kubeadm; TCP with
  `distribution = "rke2"`, which may disable anonymous access, and on the
  supervisor port 9345.
- **Hairpin.** An Azure internal load balancer drops a flow from a backend
  to its own frontend when it maps the flow back to that backend. The
  machine role therefore installs a small service on control-plane nodes
  (cloud-config bootstrap data only): while the node's own API server
  answers `/readyz`, an iptables rule sends the node's traffic for the
  frontend to it directly; otherwise the rule is gone and the load balancer
  takes the traffic to another control-plane node, since this node's probe
  is down too. With RKE2 it covers port 9345 as well. Turn it off with
  `api_server_hairpin_workaround = false`; with Ignition, add the
  equivalent to your bootstrap configuration.
- **The endpoint guard** records `api_load_balancer_public`, the endpoint
  port, the control-plane subnet and the private address the frontend got,
  and fails any later plan that changes one (see
  [Shared Behavior](../shared-behavior.md#the-api-endpoint)). Making the
  current dynamic address static is allowed, since it moves nothing.

## Exports

The cluster role's `exports` carry the schema `captf.io/azure-cluster/v1`.

| Key | Value |
| --- | --- |
| `schema` | `captf.io/azure-cluster/v1` |
| `tenant_id` | The identity's tenant |
| `subscription_id` | The subscription, lowercase |
| `region` | The virtual network's Azure location, such as `westeurope` |
| `resource_group_name`, `resource_group_id` | The cluster's resource group (name lowercase) |
| `failure_domains` | One entry per zone, `{ "1" = {}, "2" = {}, "3" = {} }`; `{}` without zones |
| `virtual_network` | `{id, name, resource_group_name}` of the brought network |
| `subnet_id`, `subnet_name` | The control-plane subnet |
| `worker_subnet_id`, `worker_subnet_name` | The worker subnet (the control-plane subnet without `worker_subnet_id`) |
| `admin_username`, `admin_ssh_public_key` | The nodes' admin user (`captf`) and key |
| `control_plane` | `{identity_id, identity_client_id, network_security_group_id, network_security_group_name, application_security_group_id, availability_set_id}`; the availability set only in a region without zones |
| `worker` | The same keys without `availability_set_id` |
| `api` | `{host, port, backend_port, frontend_ip, backend_pool_id, hairpin_workaround, supervisor_port}`; `port` is the endpoint port, `backend_port` the kube-apiserver's; `null` with a user endpoint |
| `cloud_provider_config` | The cloud-provider-azure configuration (`/etc/kubernetes/azure.json`) without `userAssignedIdentityID`, which each node adds for its identity |

Nothing in the exports is secret: the cloud provider authenticates with the
nodes' managed identities.

## Tags

Azure tag names cannot contain `/`, so `captf.io/<key>` becomes
`captf.io_<key>` (see [Shared Behavior](../shared-behavior.md#tags-and-labels)).
Tag names are case-insensitive, so `additional_tags` rejects any key that
starts with `captf.io_` or `captf.io/` in any case, and takes at most 44
tags: Azure allows 50 per resource. Values longer than 256 characters keep
247, then `-` and 8 hex characters of their sha256.

Not taggable: role assignments, security rules, load balancer backend
pools, probes and rules, NIC associations, the OS disk Azure creates with a
VM, and the instances, NICs and OS disks Azure creates for a scale set. All
of them live in the cluster's resource group, which is tagged.

??? note "Design notes"

    - **One resource group per cluster, always created.** It scopes the node
      identities' Contributor rights to what the cluster owns, collects what
      cloud-provider-azure creates for Services, and makes destroy fail loudly
      while those are still there instead of deleting disks with data.
    - **Network security groups on the NICs, not the subnet.** The subnet is
      yours; application security groups name the nodes, so intra-cluster
      traffic is open whatever the addresses. Workers keep Azure's default
      allow-from-network rule, because cloud-provider-azure adds none for
      internal Service load balancers.
    - **The module writes `/etc/kubernetes/azure.json`.** Without it the cloud
      controller manager never starts and no Machine gets its Node; the derived
      names it needs are not something you can easily put in a KubeadmConfig.
      It is written only when absent, so a file of your own wins.
    - **Custom data, never user data.** Azure exposes user data to every
      process on the node through the instance metadata service; custom data
      it does not.
    - **Scale sets update their model in place.** The provider's
      `roll_instances_when_required` and `reimage_on_manual_upgrade` are off:
      with azurerm's defaults every bootstrap token rotation would reimage
      every instance. A version change therefore creates a new scale set.
    - **Azure Autoscale holds a pool's capacity in both modes,** because the
      scale set ignores changes to its instance count, which an autoscaled pool
      must.
    - **Trusted launch is off by default:** the CAPZ reference images do not
      support it.

The evidence for each is in the role's `DESIGN.md`:
[cluster](https://github.com/captf-io/terraform-azure-cluster/blob/main/DESIGN.md),
[machine](https://github.com/captf-io/terraform-azure-machine/blob/main/DESIGN.md) and
[machinepool](https://github.com/captf-io/terraform-azure-machinepool/blob/main/DESIGN.md).

!!! warning "Not yet verified"

    - Whether Azure reports zones on a frontend or public IP differently from
      what was sent (harmless: the modules ignore later zone changes).
    - The minimal role set for cloud-provider-azure and Azure Disk CSI.
    - Azure Autoscale holding minimum, maximum and default equal with no rules,
      including 0, and how long it takes to apply a change.
    - The custom data limit of 65,535 decoded bytes (87,380 base64 characters).
    - Hairpin through a public load balancer; whether RKE2 needs the hairpin
      workaround; the DNAT rule alongside every CNI's iptables rules.
    - cloud-init running CABPK's Jinja template from a `text/plain` part of a
      multipart message, on the CAPZ images' cloud-init version.
    - Azure returning a role assignment's subnet or registry scope with the
      casing it was created with.
    - cloud-provider-azure with `vmType: "vmss"` handling standalone VMs next to
      scale sets.
    - The CAPZ gallery publishing an image for every Kubernetes version you
      roll to.
    - A cluster destroy after its network was deleted.
    - RKE2's API server answering `/readyz` with 401 or 403 when anonymous
      access is off, and whether the 9345 DNAT is needed.
    - Azure Resource Manager read throttling of pool refreshes beyond about 200
      instances.
