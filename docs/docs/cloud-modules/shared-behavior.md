---
description: "What all five cloud module sets have in common: the API endpoint, traffic rules, node identities, bootstrap data, health, tags and destroy."
tags:
  - Cloud modules
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "Steven Crothers"
icon: lucide/layers
subtitle: "What every cloud module does"
---

# Shared Behavior

The five sets of [cloud modules](README.md) follow one set of conventions,
so they behave the same way wherever the cloud allows it. This page
describes that common behavior; each cloud's pages describe only what
differs.

## The API endpoint

- **Internal by default.** The cluster role puts the API server load
  balancer on your subnets, reachable from inside the network. Setting
  `api_load_balancer_public = true` makes it internet-facing and requires a
  non-empty `api_allowed_cidrs`. Nodes then reach the endpoint through your
  egress path, so the list must include its public addresses; each cloud
  page lists what else a public endpoint needs.
- **Your own endpoint.** When the `Cluster` already has a control-plane
  endpoint (kube-vip, an external load balancer), the cluster role creates
  no load balancer and publishes that endpoint unchanged.
- **The port.** The load balancer listens on
  `Cluster.spec.clusterNetwork.apiServerPort` (default 6443). With
  `distribution = "rke2"` it also listens on the RKE2 supervisor port, 9345,
  and the kube-apiserver backends stay on 6443, where RKE2 always listens.
- **Hairpin.** A control-plane node must reach the endpoint itself while it
  joins (see the
  [cluster contract](../module-author/contract/v1alpha1/cluster.md)). Each
  cloud's load balancer handles this differently; the cloud pages say how.
- **The endpoint guard.** Cluster API never updates a cluster's endpoint
  after its first value, so a moved endpoint breaks every kubeconfig and
  certificate. Each cluster role records, when the load balancer is
  created, every input that decides the endpoint (visibility, subnets,
  port, address) and fails any later plan that would change one, with a
  message naming the recorded and the requested value. CAPTF's
  [destructive-plan guard](../concepts/approvals/destructive-guard.md)
  catches replacements only; the endpoint guard also catches changes a
  cloud makes in place. AWS lets you add load balancer subnets, and
  removing one is caught only by the destructive-plan guard; see
  [AWS](aws/README.md#api-endpoint).

## Network traffic

Nodes of one cluster accept all traffic from each other, scoped to the
cluster's own security group, network security group, network tag,
service account or application security group, so any CNI works without
port lists. Nothing else is open by default except the API port from the
load balancer, and on OpenStack the NodePorts from the node subnet (see
[OpenStack Cluster](openstack/cluster.md)). Some clouds have variables
that open more, such as `nodeport_allowed_cidrs` on OCI. SSH is closed
unless you list sources in `ssh_allowed_cidrs` (Google Cloud uses OS Login
instead).

## Node identities

The cluster role creates the cloud identities the cloud controller manager
and the CSI driver need on the nodes: instance profiles, service accounts,
managed identities or a dynamic group. Variables take existing identities
instead. On OCI the dynamic group covers the control-plane nodes only, and
needs a defined tag to match them by. OpenStack has no equivalent: its
cloud controller manager needs credentials you supply in the workload
cluster.

## Bootstrap data

- Both `cloud-config` and `ignition` bootstrap formats are accepted.
  Gzipped Ignition is refused. A precondition checks the cloud's user-data
  size limit.
- Control-plane bootstrap data holds the cluster's CA and service-account
  keys. Where instance user data is readable outside the instance, the
  machine role can stage it in a secret store the node's identity reads:
  S3 on AWS, Secret Manager on Google Cloud. The instance gets a small
  `#cloud-boothook` script that fetches the payload and installs it as
  `/etc/cloud/cloud.cfg.d/99-captf-bootstrap.cfg`, which cloud-init reads
  before it runs its modules. `bootstrap_delivery = "inline"` turns staging
  off for images without the fetch tools.
- Elsewhere the payload goes in user data, and the cloud page says who can
  read it. Azure keeps custom data out of its API and instance metadata.
  On OCI and OpenStack the instance metadata service serves it, which each
  page lists as an exception.

## Machine pools

- **Bootstrap rotation in place.** Bootstrap data rotates about every 7.5
  minutes. A rotation updates the group's launch configuration (or the
  staged object) in place, and never replaces a running instance; new
  instances pick up the current data.
