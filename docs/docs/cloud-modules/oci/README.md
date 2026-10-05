---
description: "Build a workload cluster on an OCI VCN you bring: the images, prerequisites, identity Secret, quick start, API endpoint, exports and tags."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/database
subtitle: "Network LB, instances, pools"
---

# OCI

The OCI modules build a self-managed Kubernetes cluster on Oracle Cloud
Infrastructure, on a VCN you bring. The cluster role creates the nodes'
network security groups, a network load balancer for the API, and a dynamic
group and policy so the control-plane nodes run the OCI cloud controller
manager and CSI controller as instance principals. The machine role creates
one compute instance per `Machine`; the machinepool role runs an instance
pool at a fixed size or under OCI autoscaling. The code is in one
repository per role:
[`terraform-oci-cluster`](https://github.com/captf-io/terraform-oci-cluster),
[`terraform-oci-machine`](https://github.com/captf-io/terraform-oci-machine) and
[`terraform-oci-machinepool`](https://github.com/captf-io/terraform-oci-machinepool),
published on the Terraform Registry as
[`captf-io/cluster/oci`](https://registry.terraform.io/modules/captf-io/cluster/oci),
[`captf-io/machine/oci`](https://registry.terraform.io/modules/captf-io/machine/oci) and
[`captf-io/machinepool/oci`](https://registry.terraform.io/modules/captf-io/machinepool/oci).
The images are built from
[`captf-io/oci-modules`](https://github.com/captf-io/oci-modules). Read the
status note in [Cloud Modules](../README.md) before you rely on it.

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
| cluster | `ghcr.io/captf-io/oci-cluster` | [Cluster](cluster.md) |
| machine | `ghcr.io/captf-io/oci-machine` | [Machine](machine.md) |
| machinepool | `ghcr.io/captf-io/oci-machinepool` | [MachinePool](machinepool.md) |

The images pin the `oracle/oci` provider at 9.8.0.

## Prerequisites

- **A VCN** with a regional subnet for the control plane, and optionally one
  for workers and one for the API load balancer, all in one VCN and in the
  compartment you pass as `network_compartment_id` (default: the cluster's
  `compartment_id`). Private nodes need a NAT gateway route for egress, and
  a service gateway or NAT route to the OCI APIs. A public API load balancer
  needs a public subnet. Subnets need no DNS label. Security lists stay
  yours: the modules put their rules in network security groups.
- **A defined-tag namespace and key** for `node_identity.defined_tag`. The
  cluster's node dynamic group matches only control-plane instances by this
  tag; without one the cluster role refuses to plan unless you opt in to a
  compartment-wide group or turn node identity off. Keep one compartment per
  cluster either way.
- **Permissions** for the identity's user (or instance principal):

    ```text
    Allow group <group> to use virtual-network-family in compartment <network compartment>
    Allow group <group> to manage network-security-groups in compartment <compartment>
    Allow group <group> to manage network-load-balancers in compartment <compartment>
    Allow group <group> to inspect compartments in tenancy
    Allow group <group> to manage instance-family in compartment <compartment>
    Allow group <group> to use volume-family in compartment <compartment>
    Allow group <group> to manage compute-management-family in compartment <compartment>
    Allow group <group> to manage auto-scaling-configurations in compartment <compartment>
    Allow group <group> to read metrics in compartment <compartment>
    # Node identity (node_identity.enabled, the default):
    Allow group <group> to manage dynamic-groups in tenancy
    Allow group <group> to manage policies in compartment <node policy compartment>
    Allow group <group> to inspect tenancies in tenancy
    Allow group <group> to use tag-namespaces in tenancy
    # boot_volume_kms_key_id:
    Allow service blockstorage to use keys in compartment <vault compartment>
    ```

- **A node image** in the cluster's region with containerd, the kubelet and
  kubeadm (or RKE2) of your Kubernetes version and cloud-init, for example
  from [image-builder](https://image-builder.sigs.k8s.io/capi/providers/oci.html).
  The modules switch instance metadata v1 off, so cloud-init must read
  metadata v2, as current releases do. Autoscaled pools also need the
  Oracle Cloud Agent's Compute Instance Monitoring plugin.
- **In the workload cluster**, once its API server answers: the
  [OCI cloud controller manager](https://github.com/oracle/oci-cloud-controller-manager)
  with `useInstancePrincipals: true`, the cluster's compartment and VCN,
  and `securityListManagementMode: None`, scheduled on control-plane nodes;
  a CNI; and the OCI CSI driver if you want block volumes.

## Identity Secret

The OCI provider reads each setting from `OCI_<ARGUMENT>` environment
variables. CAPTF drops `TF_VAR_*`, so the Secret uses the `OCI_*` names, and
the API signing key travels as a file key that `OCI_PRIVATE_KEY_PATH` points
to. Config-file profiles do not work: the Job has no `~/.oci/config`. See
[Identities and Credentials](../../user-guide/identities.md).

| Key | Value |
| --- | --- |
| `OCI_TENANCY_OCID` | The tenancy OCID; the cluster role also reads it for the dynamic group |
| `OCI_USER_OCID` | The OCID of the user the API key belongs to |
| `OCI_FINGERPRINT` | The API key's fingerprint |
| `OCI_PRIVATE_KEY_PATH` | `/var/run/captf/credentials/oci_api_key.pem` |
| `oci_api_key.pem` | The PEM private key, unencrypted (or add `OCI_PRIVATE_KEY_PASSWORD`) |
| `OCI_AUTH` | Optional: `InstancePrincipal` on a management cluster that runs on OCI, instead of the key |

```yaml title="identity.yaml"
apiVersion: v1
kind: Secret
metadata:
  name: oci
  namespace: captf-system
type: Opaque
stringData:
  OCI_TENANCY_OCID: ocid1.tenancy.oc1..replace-me
  OCI_USER_OCID: ocid1.user.oc1..replace-me
  OCI_FINGERPRINT: "00:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee:ff"
  OCI_PRIVATE_KEY_PATH: /var/run/captf/credentials/oci_api_key.pem
  oci_api_key.pem: |
    -----BEGIN PRIVATE KEY-----
    replace-me
    -----END PRIVATE KEY-----
```

The region is never in the identity: each `TerraformCluster` sets `region`.

## Quick start

1. Apply the identity and its Secret from
   [`examples/identity.yaml`](https://github.com/captf-io/terraform-oci-cluster/blob/main/examples/identity.yaml),
   then replace the Secret's placeholders with your key:

    ```sh
    export NAMESPACE=team-a
    clusterctl generate yaml --from examples/identity.yaml | kubectl apply -f -
    kubectl create secret generic oci -n captf-system --dry-run=client -o yaml \
      --from-literal=OCI_TENANCY_OCID=ocid1.tenancy.oc1..<id> \
      --from-literal=OCI_USER_OCID=ocid1.user.oc1..<id> \
      --from-literal=OCI_FINGERPRINT=<fingerprint> \
      --from-literal=OCI_PRIVATE_KEY_PATH=/var/run/captf/credentials/oci_api_key.pem \
      --from-file=oci_api_key.pem=<path to the PEM key> | kubectl apply -f -
    ```

2. Generate the cluster from
   [`examples/cluster-kubeadm.yaml`](https://github.com/captf-io/terraform-oci-cluster/blob/main/examples/cluster-kubeadm.yaml):
   a three-node `KubeadmControlPlane`, a `MachineDeployment`, a
   `MachinePool` and MachineHealthChecks.

    ```sh
    export CLUSTER_NAME=demo KUBERNETES_VERSION=v1.34.1
    export OCI_COMPARTMENT_ID=ocid1.compartment.oc1..<id> OCI_REGION=us-ashburn-1
    export OCI_CONTROL_PLANE_SUBNET_ID=ocid1.subnet.oc1.iad.<id>
    export OCI_WORKER_SUBNET_ID=ocid1.subnet.oc1.iad.<id>
    export OCI_IMAGE_ID=ocid1.image.oc1.iad.<id>
    export OCI_NODE_TAG_NAMESPACE=<tag namespace> OCI_NODE_TAG_KEY=<tag key>
    clusterctl generate yaml --from examples/cluster-kubeadm.yaml | kubectl apply -n "$NAMESPACE" -f -
    ```

3. Wait for the `TerraformCluster` to become ready. KCP then creates the
   control plane, and each control-plane instance joins the load balancer as
   it boots.
4. Install the cloud controller manager and a CNI in the workload cluster,
   as in [Prerequisites](#prerequisites).

Every node registers with `provider-id: oci://{{ v1.instance_id }}` in the
example's `kubeletExtraArgs`: cloud-init's Oracle datasource sets
`instance_id` to the instance OCID, so the Node's provider ID matches the
modules' `provider_id` from its first registration.

## API endpoint

- **Internal by default.** The network load balancer gets a private address
  in its subnet, reachable from the VCN. The management cluster must reach
  the VCN (peering, a DRG or VPN), or set `api_load_balancer_public = true`
  with `api_allowed_cidrs` and a public subnet. Nodes in private subnets
  reach a public endpoint through the NAT gateway, so its public IP belongs
  in `api_allowed_cidrs`.
- **Who may connect.** The load balancer's NSG admits the API ports from the
  VCN's CIDRs and `api_allowed_cidrs`; the control-plane NSG admits them
  only from the load balancer's NSG.
- **Hairpin.** The backend sets do not preserve the client address
  (`is_preserve_source = false`), so a backend sees the load balancer as the
  source and a control-plane node reaches itself through the endpoint.
  [Cluster API Provider OCI](https://github.com/oracle/cluster-api-provider-oci/blob/main/cloud/scope/network_load_balancer_reconciler.go)
  configures its API load balancer the same way.
- **Fixed addresses.** `api_load_balancer_private_ip` and
  `api_load_balancer_reserved_public_ip_id` pin the address.
- **The endpoint guard** records `api_load_balancer_public`, the load
  balancer subnet, `api_load_balancer_private_ip`,
  `api_load_balancer_reserved_public_ip_id`,
  `cluster_network.api_server_port` and the address the load balancer got.
  See [Shared Behavior](../shared-behavior.md#the-api-endpoint).

## Exports

Schema `captf.io/oci-cluster/v1`:

| Key | Value |
| --- | --- |
| `schema` | `captf.io/oci-cluster/v1` |
| `region` | The cluster's region |
| `compartment_id` | The compartment of every cluster resource |
| `vcn_id` | The control-plane subnet's VCN |
| `control_plane_subnet_id`, `worker_subnet_id` | The node subnets |
| `control_plane_nsg_id`, `worker_nsg_id` | The node network security groups |
| `failure_domains` | Failure domain name to `{ availability_domain, fault_domain }`; `fault_domain` only in fault-domain mode |
| `node_defined_tags` | The defined tag workers carry; `{}` without `node_identity.defined_tag` |
| `control_plane_defined_tags` | The defined tag control-plane machines carry, which the node dynamic group matches |
| `api` | `{ host, port, network_load_balancer_id, kube_apiserver, rke2_supervisor }`, each listener `{ backend_set_name, port }`; `null` with a user-supplied endpoint |

## Tags

Every taggable resource carries `captf_tags` as OCI free-form tags. Free-form
keys may not contain periods or spaces, so `.` and space become `_`
(`captf_io/cluster`); values are unchanged. OCI allows 10 free-form tags per
resource and the six captf tags always apply, so `additional_tags` takes at
most four, none starting with `captf_io/`. The provider ignores the defined
tags `Oracle-Tags.CreatedBy` and `Oracle-Tags.CreatedOn`; list your own tag
defaults in `ignore_defined_tags`.

Not taggable on OCI: network security group rules, network load balancer
backend sets, listeners and backends.

??? note "Design notes"

    - **A network load balancer for the API**, because it forwards TCP without
      terminating TLS and, with source preservation off, supports hairpin.
    - **Node identity for control-plane nodes only.** `read instance-family`
      lets a principal read any instance's user data, which on a control-plane
      instance holds the cluster's CA keys; workers get no OCI permissions, and
      the CSI node driver needs none.
    - **The tag namespace is yours.** A per-cluster namespace created by the
      module would make destroy slow (OCI retires and deletes namespaces
      asynchronously) and block a new cluster of the same name.
    - **Failure domains** are availability domains where the region has
      several, otherwise the three fault domains of its one availability domain,
      as CAPOCI does.
    - **Two pool resources**, fixed and autoscaled, because the provider
      overwrites `size` from the cloud on every read and OCI pools have no
      minimum or maximum to pin. A mode switch replaces the pool, so it needs
      the `autoscaled` variable to agree.
    - **Listings, not reads,** for the subnets and VCN, so a destroy finishes
      after the network is gone.
    - **User data inline.** OCI has no store the modules stage bootstrap data in
      yet, so it goes in instance metadata; the role pages say who can read it.

Each role's `DESIGN.md` has the evidence for each decision:
[cluster](https://github.com/captf-io/terraform-oci-cluster/blob/main/DESIGN.md),
[machine](https://github.com/captf-io/terraform-oci-machine/blob/main/DESIGN.md) and
[machinepool](https://github.com/captf-io/terraform-oci-machinepool/blob/main/DESIGN.md).

!!! warning "Not yet verified"

    - Whether OCI accepts the empty free-form tag value of `captf.io/template`.
    - IAM writes through the home-region provider; identity domains other than
      Default; a `/` in a defined-tag value in a matching rule.
    - The minimal node policy for load balancer Services and CSI, and the
      minimal permissions listed above.
    - Autoscaling down to 0 instances (refused until verified), and what the
      autoscaling configuration's `initial` size does to an existing pool.
    - The casing of pool members' states, and whether terminating members are
      listed.
    - Deleting an instance configuration that running instances came from.
    - An empty second plan for shape, source details, defined tags and the
      autoscaling rules.
    - Backend registration time against a fast `kubeadm init`.
    - In-transit boot volume encryption on custom images.
    - Whether the cloud controller manager and CSI controller need more than
      the five policy statements.
