---
title: "TerraformMachinePool API Reference"
description: "Every field, status value, condition, printer column and admission rule of the TerraformMachinePool kind, with examples."
icon: lucide/boxes
subtitle: "One native scaling group"
---

# TerraformMachinePool

A `TerraformMachinePool` is the infrastructure object behind one Cluster API
`MachinePool`: a group of nodes that CAPTF provisions and scales as a single
native cloud scaling group, by running a machinepool-role module as a
Kubernetes Job. The `MachinePool` references it through
`MachinePool.spec.template.spec.infrastructureRef`, and Cluster API sets the
`MachinePool` as its owner. You create it yourself, or Cluster API creates it
from a [`TerraformMachinePoolTemplate`](terraformmachinepooltemplate.md)
when a ClusterClass topology manages the `MachinePool`.

Unlike a `TerraformMachine`, every field of a pool is mutable: a change
re-applies the module. The controller writes the group's membership back into
`spec.providerID` and `spec.providerIDList`. See
[The Kinds](../../concepts/kinds.md) for how the three workload kinds
compare and [Machine Pools](../../user-guide/machine-pools.md) for the task
guide.

| Property | Value |
| --- | --- |
| API version | `infrastructure.cluster.x-k8s.io/v1alpha1` |
| Kind | `TerraformMachinePool` |
| Scope | Namespaced |
| Module role | `machinepool` (see the [machinepool contract](../../module-author/contract/v1alpha1/machinepool.md)) |
| Created by | You, or Cluster API from a [`TerraformMachinePoolTemplate`](terraformmachinepooltemplate.md) through a ClusterClass |
| Referenced by | `MachinePool.spec.template.spec.infrastructureRef` |
| Finalizer | `terraformmachinepool.infrastructure.cluster.x-k8s.io` |
| Short names | None |
| Categories | `cluster-api` |
| Status subresource | Yes |

## Example

The smallest useful pool names a module image and carries the cluster's name
label. `spec.source.image` is the only required field, and `spec.identityRef`
can be omitted when the `TerraformCluster` provides a default.

```yaml title="pool.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachinePool
metadata:
  name: my-cluster-workers
  namespace: team-a
  labels:
    cluster.x-k8s.io/cluster-name: my-cluster # (1)!
spec:
  source:
    image: ghcr.io/captf-io/module-images/aws-machinepool:v0.1.0-opentofu
  identityRef:
    name: aws-prod
```

1. CAPTF finds the owning `Cluster` by this label, not by the
   `MachinePool`'s `spec.clusterName`. Cluster API adds it on its own next
   reconcile if it is missing, so setting it yourself avoids a wait.