- **Version rolls.** A change of the `MachinePool`'s Kubernetes version,
  compared verbatim so that an RKE2 `+rke2rN` bump counts, rolls the
  instances. Any other change that replaces instances is listed in the
  role's Exceptions.
- **Zones.** A pool that names no failure domains takes the cluster's at its
  first apply and keeps them, so a later change to the cluster's zones never
  moves running instances.
- **Autoscaling.** With the autoscaler annotations set, the group's minimum
  and maximum come from them and an apply never resets the desired count.
- **Node labels.** Cluster API does not put a `MachinePool`'s labels on its
  nodes, so the module does: a boot script adds `--node-labels` to the
  kubelet's arguments (both `/etc/default/kubelet` and
  `/etc/sysconfig/kubelet`) and writes an RKE2 `config.yaml.d` file. Labels
  the NodeRestriction admission plugin forbids are dropped and listed in the
  `dropped_node_labels` output. Ignition with labels is refused.

## Health

Every role reports the contract's `health` output from the cloud's own
state, with a machine-readable reason:

- A resource that is gone, or in a state that means deletion, is
  `terminated` with a reason like `InstanceNotFound` or
  `LoadBalancerNotFound`.
- Cluster health comes from the API load balancer, never from its backends,
  which are unhealthy during every normal control-plane bring-up.
- Pool health is, in this order: the group gone gives `terminated`; a
  desired capacity of 0 gives `running` and healthy; no members yet gives
  `pending` (`NoMembers`); any degraded, stopped or unknown member gives the
  worst of those; otherwise `running`, healthy only when every member runs
  and the count matches, with `ScalingInProgress` while it does not. A
  starting member never makes the pool `pending`. On Google Cloud an
  autoscaled group still at size 0 while its minimum is above 0 also
  reports `pending`, so a group created empty is not marked provisioned
  early.

See [Drift and Health](../concepts/drift-and-health.md) for how CAPTF uses
these readings.

## Tags and labels

Every resource that can carry tags or labels carries the contract's
`captf_tags`, plus your `additional_tags`. The `captf.io/<key>` keys are not
valid on every cloud, so each maps them the same way everywhere:

| Cloud | Mapping | Example |
| --- | --- | --- |
| AWS | unchanged | `captf.io/cluster` |
| Google Cloud labels | lowercase; `.` to `-`; other invalid characters to `_` | `captf-io_cluster` |
| Azure | `/` to `_` | `captf.io_cluster` |
| OCI free-form tags | `.` and space to `_`; at most 4 `additional_tags` | `captf_io/cluster` |
| OpenStack | Nova metadata `/` to `:`; Neutron and Octavia tags as `key=value` | `captf.io:cluster` |

## Exports and externally managed clusters

The cluster role's `exports` output carries a `schema` string such as
`captf.io/aws-cluster/v1`, the region, the failure domains, the API
endpoint and the ids the other roles need. The machine and machinepool
roles check the schema. When the `TerraformCluster` is externally managed
its exports are empty; set the user variable `external_cluster_exports` on
the machine or pool, in the same shape, to run them anyway.

## Destroy

A cluster's resources go only after all its machines and pools are gone.
Each role reads what you brought (subnets, networks, identities) through
listings that come back empty rather than failing, so deleting the network
first does not leave a `destroy` stuck, except where a cloud page's
Limitations say otherwise. Resources are counted so that one
deleted outside Terraform reads as gone, not unknown.

## Common variable names

The same concept has the same variable name in every repository:

| Concept | Variable |
| --- | --- |
| Public API load balancer | `api_load_balancer_public` |
| API client allowlist | `api_allowed_cidrs` |
| Static private API address | `api_load_balancer_private_ip` |
| Kubernetes distribution | `distribution` (`kubeadm` or `rke2`) |
| SSH allowlist | `ssh_allowed_cidrs` |
| Spot capacity | `spot`, or the cloud's term (`preemptible`) |
| Image name placeholders | `{version}` (`v1.31.4`) and `{semver}` (`1.31.4`); on Google Cloud, whose image names hold no dots, also `{slug}` and `{fullslug}` (which keeps an RKE2 `+rke2rN` suffix) |
| Staged bootstrap delivery | `bootstrap_delivery` |
| Extra tags or labels | `additional_tags` |
| Externally managed cluster | `external_cluster_exports` |
