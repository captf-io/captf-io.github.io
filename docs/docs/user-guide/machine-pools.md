---
title: "Managing Machine Pools with CAPTF"
description: Create a MachinePool backed by a TerraformMachinePool, choose fixed or autoscaled replicas, check members, and delete the group.
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/boxes
subtitle: "Scale groups of machines"
---

# Machine Pools

This page shows you how to create a `MachinePool` backed by a
`TerraformMachinePool`: a group of nodes CAPTF provisions and scales as one
native cloud scaling group (an autoscaling group, a scale set, an instance
group, or similar), rather than as individual `TerraformMachine`s. It
covers fixed and autoscaled replica counts, the group's reported members,
and deletion. See [The Kinds](../concepts/kinds.md) for how a
`TerraformMachinePool` compares to a `TerraformMachine`, and the
[machinepool contract](../module-author/contract/v1alpha1/machinepool.md)
for everything the module role must implement.

!!! info "Before you begin"

    - The provider installed, and a `TerraformCluster` provisioned or being
      provisioned (see [Installation](../operator-guide/installation.md)).
    - A `TerraformClusterIdentity` allowed in your namespace (see
      [Identities and Credentials](identities.md)).
    - A machinepool-role module image: one that implements the
      [machinepool contract](../module-author/contract/v1alpha1/machinepool.md),
      managing one scaling group and reporting its provider IDs, desired
      capacity and members.

## Pool or MachineDeployment

A pool's members are the cloud's, not Cluster API's: they have no
`Machine` objects, and CAPTF cannot remove one chosen member from the
group. The cloud's scaling group picks which instances go on scale-in,
replaces failed ones and rolls out new launch configuration. Anything that
works by deleting a specific `Machine` needs a MachineDeployment of
`TerraformMachine`s instead:

| You need | `MachinePool` with a `TerraformMachinePool` | MachineDeployment with `TerraformMachine`s |
| --- | --- | --- |
| A native scaling group that the cloud manages | Yes | No |
| Autoscaling | Yes: the module's own cloud autoscaler, or the Kubernetes Cluster Autoscaler's provider for that cloud (see [Autoscale with the Kubernetes Cluster Autoscaler](#autoscale-with-the-kubernetes-cluster-autoscaler)) | Yes: the Kubernetes Cluster Autoscaler's `clusterapi` provider |
| A drain before an instance goes | Only from the Kubernetes Cluster Autoscaler for the nodes it removes, or from the cloud's lifecycle hooks or a termination handler, if the module sets one up | Yes: Cluster API drains every `Machine` it deletes |
| MachineHealthCheck remediation | No | Yes |
| To delete one specific node, by deleting its `Machine` or with `cluster.x-k8s.io/delete-machine` | No | Yes |

The reasons pools stop here are in
[MachinePool Machines](../module-author/contract/v1alpha1/machinepool.md#machinepool-machines).

## Create a MachinePool

A `MachinePool` has a single infrastructure object for its whole group,
not one per member: `MachinePool.spec.template.spec.infrastructureRef`
names one `TerraformMachinePool` directly, by kind and name, the same way
`Cluster.spec.infrastructureRef` names one `TerraformCluster`. There is no
per-replica cloning, so you create the `TerraformMachinePool` yourself
rather than pointing at a `TerraformMachinePoolTemplate`; a
`TerraformMachinePoolTemplate` exists only for a `MachinePool` a
ClusterClass topology manages, covered in
[Templates and ClusterClass](clusterclass.md).

The `TerraformMachinePool` must carry the cluster's
`cluster.x-k8s.io/cluster-name` label: CAPTF looks up the owning `Cluster`
by that label, not by the `MachinePool`'s `spec.clusterName`. Cluster
API's `MachinePool` controller patches this label on from
`spec.clusterName` once the `TerraformMachinePool` exists, but only on
its own next reconcile; setting the label yourself avoids that wait.

For example:

```yaml
apiVersion: cluster.x-k8s.io/v1beta2
kind: MachinePool
metadata:
  name: my-cluster-workers
  namespace: team-a
spec:
  clusterName: my-cluster
  replicas: 3
  template:
    spec:
      clusterName: my-cluster
      version: v1.31.4
      bootstrap:
        configRef:
          apiGroup: bootstrap.cluster.x-k8s.io
          kind: KubeadmConfig
          name: my-cluster-workers
      infrastructureRef:
        apiGroup: infrastructure.cluster.x-k8s.io
        kind: TerraformMachinePool
        name: my-cluster-workers
---
apiVersion: bootstrap.cluster.x-k8s.io/v1beta2
kind: KubeadmConfig
metadata:
  name: my-cluster-workers
  namespace: team-a
spec:
  joinConfiguration: {}
---
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachinePool
metadata:
  name: my-cluster-workers
  namespace: team-a
  labels:
    cluster.x-k8s.io/cluster-name: my-cluster
spec:
  source:
    image: ghcr.io/example/machinepool-module:v0.1.0
  identityRef:
    name: aws-prod
```

The `KubeadmConfig` is the bootstrap provider's own object (one per pool,
for the same reason: a pool has no per-member Machine to hold one each);
its content is the bootstrap provider's concern, not CAPTF's. With
`spec.replicas` unset, Cluster API defaults it to 1; set it to the fixed
size you want, as above. Every field of `TerraformMachinePoolSpec` is
mutable: changing `spec.source`, `spec.identityRef`, `spec.variables` or
any other field re-applies the module on the next reconcile, and there is
no `spec.applyPolicy`. Only an apply that renders a change of the
cluster's exports is guarded (see [When the cluster's exports
change](#when-the-clusters-exports-change) and [The
Kinds](../concepts/kinds.md)). Pass module-specific configuration through
`spec.variables` or `spec.variablesFrom` as for any other kind (see
[Module Variables](variables.md)); `spec.jobs` tunes the Job the same way
it does for a `TerraformMachine` (see [Tuning Jobs](job-tuning.md)). A
pool with none of its own inherits `spec.identityRef`, `spec.jobs` and
`spec.drift.intervalSeconds` from the owning `TerraformCluster`'s
`spec.defaults`.

