---
description: "Build a workload cluster in a Google Cloud VPC network you bring: the images, prerequisites, identity Secret, quick start, endpoint, exports and labels."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/cloud-cog
subtitle: "Proxy NLB, VMs, instance groups"
---

# Google Cloud

The Google Cloud modules create, in a VPC network you bring, a Cluster API
cluster's API load balancer (an internal proxy Network Load Balancer by
default), its firewall rules and its node service accounts; one Shielded VM
per `Machine`; and one regional managed instance group per `MachinePool`.
They live in [`captf-io/gcp-modules`](https://github.com/captf-io/gcp-modules)
and pin the `hashicorp/google` provider at 8.5.0. Like every reference
module set, they are pre-release: read the status note in
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
| cluster | `ghcr.io/captf-io/gcp-cluster` | [Cluster](cluster.md) |
| machine | `ghcr.io/captf-io/gcp-machine` | [Machine](machine.md) |
| machinepool | `ghcr.io/captf-io/gcp-machinepool` | [MachinePool](machinepool.md) |

The machine image's capacity labels describe its default machine type,
`n2-standard-4`: 4 vCPU and 16 GiB on `amd64`.

## Prerequisites

### Network

You bring the network; the modules create nothing in it but firewall rules.

- A VPC network and a regional subnetwork for the nodes. The internal API
  address comes from the same subnetwork.
- Cloud NAT on that subnetwork's router: nodes have no external address and
  need egress for container images and packages.
- For the default internal endpoint, a proxy-only subnet in the same
  network and region (`--purpose=REGIONAL_MANAGED_PROXY --role=ACTIVE`, an
  unused /23). One serves every Envoy-based load balancer there; the plan
  fails, with the `gcloud` command in its message, when there is none.
- Pod and Service CIDRs that overlap neither the subnetworks nor the
  proxy-only subnet. An auto-mode network uses 10.128.0.0/9.
- The management cluster must reach the internal API address: from the same
  VPC, a peered network, a VPN or Interconnect. Clients in other regions
  need `api_global_access`.
- Shared VPC: set the cluster's `network_project` to the host project. The
  firewall rules go there, and cloud-provider-gcp needs
  `network-project-id` in its `gce.conf`.

### Permissions of the identity

The role set below is expected to suffice; no real project has confirmed it
yet.

| Role | Granted on | For |
| --- | --- | --- |
| `roles/compute.loadBalancerAdmin` | the project | Addresses, forwarding rules, backend services, health checks, target proxies |
| `roles/compute.instanceAdmin.v1` | the project | Instance groups, instances and memberships, instance templates, managed instance groups, autoscalers |
| `roles/compute.securityAdmin` | the project and the network's project | Firewall rules, the Cloud Armor policy |
| `roles/compute.networkViewer` | the network's project | Listing the subnetworks |
| `roles/compute.networkUser` | the node subnetwork (Shared VPC only) | Instances in the host project's subnetwork |
| `roles/iam.serviceAccountAdmin` | the project | Creating the node service accounts (not needed when you bring both) |
| `roles/resourcemanager.projectIamAdmin` | the project | Granting the node service accounts their roles (not needed when you bring both) |
| `roles/iam.serviceAccountUser` | the two node service accounts only | Running instances as them; never grant it project-wide |
| `roles/secretmanager.admin` | the project | Staging control-plane bootstrap data |

Enable the Compute Engine and Secret Manager APIs in the project.

### Node images

Build an image per Kubernetes version, for example with
[image-builder](https://image-builder.sigs.k8s.io/capi/providers/gcp), and
name it so that a placeholder finds it: `capi-ubuntu-2404-v1-33-4` for
`projects/<project>/global/images/capi-ubuntu-2404-{slug}`. The image needs
cloud-init (or Ignition), and `curl`, `sed`, `base64` and `gzip` for staged
control-plane bootstrap data. Secure Boot is on by default, so its kernel
modules must be signed.

### In the workload cluster

- [cloud-provider-gcp](https://github.com/kubernetes/cloud-provider-gcp), the
  cloud controller manager, with a `gce.conf` from the cluster's exports:
  `project-id`, `network-name`, `subnetwork-name`, and
  `node-tags = <node_network_tag>`. The kubelets run with
  `cloud-provider: external`, so the CCM writes the `gce://` provider IDs
  the modules report.
- The [Compute Engine persistent disk CSI driver](https://github.com/kubernetes-sigs/gcp-compute-persistent-disk-csi-driver),
  whose controller runs as the control-plane service account.
- A CNI.

## Identity Secret

| Key | Value |
| --- | --- |
| `GOOGLE_CREDENTIALS` | A service account key JSON, or an `external_account` (workload identity federation) configuration |
| `GOOGLE_PROJECT` | The default project, when the `TerraformCluster` does not set `project` |
| `GOOGLE_REGION` | The default region, when the `TerraformCluster` does not set `region` |

Instead of `GOOGLE_CREDENTIALS`, a `credentials.json` key plus
`GOOGLE_APPLICATION_CREDENTIALS=/var/run/captf/credentials/credentials.json`
works too. From
[examples/identity.yaml](https://github.com/captf-io/gcp-modules/blob/main/examples/identity.yaml):

```yaml title="identity.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformClusterIdentity
metadata:
  name: gcp
spec:
  secretRef:
    name: gcp
    namespace: captf-system
  allowedNamespaces:
    list:
    - team-a
---
apiVersion: v1
kind: Secret
metadata:
  name: gcp
  namespace: captf-system
type: Opaque
stringData:
  GOOGLE_PROJECT: my-project
  GOOGLE_REGION: us-central1
  GOOGLE_CREDENTIALS: |
    {
      "type": "service_account",
      "project_id": "replace-me",
      "private_key_id": "replace-me",
      "private_key": "replace-me",
      "client_email": "captf@replace-me.iam.gserviceaccount.com",
      "client_id": "replace-me",
      "token_uri": "https://oauth2.googleapis.com/token"
    }
```

See [Identities and Credentials](../../user-guide/identities.md) for how the
Secret reaches a Job.

## Quick start

1. Create the network: VPC, node subnetwork, Cloud NAT and the proxy-only
   subnet.
2. Build a node image per Kubernetes version, named for the `{slug}`
   placeholder.
3. Create the identity:

    ```sh
    export NAMESPACE=team-a GCP_PROJECT=my-project GCP_REGION=us-central1
    clusterctl generate yaml --from examples/identity.yaml | kubectl apply -f -
    ```

4. Create the cluster: a `TerraformCluster`, a `KubeadmControlPlane`, a
   `MachineDeployment` of workers and an autoscaled `MachinePool`:

    ```sh
    export CLUSTER_NAME=demo KUBERNETES_VERSION=v1.33.4 \
      GCP_NETWORK=captf-vpc GCP_SUBNETWORK=captf-nodes \
      GCP_IMAGE='projects/my-images/global/images/capi-ubuntu-2404-{slug}'
    clusterctl generate yaml --from examples/cluster-kubeadm.yaml | kubectl apply -n team-a -f -
    ```

5. Once the API server answers, install cloud-provider-gcp, the persistent
   disk CSI driver and a CNI in the workload cluster.

[examples/README.md](https://github.com/captf-io/gcp-modules/blob/main/examples/README.md)
lists every variable of the two example files.

## API endpoint

- **Internal (default).** A regional internal proxy Network Load Balancer
  with a reserved internal address in the node subnetwork. Clients reach it
  from inside the VPC, or from any region with `api_global_access`.
- **Public.** With `api_load_balancer_public = true`, a global external
  proxy Network Load Balancer on a global address. A VPC firewall cannot
  filter clients behind a proxy, so a Cloud Armor policy allows only
  `api_allowed_cidrs` and denies the rest. Nodes reach the endpoint through
  Cloud NAT, so its static egress addresses must be in `api_allowed_cidrs`.
- **Hairpin.** Both are proxies: the proxy opens a new connection to a
  healthy backend, so a control-plane node reaches the endpoint it is itself
  behind. An internal passthrough load balancer would route the node's
  packets back to the node itself.
- **Backends.** One unmanaged instance group per zone; control-plane
  machines join their zone's group in their own state.
- **The endpoint guard** records `api_load_balancer_public`, `network`,
  `subnetwork`, `project`, `region`, the API port and the address when the
  load balancer is created, and fails any later plan that would change one
  of them. See [Shared Behavior](../shared-behavior.md#the-api-endpoint).

## Exports

Schema `captf.io/gcp-cluster/v1`:

| Key | Value |
| --- | --- |
| `schema` | `"captf.io/gcp-cluster/v1"` |
| `project`, `region` | Where machines and pools are created |
| `network`, `subnetwork` | Self links of the network and the node subnetwork |
| `name_prefix` | `captf-<namespace>-<cluster>`, truncated, plus 8 hex characters of the cluster key's sha256 |
| `failure_domains` | `{"<zone>" = {zone = "<zone>"}}` |
| `node_network_tag` | `<name_prefix>-node`, on every node: the `node-tags` value for cloud-provider-gcp |
| `control_plane`, `worker` | `{service_account = <email>, network_tags = [<node tag>, <role tag>]}` |
| `api` | `{host, port, backend_port, instance_groups = {"<zone>" = <self link>}}`; `null` with a user endpoint |

`api.port` is the endpoint's port; `api.backend_port` is the kube-apiserver
port on the nodes, 6443 with RKE2. Both listeners share the per-zone
instance groups, so there is no per-listener registration target.

## Tags

GCP labels: keys match `[a-z][a-z0-9_-]{0,62}` and values
`[a-z0-9_-]{0,63}`, so the `captf_tags` keys become `captf-io_cluster` and
so on, and values are lowercased with invalid characters turned into `_`. A
value over 63 characters keeps 54 characters, then `-` and 8 hex characters
of the original's sha256. `additional_tags` must already be valid labels,
may not start with `captf-io_`, and holds at most 58 entries (GCP allows 64
per resource).

These resource types cannot carry labels: firewall rules, instance groups,
managed instance groups, autoscalers, health checks, backend services,
target proxies, service accounts and IAM members. Their names carry the
cluster's or pool's name prefix, and their descriptions name the owning
object.

??? note "Design notes"

    - **A proxy load balancer, not passthrough,** because only a proxy lets a
      control-plane node reach the endpoint it is behind.
    - **Firewall rules match service accounts, not network tags,** so an
      instance cannot join the cluster's traffic by setting a tag. Nodes still
      carry a node tag, which cloud-provider-gcp needs for Service firewall
      rules.
    - **Node service accounts use predefined roles only:** a deleted custom
      role's ID cannot be reused for weeks, which would break recreating a
      cluster of the same name.
    - **Descriptions never hold `captf_tags`:** `description` forces
      replacement on addresses, forwarding rules and instance groups, and
      `captf.io/template` changes on a ClusterClass rebase.
    - **Control-plane bootstrap data is staged in Secret Manager:** instance
      metadata is readable through `compute.instances.get`, which `roles/viewer`
      includes.
    - **A pool's bootstrap data lives in the group's all-instances config,** so
      a rotation is a metadata refresh that never restarts or replaces an
      instance.
    - **A Kubernetes version change rolls a pool through the image name:** the
      image must carry a version placeholder, because a template change that
      only touches metadata is applied as a refresh.

[DESIGN.md](https://github.com/captf-io/gcp-modules/blob/main/DESIGN.md)
has the evidence for each, and the alternatives rejected.

!!! warning "Not yet verified"

    - The proxy-only subnet filter `purpose = "REGIONAL_MANAGED_PROXY"` on a
      real project.
    - The minimal role set for cloud-provider-gcp and the PD CSI driver, and the
      identity's role set.
    - That the managed instance group applies an all-instances config change as
      a refresh.
    - Who can read control-plane bootstrap data that is still in instance
      metadata (Ignition, or `bootstrap_delivery = "inline"`).
    - That `DEPROVISIONING` appears only while an instance is deleted, not
      while it stops.
    - cloud-init's handling of a gzip part, and of a `## template: jinja`
      payload, inside a pool's multipart user data.
    - That the managed instance group repairs a preempted, stopped Spot VM.
    - Firewall rules naming a service account created moments earlier.
    - The staged bootstrap fetch on a real image, and IAM propagation within
      its five minutes of retries.
    - Secret Manager replication under a resource-location policy, and the
      secret's deletion with the machine.
    - That a kubeadm payload behaves the same as cloud-init system
      configuration as it does as user data.