The `MachinePool` that owns the pool points back at it, and also needs a
bootstrap provider object (see
[Create a MachinePool](../../user-guide/machine-pools.md#create-a-machinepool)).

## Full example

```yaml title="pool-full.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachinePool
metadata:
  name: my-cluster-workers
  namespace: team-a
  labels:
    cluster.x-k8s.io/cluster-name: my-cluster
spec:
  source:
    image: ghcr.io/captf-io/module-images/aws-machinepool:v0.1.0-opentofu
    imagePullPolicy: IfNotPresent
  identityRef:
    name: aws-prod # (1)!
  jobs:
    activeDeadlineSeconds: 3600 # (2)!
    lockTimeoutSeconds: 300
  variables: # (3)!
    instance_type: m6i.large
    root_volume_gib: 100
  variablesFrom:
    - configMapRef:
        name: pool-common-vars
  drift:
    intervalSeconds: 900 # (4)!
    action: Remediate
  membershipRefreshIntervalSeconds: 30 # (5)!
  providerID: aws:///us-east-1/my-cluster-workers # (6)!
  providerIDList: # (7)!
    - aws:///us-east-1a/i-0a1b2c3d4e5f60001
    - aws:///us-east-1b/i-0a1b2c3d4e5f60002
```

1. Falls back to the `TerraformCluster`'s `spec.defaults.identityRef`, then
   its `spec.identityRef`, when unset.
2. Merged field by field over the cluster's `spec.defaults.jobs`.
3. The inline value wins over `variablesFrom` on the same key. The names
   `captf_*` and the role's contract inputs are reserved.
4. Both sub-fields fall back to the cluster's `spec.defaults.drift`. A pool's
   drift cannot be turned off.
5. How often CAPTF refreshes the group's membership between applies.
6. Set by the controller from the module's `provider_id` output. You do not
   write it.
7. Set by the controller from the module's `provider_id_list` output. You do
   not write it.

## Spec

The `spec` block must not be empty, and `spec.source` is required.
No spec field is immutable. Because the CRD declares no defaults, every
default below is applied by the controller at reconcile, never stored in the
object.

The fields embedded from the shared workspace spec are documented in depth on
[Common Fields](common-fields.md). The table links to each.

| Field | Type | Description |
| --- | --- | --- |
| `spec.source` | object | The machinepool module image and pull policy. See [Source](common-fields.md#source). **Required.** **Mutable.** Never inherited from the cluster. |
| `spec.identityRef` | object | The `TerraformClusterIdentity` whose credentials the pool's Jobs use. See [Identity reference](common-fields.md#identity-reference). **Mutable.** **Default:** the owning `TerraformCluster`'s `spec.defaults.identityRef`, else its `spec.identityRef`. |
| `spec.jobs` | object | Tuning of the Jobs that run the module. See [Jobs](common-fields.md#jobs). **Mutable.** **Default:** merged field by field over the cluster's `spec.defaults.jobs`, then the built-in per-field defaults. |
| `spec.variables` | object | Inline module variables, a JSON object. See [Variables](common-fields.md#variables). **Mutable.** A change re-applies the pool. Wins over `spec.variablesFrom`. |
| `spec.variablesFrom` | list | ConfigMaps and Secrets that supply module variables. See [Variable sources](common-fields.md#variable-sources). **Mutable.** |
| `spec.providerID` | string | The scaling group's provider ID. See [Provider IDs](#provider-ids). |
| `spec.providerIDList` | list of strings | The provider IDs of every non-terminated member. See [Provider IDs](#provider-ids). |
| `spec.drift` | object | How often to check for drift and what to do about it. See [Drift](#drift). **Mutable.** |
| `spec.membershipRefreshIntervalSeconds` | integer | How often to refresh group membership between applies. See [Membership refresh](#membership-refresh). |

### Provider IDs

The controller writes both fields from the module's outputs. You do not set
them, and a template accepts but does not use them.

| Field | Type | Description |
| --- | --- | --- |
| `spec.providerID` | string | The scaling group's provider ID, from the module's `provider_id` output. Optional in the Cluster API `InfraMachinePool` contract and may stay unset for modules that have no group object. **Optional.** **Mutable.** **Range:** 1 to 512 characters. |
| `spec.providerIDList` | list of strings | The provider IDs of every non-terminated member, from the module's `provider_id_list` output, sorted and deduplicated. Each entry must equal the corresponding Node's `spec.providerID`. Cluster API copies the list to `MachinePool.spec.providerIDList`, and a Node stays unschedulable until its ID is in it. **Optional.** **Mutable.** **Range:** at most 10000 entries, each 1 to 512 characters. |

The list changes whenever the group's membership does, which is why neither
field is immutable.

### Drift

`spec.drift` is merged field by field over the cluster's
`spec.defaults.drift`. A field you leave unset inherits the cluster's value.
See [Drift](../../user-guide/drift.md) for the task guide and
[Drift and Health](../../concepts/drift-and-health.md) for how a check runs.

| Field | Type | Description |
| --- | --- | --- |
| `spec.drift.intervalSeconds` | integer | Seconds between drift checks. **Mutable.** **Default:** the cluster's `spec.defaults.drift.intervalSeconds` when positive, else the manager's `--drift-default-interval` (30 minutes; see [Manager Flags](../manager-flags.md)). **Range:** 1 or more. |
| `spec.drift.action` | string | What CAPTF does when a check finds changes. **Mutable.** **Default:** `Report`. **Allowed values:** `Report` records the difference in the `DriftDetected` condition only; `Remediate` applies the pool's current inputs to remove it. |

A pool's drift cannot be disabled, so `0` is rejected for
`spec.drift.intervalSeconds`, and an inherited `0` from the cluster's
defaults is ignored in favor of the manager default. The drift Job's refresh
feeds the group's current size into its plan; with no checks, a cloud-side
scaling change would never register.

!!! warning "Remediation can fight a module's own autoscaling"

    With `spec.drift.action: Remediate` and autoscaling enabled, the module
    must exclude its desired-count attribute from the plan. Otherwise every
    cloud-side scale reports as drift and is reverted.

### Membership refresh

| Field | Type | Description |
| --- | --- | --- |
| `spec.membershipRefreshIntervalSeconds` | integer | Seconds between `apply -refresh-only` runs that pick up members joining or leaving the group between applies. **Optional.** **Mutable.** **Default:** 60 when unset or 0. **Range:** 15 to 86400. |

The schema minimum of 15 means `0` is never a valid explicit value, so it
always reads as unset. The controller also refreshes right after every apply.
While the group has not converged (the length of `spec.providerIDList`
differs from `status.replicas`), it refreshes every 30 seconds, or at the
configured interval when that is shorter. A shorter interval gets new nodes
ready sooner at the cost of more Jobs. See
[Set the membership refresh interval](../../user-guide/machine-pools.md#set-the-membership-refresh-interval).

### Relation to the MachinePool

The owning `MachinePool` supplies the pool's size, not the
`TerraformMachinePool`: the desired replica count reaches the module as its
`replicas` input, from `MachinePool.spec.replicas`.

- **Fixed size.** With no autoscaler annotations, `MachinePool.spec.replicas`
  is the only source of desired capacity. Change it to resize the group.
- **Autoscaling.** With both
  `cluster.x-k8s.io/cluster-api-autoscaler-node-group-min-size` and
  `...-max-size` annotations on the `MachinePool`, the module owns the
  desired count. The controller then writes the observed capacity back to
  `MachinePool.spec.replicas` on every reconcile. The `AutoscalingActive`
  condition reports the mode; see [Conditions](#conditions).
- **Membership.** Cluster API reads `spec.providerIDList` to match Nodes to
  the group, and reads `status.ready` to decide the pool is provisioned.

## Status

The `status` block is rebuilt from the state Secret, the durable inputs and the Job
list, so nothing in it is lost by `clusterctl move`. Fields shared with the
other workload kinds are documented on [Common Fields](common-fields.md).

| Field | Type | Description |
| --- | --- | --- |
| `status.conditions` | list | The pool's conditions, keyed by `type`, at most 32. See [Conditions](#conditions). |
| `status.conditions[].type` | string | The condition type, such as `Ready` or `ApplyJobSucceeded`. |
| `status.conditions[].status` | string | `True`, `False` or `Unknown`. |
| `status.conditions[].observedGeneration` | integer | The `metadata.generation` the condition was computed for. |
| `status.conditions[].lastTransitionTime` | time | When the condition last changed status. |
| `status.conditions[].reason` | string | A machine-readable reason. See [Conditions](../conditions.md). |
| `status.conditions[].message` | string | A human-readable detail. It never contains a variable value. |
| `status.ready` | boolean | The v1beta1 compatibility flag Cluster API reads to decide the pool is provisioned. Latched together with `status.initialization.provisioned`: once `true`, it stays `true`. |
| `status.replicas` | integer | The group's desired capacity at the last refresh, from the module's `replicas` output. Outside a scaling transition it equals the length of `spec.providerIDList`. **Range:** 0 or more. |
| `status.instances` | list | The group's members, from the module's `instances` output, at most 1000. See [Instances](#instances). |
| `status.initialization` | object | The Cluster API contract's provisioned flag. See [Initialization](common-fields.md#initialization). |
| `status.observedGeneration` | integer | The generation this status was computed for. See [Observed generation](common-fields.md#observed-generation). |
| `status.activeJob` | object | The Job running for the pool now, if any. See [Active job](common-fields.md#active-job). |
| `status.lastRun` | object | The result of the last completed Job. See [Last run](common-fields.md#last-run). |
| `status.lastDriftCheck` | time | When the last drift check completed. See [Drift checks and refreshes](common-fields.md#drift-checks-and-refreshes). |
| `status.lastRefresh` | time | When the last refresh or drift check completed. See [Drift checks and refreshes](common-fields.md#drift-checks-and-refreshes). |
| `status.pendingRefreshes` | integer | Consecutive health samples that read `pending`, which spaces refreshes while the group starts up. See [Drift checks and refreshes](common-fields.md#drift-checks-and-refreshes). |
| `status.observedStateSerial` | integer | The state serial the outputs were read from. See [State](common-fields.md#state). |
| `status.lastRestoredSerial` | integer | The backup serial of the last consumed restore Job. See [State](common-fields.md#state). |
| `status.stateSecretSuffix` | string | The state Secret's backend suffix, derived by the controller. See [State](common-fields.md#state). |
| `status.stateBackups` | list | The state backups the controller keeps, newest first. See [State](common-fields.md#state). |
| `status.source` | object | What the last Job actually ran. See [Image in use](common-fields.md#image-in-use). |

The whole status block is reported under [Workspace status](common-fields.md#workspace-status).

### Instances

`status.instances` mirrors the module's `instances` output. Its shape is
module-defined and core Cluster API does not use it. If the module reports
more than the controller keeps, the list is shortened and `OutputsValid`
carries the `InstancesTruncated` reason (see
[Conditions](../conditions.md#outputsvalid)).

| Field | Type | Description |
| --- | --- | --- |
| `status.instances[].providerID` | string | The instance's provider ID. **Required.** **Range:** 1 to 512 characters. |
| `status.instances[].instanceID` | string | A provider-defined identifier, distinct from `providerID` when the module has one to give. **Range:** 1 to 256 characters. |
| `status.instances[].addresses` | list | The instance's addresses, 1 to 256 entries. |
| `status.instances[].addresses[].type` | string | The Cluster API machine address type. **Allowed values:** `Hostname`, `ExternalIP`, `InternalIP`, `ExternalDNS`, `InternalDNS`. |
| `status.instances[].addresses[].address` | string | The address itself. |
| `status.instances[].failureDomain` | string | The failure domain the instance actually runs in. **Range:** 1 to 256 characters. |
| `status.instances[].state` | string | The instance's health, the contract's `health.state`. **Allowed values:** `pending`, `running`, `degraded`, `stopped`, `terminated`, `unknown`. |

??? example "Example status"

    ```yaml
    status:
      ready: true
      replicas: 2
      initialization:
        provisioned: true
      observedGeneration: 4
      observedStateSerial: 17
      stateSecretSuffix: <16 hex digits>-mp   # of sha256(namespace/kind/name)
      lastRefresh: "2026-10-02T09:41:12Z"
      lastDriftCheck: "2026-10-02T09:30:07Z"
      instances:
        - providerID: aws:///us-east-1a/i-0a1b2c3d4e5f60001
          instanceID: i-0a1b2c3d4e5f60001
          failureDomain: us-east-1a
          state: running
          addresses:
            - type: InternalIP
              address: 10.0.1.23
        - providerID: aws:///us-east-1b/i-0a1b2c3d4e5f60002
          instanceID: i-0a1b2c3d4e5f60002
          failureDomain: us-east-1b
          state: pending
      conditions:
        - type: Ready
          status: "True"
          reason: Ready
          observedGeneration: 4
          lastTransitionTime: "2026-10-02T09:12:40Z"
        - type: AutoscalingActive
          status: "False"
          reason: AutoscalingDisabled
          observedGeneration: 4
          lastTransitionTime: "2026-10-02T09:12:40Z"
    ```

## Conditions

`Ready` is the summary: Cluster API mirrors it into the `MachinePool`'s
`InfrastructureReady` condition. Every reason of every condition is listed in
[Conditions](../conditions.md); this page names only which conditions a pool
carries.

| Condition | `True` | `False` | `Unknown` |
| --- | --- | --- | --- |
| `Ready` | Every input is healthy. | An input is `False`. | An input is `Unknown`. |
| `DependenciesReady` | The owner, the cluster, its exports, the bootstrap data and any variable sources are in place. | The owner is gone, mismatched or has no `MachinePool` ownerRef yet, the `Cluster` is not a `TerraformCluster`, or a variable source is missing or invalid. | The pool waits for its owner, the cluster, its exports or bootstrap data. |
| `IdentityAllowed` | The identity exists and permits this namespace. | No identity is set, it is missing, does not permit this namespace or has no Secret. | The identity check could not be completed. |
| `CredentialsMirrored` | The Job's credentials are in place. | They could not be copied. | The mirror is pending. |
| `RunnerRBACReady` | The Job's ServiceAccount and RBAC exist. | They could not be created, or an override ServiceAccount lacks the `captf.io/runner=true` label. | Never `Unknown`. |
| `ApplyJobSucceeded` | The last apply or destroy succeeded. | It failed, hit its deadline or could not start, or a destructive change of the cluster's exports waits for approval. | No apply has completed yet, or the run waits for a lease or for the cluster. A running apply keeps the last result. |
| `StateReadable` | The state Secret reads cleanly. | It is encrypted, corrupt, inconsistent, lost or locked. | No state exists yet. |
| `RestoreJobSucceeded` | The last state restore succeeded. | It failed, or the requested backup does not exist. | The restore waits for a run lease or for the cluster. Set only once a restore is requested. |
| `OutputsValid` | The module's outputs satisfy the contract. | An output is missing or invalid, or a provider ID changed. | Required outputs are still `null`. |
| `InfrastructureHealthy` | The module reports the group healthy. | The pool is provisioning, or the module reports pending, unhealthy, degraded, stopped or terminated. | Before the first apply, or health is unknown. |
| `DriftJobSucceeded` | The last drift check succeeded. | It failed or hit its deadline. | No check has completed, a check is running or waits for a lease, or the durable inputs Secret is missing. |
| `DriftDetected` | The last check found drift: reported, pending remediation or being remediated. | It found none. | No check has completed. |
| `AutoscalingActive` | The module owns the group's desired count and the controller writes it back to `MachinePool.spec.replicas`. | Autoscaling is off, its annotations are invalid, or another controller owns `spec.replicas`. | Never `Unknown`. |
| `Paused` | The `Cluster` or object is paused. | It is not. | Never `Unknown`. |
| `Deleting` | The pool is being deleted. It makes `Ready` `False`. | It is not. | Never `Unknown`. |

After provisioning, `Ready` is computed from `InfrastructureHealthy`,
`ApplyJobSucceeded` and `Deleting`. Unlike for the cluster and the machine, a
failed re-apply shows in a pool's `Ready`, because a pool is re-applied
regularly. `DriftDetected`, `DriftJobSucceeded`, `RestoreJobSucceeded`,
`AutoscalingActive` and `Paused` never feed `Ready`.

A pool becomes provisioned once its state carries a successful apply and the
module reports a health state other than `pending`. That does not require
`spec.providerIDList` to be non-empty, since a pool can scale to zero.

## Printer columns

`kubectl get terraformmachinepools` shows:

| Column | Source |
| --- | --- |
| `CLUSTER` | The `cluster.x-k8s.io/cluster-name` label. |
| `MACHINEPOOL` | The name of the owner reference of kind `MachinePool`. |
| `REPLICAS` | `status.replicas`. |
| `READY` | The `Ready` condition's status. |
| `AGE` | Time since creation. |

## Validation

The CRD schema and the validating webhook
(`validation.terraformmachinepool.infrastructure.cluster.x-k8s.io`, on create
and update, `failurePolicy: Fail`) enforce these rules. The webhook returns one
`Invalid` error that lists every violation. It sets no defaults: all defaults
come from the controller at reconcile.

- **Required.** `spec` must have at least one field, and `spec.source.image`
  must be set.
- **Image reference.** `spec.source.image` must parse as a container image
  reference. The webhook checks the syntax only, not the registry or the
  contents. `spec.source.imagePullPolicy` must be `IfNotPresent`, `Always` or
  `Never`.
- **Immutability.** None. Every field of the pool can change on a live
  object, and a change re-applies the module.
- **Ranges.**
    - `spec.providerID`: 1 to 512 characters.
    - `spec.providerIDList`: at most 10000 entries, each 1 to 512 characters.
    - `spec.drift.intervalSeconds`: 1 or more.
    - `spec.membershipRefreshIntervalSeconds`: 15 to 86400.
    - `status.instances`: at most 1000 entries. `status.conditions`: at most
      32.
- **Enums.** `spec.drift.action` is `Report` or `Remediate`.
  `status.instances[].state` is one of the six health states.
- **Variables.**
    - `spec.variables` is a JSON object with 1 to 256 keys.
    - Each key is a Terraform identifier that does not start with `captf_`,
      is not a machinepool contract input and is not a module meta-argument.
    - Each `spec.variablesFrom` entry sets exactly one of `configMapRef` and
      `secretRef`. Keys inside a referenced ConfigMap or Secret are checked at
      reconcile and report `VariablesInvalid`.
    - Errors never include a value.
- **Job policy.** `spec.jobs` may not weaken the hardened security context:
  no privileged container, privilege escalation, added capabilities,
  writable root filesystem, unmasked `/proc`, `runAsNonRoot: false`, UID 0,
  `Unconfined` seccomp profile or Windows host process, in the container or
  pod context. `lockTimeoutSeconds` must be less than
  `activeDeadlineSeconds`; an unset one is compared with the other's built-in
  default. The check runs on create, and on update only when `spec.jobs`
  changed, never on a deleting object, so a stored policy cannot block a
  finalizer removal. The merge with the cluster's defaults is not checked.
  See [Tuning Jobs](../../user-guide/job-tuning.md#security-contexts).
- **Delete.** Always allowed.

## Lifecycle

- **Create.** The controller waits for the owning `MachinePool`, the cluster
  to be provisioned and its exports and the bootstrap data to be ready, then
  applies the module. It refreshes right after the apply to read the group's
  members.
- **Scale.** A change to `MachinePool.spec.replicas` re-applies the pool. In
  autoscaling mode the controller instead writes the observed capacity back.
- **Change.** Any spec change, and a rotation of the bootstrap data Secret,
  re-applies the module. An apply that renders a change of the cluster's
  exports is guarded: if its plan deletes or replaces anything, it waits for
  the `captf.io/approve-destructive-plan` annotation (see
  [The destructive-plan guard](../../concepts/approvals/destructive-guard.md#machine-pools)).
- **Drift and refresh.** Drift checks run on `spec.drift.intervalSeconds` and
  membership refreshes on `spec.membershipRefreshIntervalSeconds`.
- **Delete.** Nothing blocks the deletion. The controller runs a destroy Job
  from the stored inputs and removes the finalizer once it succeeds, even if
  the `MachinePool` or `Cluster` no longer exists. See
  [The reconcile lifecycle](../../concepts/lifecycle.md#deletion-order).

!!! related "See also"

    - [TerraformMachinePoolTemplate](terraformmachinepooltemplate.md) and
      [Common Fields](common-fields.md).
    - [Machine Pools](../../user-guide/machine-pools.md), [Drift](../../user-guide/drift.md),
      [Identities and Credentials](../../user-guide/identities.md) and
      [Tuning Jobs](../../user-guide/job-tuning.md).
    - [The machinepool contract](../../module-author/contract/v1alpha1/machinepool.md).
    - [The Kinds](../../concepts/kinds.md),
      [The Reconcile Lifecycle](../../concepts/lifecycle.md) and
      [Drift and Health](../../concepts/drift-and-health.md).
    - [Conditions](../conditions.md),
      [Annotations, Labels and Finalizers](../annotations-labels.md) and
      [Manager Flags](../manager-flags.md).