`node_labels` (rendered from `spec.template.metadata.labels`, not the
`TerraformMachinePool`'s own metadata) and the other inputs a module sees
are listed in the [machinepool contract](../module-author/contract/v1alpha1/machinepool.md#inputs)
and the [environment reference](../reference/environment.md); this page
does not restate them.

## Choose fixed replicas or autoscaling

With no autoscaler annotations, `MachinePool.spec.replicas` is the sole
source of desired capacity, exactly as in the example above: change it to
resize the group.

To let the module's own native autoscaling policy own the desired count
instead (or the Kubernetes Cluster Autoscaler; see
[Autoscale with the Kubernetes Cluster Autoscaler](#autoscale-with-the-kubernetes-cluster-autoscaler)),
set both annotations Cluster API's autoscaler contract defines, on the
`MachinePool`:

```yaml
apiVersion: cluster.x-k8s.io/v1beta2
kind: MachinePool
metadata:
  name: my-cluster-workers
  namespace: team-a
  annotations:
    cluster.x-k8s.io/cluster-api-autoscaler-node-group-min-size: "3"
    cluster.x-k8s.io/cluster-api-autoscaler-node-group-max-size: "10"
spec:
  clusterName: my-cluster
  template:
    spec:
      clusterName: my-cluster
      version: v1.31.4
      bootstrap:
        configRef:
          apiGroup: bootstrap.cluster.x-k8s.io
          kind: KubeadmConfig
          name: my-cluster-workers
      infrastructureRef:
        apiGroup: infrastructure.cluster.x-k8s.io
        kind: TerraformMachinePool
        name: my-cluster-workers
```

Both annotations must be present, parse as non-negative integers, and
satisfy min ≤ max, or the pool reports
[`AutoscalingActive=False/AutoscalingAnnotationsInvalid`](../reference/conditions.md#autoscalingactive)
and applies without autoscaling. Valid, the pool reports
`AutoscalingActive=True/ReplicasManagedByModule`: the module owns the
group's desired count and its own scaling policy (target tracking,
scheduled, or whatever it implements), and the controller claims the
`cluster.x-k8s.io/replicas-managed-by` annotation on the `MachinePool` so
Cluster API stops treating `spec.replicas` as authoritative. On every
reconcile the controller then writes the group's observed desired
capacity back to `MachinePool.spec.replicas`, emitting a
[`ReplicasWrittenBack`](../reference/events.md) event when it changes; see
[Annotations, Labels and
Finalizers](../reference/annotations-labels.md#cluster-api-and-clusterctl-keys)
for both keys. Leave `spec.replicas` unset in this mode: Cluster API
defaults and clamps it from the annotations for the first apply, and the
write-back takes over from there. Removing both annotations returns
`spec.replicas` to being authoritative and releases
`replicas-managed-by`.

If another controller already owns `cluster.x-k8s.io/replicas-managed-by`
on the `MachinePool` (its value is something other than the one CAPTF
claims), CAPTF leaves the annotation alone and stops writing observed
replicas back. The pool reports
`AutoscalingActive=False`/`ReplicasManagedExternally`, with a `Warning`
event, and `spec.replicas` stays under that other controller's control.
See [`AutoscalingActive`](../reference/conditions.md#autoscalingactive).

!!! warning "The Cluster Autoscaler's `clusterapi` provider does not drive these pools"

    It requires MachinePool Machines, which CAPTF does not implement (see
    [Pool or MachineDeployment](#pool-or-machinedeployment)). Running it
    against a CAPTF pool is unsupported, since its `spec.replicas` patches
    would be overwritten by the write-back above. Its cloud providers work:
    see the next section.

## Autoscale with the Kubernetes Cluster Autoscaler

The Kubernetes Cluster Autoscaler's cloud providers (`--cloud-provider=aws`,
`azure` or `oci`) resize a scaling group directly through the cloud's API,
draining each node they remove first. To CAPTF that is one more cloud-side
scale, the case autoscaling mode exists for:

1. Set the `MachinePool`'s min and max annotations, as in
   [Choose fixed replicas or autoscaling](#choose-fixed-replicas-or-autoscaling).
   The module puts the bounds on the group and leaves its desired count
   alone, and the controller writes the observed count back to
   `MachinePool.spec.replicas`.
2. Set the module's `autoscaler` variable to `external` in the
   `TerraformMachinePool`'s `spec.variables`, so the module creates no
   autoscaler of its own.
3. Make the group discoverable by the Cluster Autoscaler, as the module's
   page describes (tags on the group, or its ID).
4. Run the Cluster Autoscaler in the workload cluster with the cloud's
   provider and credentials allowed to resize the group. Keep its bounds for
   the group equal to the annotations.

| Reference module | `autoscaler: external` |
| --- | --- |
| [AWS](../cloud-modules/aws/machinepool.md) | Yes: an Auto Scaling group |
| [Azure](../cloud-modules/azure/machinepool.md) | Yes: a uniform virtual machine scale set |
| [OCI](../cloud-modules/oci/machinepool.md) | Yes: an instance pool |
| [GCP](../cloud-modules/gcp/machinepool.md) | No: the module's managed instance group is regional, and the Cluster Autoscaler's `gce` provider resizes zonal groups only ([`autoscaling_gce_client.go`](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/gce/autoscaling_gce_client.go) calls the zonal `InstanceGroupManagers` API) |

!!! warning "Run one autoscaler per group"

    With the default `autoscaler: native`, the module's own cloud autoscaler
    also resizes the group. Next to the Cluster Autoscaler it can remove the
    nodes the Cluster Autoscaler added, without a drain.

## Scale a MachineDeployment from zero

The Cluster Autoscaler's `clusterapi` provider can scale a
MachineDeployment or MachineSet to and from zero only if it knows the node's
size without a running node. For CAPTF it reads that from
`TerraformMachineTemplate.status.capacity`, which comes from, in order of
precedence:

1. the `capacity.cluster-autoscaler.kubernetes.io/*` annotations on the
   MachineDeployment or MachineSet (the Cluster Autoscaler's own override);
2. `TerraformMachineTemplate.spec.capacity`, for a module that takes its size
   as a variable;
3. the machine image's `io.captf.capacity` label, for a module that fixes it.

Capacity is a set of quantities (`cpu: "4"`, `memory: 16Gi`). CAPTF never
writes a node count for a MachineDeployment or MachineSet: the Cluster
Autoscaler, or you, own `spec.replicas`. The one count CAPTF does write is the
observed count of an autoscaled MachinePool, copied back as described above.
See [Override the
capacity](../reference/resources/terraformmachinetemplate.md#override-the-capacity).

## Add an autoscaled pool to a generated cluster

This walks through adding an autoscaled `MachinePool` to a cluster
generated from the default flavor ([Templates and
ClusterClass](clusterclass.md)), since none of the shipped flavors creates
one on their own.

Generate the default flavor with no workers; a `MachineDeployment` is
still created, with `spec.replicas: 0`, rather than omitted:

```sh
clusterctl generate cluster my-cluster --infrastructure terraform \
  --target-namespace team-a \
  --kubernetes-version v1.31.4 \
  --control-plane-machine-count 1 --worker-machine-count 0 \
  | kubectl apply -f -
```

Add the pool alongside it: a `MachinePool` with the autoscaler
annotations, its `KubeadmConfig` (the flavor's bootstrap provider is
kubeadm), and the `TerraformMachinePool`:

```yaml
apiVersion: cluster.x-k8s.io/v1beta2
kind: MachinePool
metadata:
  name: my-cluster-workers
  namespace: team-a
  annotations:
    cluster.x-k8s.io/cluster-api-autoscaler-node-group-min-size: "2"
    cluster.x-k8s.io/cluster-api-autoscaler-node-group-max-size: "5"
spec:
  clusterName: my-cluster
  template:
    spec:
      clusterName: my-cluster
      version: v1.31.4
      bootstrap:
        configRef:
          apiGroup: bootstrap.cluster.x-k8s.io
          kind: KubeadmConfig
          name: my-cluster-workers
      infrastructureRef:
        apiGroup: infrastructure.cluster.x-k8s.io
        kind: TerraformMachinePool
        name: my-cluster-workers
---
apiVersion: bootstrap.cluster.x-k8s.io/v1beta2
kind: KubeadmConfig
metadata:
  name: my-cluster-workers
  namespace: team-a
spec:
  joinConfiguration: {}
---
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachinePool
metadata:
  name: my-cluster-workers
  namespace: team-a
  labels:
    cluster.x-k8s.io/cluster-name: my-cluster
spec:
  source:
    image: ghcr.io/example/machinepool-module:v0.1.0
  identityRef:
    name: aws-prod
```

`spec.replicas` is left unset on the `MachinePool`: with both autoscaler
annotations present and valid, Cluster API defaults and clamps it from
`min-size`/`max-size` for the first apply, and the pool's own write-back
takes over from there (see [Choose fixed replicas or
autoscaling](#choose-fixed-replicas-or-autoscaling) above). Apply the
three objects, then confirm as in [Confirm it worked](#confirm-it-worked)
below.

## Set the membership refresh interval

Between applies, the controller runs a refresh to pick up members joining
or leaving the group, on `spec.membershipRefreshIntervalSeconds` (15–86400
seconds; unset or 0 means the cluster's
`spec.defaults.membershipRefreshIntervalSeconds`, else 60):

```yaml
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachinePool
spec:
  membershipRefreshIntervalSeconds: 30
```

A new member is unschedulable until its provider ID reaches
`spec.providerIDList`, so a shorter interval gets new nodes ready for
workloads sooner, at the cost of more frequent Jobs. The controller also
refreshes right after every apply and, while the group has not converged
(`spec.providerIDList`'s length differs from `status.replicas`), every 30
seconds, or the configured interval instead when it is shorter.

## Check the group's members

```sh
kubectl get terraformmachinepool <name> -n <namespace>
```

shows the owning cluster, `MachinePool`, desired replicas and the `Ready`
condition. `spec.providerIDList` is every non-terminated member, sorted
and deduplicated; `status.replicas` is the desired capacity as of the
last refresh; `status.instances` is the module's own per-member detail
(provider ID, an optional instance ID, addresses, failure domain and
health state), capped at 1000 entries:

```sh
kubectl get terraformmachinepool <name> -n <namespace> \
  -o jsonpath='{.status.instances}'
```

See [TerraformMachinePool](../reference/resources/terraformmachinepool.md#status)
for every status field. A pool reports provisioned, and the `Ready`
condition (mirrored onto the `MachinePool`'s `InfrastructureReady`)
true, once its state carries a successful apply and its module reports a
health state other than pending; unlike a fixed-replica machine, that
latch does not depend on `spec.providerIDList` being non-empty, since a
pool may legitimately scale to zero.

## Drift on a pool

!!! note "A pool's drift check cannot be disabled"

    `spec.drift.intervalSeconds: 0` falls back to the manager's default
    interval rather than turning checks off.

The reason is that the drift Job's own refresh is what feeds a plan; without
it, a cloud-side scaling change would never register as drift. With
`spec.drift.action: Remediate`, a detected difference re-applies the
pool's current inputs; with autoscaling enabled the module is responsible
for excluding its own desired-count attribute from that plan, or every
cloud-side scale reports as drift. See [Drift](drift.md) for setting the
interval and action, and [Drift and Health](../concepts/drift-and-health.md)
for how a check runs and feeds health.

## When the cluster's exports change

A pool's inputs include the cluster's exports (`captf_cluster_outputs`). When
they change, the pool applies the change, and that apply is guarded: if its plan
deletes or replaces anything, it stops before the apply step and the change is
**held**. Nothing else is guarded: the first apply, bootstrap rotations,
version rolls, replica changes and spec edits apply as usual while the exports
are unchanged.

While a change is held, bootstrap rotations keep applying at once with the
exports of its last successful apply. Any other input change (a version roll, a
replicas or spec edit) changes the approval hash, so the change is guarded
again: one more guarded apply runs with the new exports and blocks, its plan
supersedes the old one, and the pool holds again and applies that upgrade or
edit with the held exports. `ApplyJobSucceeded` meanwhile `ApplyJobSucceeded` shows
`False`/`DestructivePlanBlocked` (so the pool's `Ready` is `False`) with what
the plan would delete or replace and the pool's approval hash. After you have
read the plan, approve it:

```sh
kubectl patch terraformplan <plan> -n <namespace> --type merge \
  -p '{"spec":{"approved":true,"approvedBy":"<your username>"}}'
```

`<plan>` is `status.pendingPlanRef.name` of the pool, and the message names it
too. The plan (reason `ExportsChange`) binds the approval hash: the inputs hash
without `bootstrap_data`, so it survives bootstrap rotations and changes on any
other input change. Anyone who may patch `terraformplans` may approve it. If
the exports return to the applied ones, the change is withdrawn and the plan is
superseded; if they move to another change, or the spec changes the approval
hash, the old plan is superseded and a new one is made. If the exports return
to a change whose plan was superseded, it is guarded again and a new plan is
made before it is held. After a guarded apply fails part-way, every apply of the pool is
guarded until one succeeds. See [The destructive-plan
guard](../concepts/approvals/destructive-guard.md#machine-pools) for the full
behavior and its limits.

## Delete a MachinePool

Deleting the `MachinePool` deletes its `KubeadmConfig` and
`TerraformMachinePool` with it. Nothing blocks a `TerraformMachinePool`'s
deletion: it destroys the group from its durable inputs and removes its
finalizer once the destroy Job succeeds, whether or not the owning
`MachinePool` or `Cluster` still exist. See [the reconcile
lifecycle](../concepts/lifecycle.md) for how deletion and finalizers work
across every kind.

## Confirm it worked

!!! success ""

    ```sh
    kubectl get terraformmachinepool <name> -n <namespace>
    ```

    `Ready` reads `True` once the group is provisioned, and `Replicas` shows
    the desired capacity. `kubectl get machinepool <name> -n <namespace>`
    shows the same replica count and `InfrastructureReady=True` once Cluster
    API has copied `spec.providerIDList` and `status.replicas` across, which
    happens only once the workload cluster is reachable.

!!! related "See also"

    - [The Kinds](../concepts/kinds.md) for how a `TerraformMachinePool`'s
      mutability differs from a `TerraformMachine`'s.
    - [The machinepool contract](../module-author/contract/v1alpha1/machinepool.md)
      for every input and output a module role must implement.
    - [Drift](drift.md) and [Drift and Health](../concepts/drift-and-health.md).
    - [Templates and ClusterClass](clusterclass.md) for a
      `TerraformMachinePoolTemplate` used through a ClusterClass topology.
    - [Module Variables](variables.md) and [Tuning Jobs](job-tuning.md).
    - [TerraformMachinePool](../reference/resources/terraformmachinepool.md),
      [Conditions](../reference/conditions.md#autoscalingactive),
      [Events](../reference/events.md) and [Annotations, Labels and
      Finalizers](../reference/annotations-labels.md#cluster-api-and-clusterctl-keys).
