---
description: "Reference for the TerraformMachine kind: every spec and status field, conditions, printer columns, validation rules and lifecycle."
icon: lucide/server
subtitle: "One Machine's infrastructure"
---

# TerraformMachine

A `TerraformMachine` is one node instance, provisioned by running a
machine-role module image as a Kubernetes Job. It is the infrastructure
machine object of Cluster API: a `Machine` points at it through
`Machine.spec.infrastructureRef`, and Cluster API mirrors its `Ready`
condition into the Machine's `InfrastructureReady` condition.

You rarely write one by hand. Cluster API creates it by cloning
`spec.template` of a [`TerraformMachineTemplate`](terraformmachinetemplate.md)
when a MachineDeployment, a MachineSet or a KubeadmControlPlane adds a
Machine. The manager then runs the module image of the `machine` role (see
the [machine role contract](../../module-author/contract/v1alpha1/machine.md)),
keeps its Terraform state in a Secret, and reads the instance's provider ID,
addresses, failure domain and health from the module's outputs.

| | |
| --- | --- |
| API version | `infrastructure.cluster.x-k8s.io/v1alpha1` |
| Kind | `TerraformMachine` |
| Scope | Namespaced |
| Module role | `machine` |
| Created by | Cluster API, from a [`TerraformMachineTemplate`](terraformmachinetemplate.md) |
| Referenced by | `Machine.spec.infrastructureRef` |
| Finalizer | `terraformmachine.infrastructure.cluster.x-k8s.io` |
| Short names | none |
| Categories | `cluster-api` |
| Status subresource | yes |

## Example

The smallest valid object sets only `spec.source.image`. The manager needs an
identity too, but a machine falls back to the one its `TerraformCluster`
names, so a machine in a working cluster does not set it.

```yaml title="terraformmachine.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachine
metadata:
  name: demo-md-0-x7k2p
  namespace: default
  labels:
    cluster.x-k8s.io/cluster-name: demo
spec:
  source:
    image: ghcr.io/captf-io/noop-machine:v0.1.0-opentofu
```

The `cluster.x-k8s.io/cluster-name` label and the owner reference to the
`Machine` come from Cluster API. Without them the manager has no cluster to
resolve and reports `DependenciesReady=False` or `Unknown` (see
[Conditions](#conditions)).

## Full example

Every spec field set. The `spec.providerID` line is shown for completeness:
the controller writes it, you do not.

```yaml title="terraformmachine-full.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachine
metadata:
  name: demo-md-0-x7k2p
  namespace: default
  labels:
    cluster.x-k8s.io/cluster-name: demo
spec:
  providerID: aws:///us-east-1a/i-0abc123def4567890 # (1)!
  source:
    image: ghcr.io/captf-io/aws-machine:v0.1.0-opentofu # (2)!
  identityRef:
    name: aws-prod # (3)!
  jobs:
    activeDeadlineSeconds: 3600
    lockTimeoutSeconds: 300
  variables:
    instance_type: m6i.large # (4)!
  variablesFrom:
    - secretRef:
        name: demo-machine-secrets # (5)!
  drift:
    intervalSeconds: 900 # (6)!
  remediation:
    annotateMachine: true # (7)!
    unhealthyThreshold: 5
    healthCheckIntervalSeconds: 120
```

1. Written once by the controller from the module's `provider_id` output.
   You never set it. See [Provider ID](#provider-id).
2. Required, and immutable: a different image means a new machine.
3. Optional when the owning `TerraformCluster` sets `spec.defaults.identityRef`
   or its own `spec.identityRef`. Immutable.
4. Inline module variables, a JSON object. Immutable, like every field that
   defines the machine.
5. A Secret in this namespace labeled `captf.io/variables=true`. Inline
   `variables` win over it on the same key.
6. Check for drift every 15 minutes. Without it, the cluster's
   `spec.defaults.drift.intervalSeconds`, then the manager's
   `--drift-default-interval`, applies.
7. Ask Cluster API to replace the Machine after 5 unhealthy samples. Needs a
   `MachineHealthCheck`; see [Remediation](#remediation).

## Spec

`spec` must set at least one property, and `spec.source` is always required.
`spec.source`, `spec.identityRef`, `spec.variables` and `spec.variablesFrom`
define the machine and are immutable after creation. `spec.providerID` is set
once. `spec.jobs`, `spec.drift` and `spec.remediation` are operational policy
and stay mutable, so you can change a stuck machine's deadline or its drift
checks without replacing it.

The workspace fields below are shared with other kinds and documented on
[Common Fields](common-fields.md).

| Field | Type | Description |
| --- | --- | --- |
| `spec.providerID` | string | The instance's provider ID, set by the controller. See [Provider ID](#provider-id). **Optional.** **Immutable** once set. **Range:** 1 to 512 characters. |
| `spec.source` | object | The machine-role module image and its pull policy ([Source](common-fields.md#source)). **Required.** **Immutable.** Never inherited from the cluster. |
| `spec.identityRef` | object | The `TerraformClusterIdentity` whose credentials the Jobs use ([Identity reference](common-fields.md#identity-reference)). **Optional.** **Immutable.** **Default:** the owning `TerraformCluster`'s `spec.defaults.identityRef`, else its `spec.identityRef`. |
| `spec.jobs` | object | Tuning of the Jobs that run the module ([Jobs](common-fields.md#jobs)). **Optional.** **Mutable.** **Default:** merged field by field over the `TerraformCluster`'s `spec.defaults.jobs`; fields neither sets take the built-in defaults. |
| `spec.variables` | object | Inline module variables, a JSON object ([Variables](common-fields.md#variables)). **Optional.** **Immutable.** |
| `spec.variablesFrom` | list | ConfigMaps and Secrets that supply module variables ([Variable sources](common-fields.md#variable-sources)). **Optional.** **Immutable.** |
| `spec.drift` | object | How often drift is checked. See [Drift](#drift). **Optional.** **Mutable.** **Default:** merged over the `TerraformCluster`'s `spec.defaults.drift`. |
| `spec.remediation` | object | How an unhealthy instance is signaled to Cluster API. See [Remediation](#remediation). **Optional.** **Mutable.** |

### Provider ID

`spec.providerID` binds the object to one instance. After the first apply
succeeds, the controller copies the module's `provider_id` output into it and
emits a `ProviderIDSet` event. Cluster API then copies it to
`Machine.spec.providerID`, where it must equal the Node's `spec.providerID`
(see [Node providerID
matching](../../module-author/contract/v1alpha1/machine.md#node-providerid-matching-module-authors)).

- The controller writes it only while it is empty and never clears it. If the
  instance disappears, `provider_id` turning `null` leaves the value in place
  and sets `InfrastructureHealthy` to `Unknown` (`ProviderIDMissing`), then to
  `False` (`InstanceTerminated`) if the next sample is `null` too.
- If a later apply returns a different value, the controller keeps the old
  one and sets `OutputsValid=False` with reason `ProviderIDChanged`.
- A state with no inputs hash, from an apply that has not succeeded, does not
  set it, because the retry may replace a tainted instance.

!!! warning "Only the manager can set providerID on an existing object"

    The webhook rejects any update that sets `spec.providerID` from a user
    other than the manager's ServiceAccount, and any change after it is set.
    Create accepts a value because `clusterctl move` recreates objects with
    theirs.

### Drift

`spec.drift` configures the periodic drift check, a refresh and plan that
compares the real instance with the machine's inputs. A machine's drift is
always reported (`DriftDetected`) and never remediated: the instance is
immutable infrastructure, replaced by a rollout rather than patched, so there
is no `action` field. See [Drift](../../user-guide/drift.md) and [Drift and
health](../../concepts/drift-and-health.md).

| Field | Type | Description |
| --- | --- | --- |
| `spec.drift.intervalSeconds` | integer (int32) | Seconds between drift checks. **Optional.** **Mutable.** **Range:** 0 or more; 0 disables drift checks. **Default:** the `TerraformCluster`'s `spec.defaults.drift.intervalSeconds`, else the manager's `--drift-default-interval` (30 minutes), applied at reconcile. |

!!! note "Disabling drift also stops health sampling"

    Health is read from the same refresh Jobs. With `intervalSeconds: 0` and
    `spec.remediation.annotateMachine` not `true`, nothing refreshes the
    machine after provisioning, so `status.unhealthySamples` and
    `InfrastructureHealthy` stop updating. With `annotateMachine: true` the
    machine still refreshes at `healthCheckIntervalSeconds`.

### Remediation

`spec.remediation` lets CAPTF ask Cluster API to replace a bad instance. With
`annotateMachine: true`, CAPTF sets the `cluster.x-k8s.io/remediate-machine`
annotation on the owner Machine when the instance has been unhealthy for
`unhealthyThreshold` consecutive samples, or at once when it is terminated. A
`MachineHealthCheck` that selects the Machine then acts on it. CAPTF also
sets `captf.io/remediation-requested` (value: the reason) so it removes only
its own annotation, which it does when the instance reads `Healthy` again and
the Machine is not being deleted. An annotation someone else set is left
alone. A single-replica control plane refuses the remediation. See [Machine
Remediation](../../user-guide/remediation.md).

| Field | Type | Description |
| --- | --- | --- |
| `spec.remediation.annotateMachine` | boolean | Annotate the owner Machine for remediation. **Optional.** **Mutable.** **Default:** `false`: CAPTF never touches the Machine. |
| `spec.remediation.unhealthyThreshold` | integer (int32) | Consecutive unhealthy samples before the Machine is annotated. A sample is one completed refresh or drift Job; a terminated instance counts on the first sample. **Optional.** **Mutable.** **Range:** 1 to 100. **Default:** 3, applied at reconcile. |
| `spec.remediation.healthCheckIntervalSeconds` | integer (int32) | How often a provisioned machine is refreshed to sample health while `annotateMachine` is `true`, independent of `spec.drift.intervalSeconds`. Ignored when `annotateMachine` is `false`. **Optional.** **Mutable.** **Range:** 60 to 86400. **Default:** 300, applied at reconcile. |

An unhealthy sample is a reading of `InstanceUnhealthy`, `InstanceDegraded` or
`InstanceStopped`. `Healthy` resets the count; `InstancePending`,
`HealthUnknown` and `InstanceTerminated` leave it unchanged (see [Unhealthy
samples](../../concepts/drift-and-health.md#unhealthy-samples)).

## Status

Nothing in `status` is load-bearing: the controller rebuilds every value from
spec, the state Secret and the Job list, so it survives `clusterctl move`.
`status.unhealthySamples` restarts at 0 after a move. Shared workspace status
fields are documented on [Common Fields](common-fields.md#workspace-status).

| Field | Type | Description |
| --- | --- | --- |
| `status.conditions` | list | The object's conditions, keyed by `type`. **Range:** at most 32. See [Conditions](#conditions). |
| `status.conditions[].type` | string | The condition type, such as `Ready` or `InfrastructureHealthy`. |
| `status.conditions[].status` | string | `True`, `False` or `Unknown`. |
| `status.conditions[].reason` | string | A CamelCase reason for the last change. Every reason is on [Conditions](../conditions.md). |
| `status.conditions[].message` | string | A human-readable detail. |
| `status.conditions[].lastTransitionTime` | time | When `status` last changed. |
| `status.conditions[].observedGeneration` | integer | The `metadata.generation` the condition was computed for. |
| `status.observedGeneration` | integer | The `metadata.generation` the controller last reconciled ([Observed generation](common-fields.md#observed-generation)). |
| `status.initialization` | object | `provisioned` is true once the infrastructure is provisioned, then latched for the object's life ([Initialization](common-fields.md#initialization)). The `Provisioned` printer column shows it. |
| `status.activeJob` | object | The Job running now, if any ([Active Job](common-fields.md#active-job)). |
| `status.lastRun` | object | The newest finished Job and its result ([Last run](common-fields.md#last-run)). |
| `status.lastDriftCheck` | time | When the last drift check completed ([Drift checks and refreshes](common-fields.md#drift-checks-and-refreshes)). |
| `status.lastRefresh` | time | When the last refresh or drift Job completed, or the apply that stood in for the refresh ([Drift checks and refreshes](common-fields.md#drift-checks-and-refreshes)). |
| `status.pendingRefreshes` | integer | Consecutive health samples that read pending; spaces the refreshes while the instance is pending ([Drift checks and refreshes](common-fields.md#drift-checks-and-refreshes)). |
| `status.stateSecretSuffix` | string | The suffix of the state Secret ([State](common-fields.md#state)). |
| `status.observedStateSerial` | integer | The Terraform state serial the outputs were read from ([State](common-fields.md#state)). |
| `status.lastRestoredSerial` | integer | The serial of the last state restore ([State](common-fields.md#state)). |
| `status.stateBackups` | list | Backups of the state available to restore ([State](common-fields.md#state)). |
| `status.source` | object | What the last Job ran: the image reference, the digest it resolved to and the runtime version ([Image in use](common-fields.md#image-in-use)). |
| `status.addresses` | list | The instance's addresses, from the module's `addresses` output, in the controller's canonical order. **Range:** 1 to 256 items. |
| `status.addresses[].type` | string | The Cluster API address type: `Hostname`, `ExternalIP`, `InternalIP`, `ExternalDNS` or `InternalDNS`. |
| `status.addresses[].address` | string | The address itself. |
| `status.failureDomain` | string | The failure domain the instance actually runs in, from the module's `failure_domain` output. Must equal `Machine.spec.failureDomain` when that is set, else `OutputsValid=False` (`FailureDomainMismatch`). **Range:** 1 to 256 characters. |
| `status.interruptible` | boolean | True for a spot or preemptible instance; Cluster API then labels the Node `cluster.x-k8s.io/interruptible`. Written as `false` when the module does not say. |
| `status.unhealthySamples` | integer (int32) | Consecutive unhealthy health samples. Unset while the instance is healthy. **Range:** 1 or more when set. Drives [remediation](#remediation). |

If a module output breaks the contract (a bad `addresses`, `failure_domain` or
`interruptible`), the controller keeps the previous status value for that
field and sets `OutputsValid=False`.

??? example "Example status"

    ```yaml
    status:
      observedGeneration: 2
      initialization:
        provisioned: true
      addresses:
        - type: InternalIP
          address: 10.0.12.34
        - type: InternalDNS
          address: ip-10-0-12-34.ec2.internal
      failureDomain: us-east-1a
      interruptible: false
      lastRefresh: "2026-10-02T09:41:07Z"
      lastDriftCheck: "2026-10-02T09:41:07Z"
      conditions:
        - type: Ready
          status: "True"
          reason: Ready
          lastTransitionTime: "2026-10-02T08:12:55Z"
          observedGeneration: 2
        - type: InfrastructureHealthy
          status: "True"
          reason: Healthy
          lastTransitionTime: "2026-10-02T08:12:55Z"
          observedGeneration: 2
        - type: DriftDetected
          status: "False"
          reason: NoDrift
          lastTransitionTime: "2026-10-02T09:41:07Z"
          observedGeneration: 2
    ```

## Conditions

`Ready` is the only condition Cluster API reads. The others say why `Ready` is
what it is. Every reason is listed on [Conditions](../conditions.md); this
page covers what each type means for a machine.

| Type | Meaning |
| --- | --- |
| [`Ready`](../conditions.md#ready) | `True` when the instance is provisioned and healthy. Before `status.initialization.provisioned` first holds, it summarizes `DependenciesReady`, `IdentityAllowed`, `CredentialsMirrored`, `RunnerRBACReady`, `ApplyJobSucceeded`, `StateReadable`, `OutputsValid`, `InfrastructureHealthy` and `Deleting`. After that it follows `InfrastructureHealthy` and `Deleting` only, so a failed re-apply or drift Job does not flip the Machine's `InfrastructureReady`. `False` when an input is `False`, `Unknown` when an input is `Unknown`. |
| [`DependenciesReady`](../conditions.md#dependenciesready) | `True` when the owner Machine and Cluster, the `TerraformCluster` exports, the bootstrap data Secret and the variable sources are all available. `Unknown` while it waits for one of them; `False` when the owner is missing, mismatched or not yet set, the Cluster is not a `TerraformCluster`, or a variable source is missing or invalid. |
| [`IdentityAllowed`](../conditions.md#identityallowed) | `True` when the resolved identity exists and allows this namespace. `False` when no identity is set, it is missing, not allowed or has no Secret. `Unknown` when the check could not be completed. |
| [`CredentialsMirrored`](../conditions.md#credentialsmirrored) | `True` when the identity's credentials are copied into the namespace for the Jobs. `False` when the copy failed; `Unknown` while the mirror is pending. |
| [`RunnerRBACReady`](../conditions.md#runnerrbacready) | `True` when the Job's ServiceAccount and RBAC are in place. `False` when they cannot be created or an override ServiceAccount lacks the `captf.io/runner=true` label. Never `Unknown`. |
| [`ApplyJobSucceeded`](../conditions.md#applyjobsucceeded) | The outcome of the newest apply or destroy. `Unknown` before the first apply completes or while the run waits for a lease or the cluster; a running apply keeps the last result. |
| [`StateReadable`](../conditions.md#statereadable) | `True` when the Terraform state Secret reads cleanly. `False` when it is encrypted, corrupt, inconsistent, lost or locked. `Unknown` when no state exists yet. |
| [`RestoreJobSucceeded`](../conditions.md#restorejobsucceeded) | The outcome of a state restore requested with `captf.io/restore-state`. Set only once a restore is requested; `Unknown` while the restore waits for a run lease. Never feeds `Ready`. |
| [`OutputsValid`](../conditions.md#outputsvalid) | `True` when the module's outputs satisfy the contract. `False` for missing or invalid outputs, a failure domain mismatch or a changed provider ID. `Unknown` while required outputs are `null`. |
| [`InfrastructureHealthy`](../conditions.md#infrastructurehealthy) | The instance's health from the module's `health` output. `False` while provisioning, pending, unhealthy, degraded, stopped or terminated; `Unknown` before the first apply, when the module reports unknown, or when `provider_id` first turns `null`. |
| [`DriftJobSucceeded`](../conditions.md#driftjobsucceeded) | The outcome of the newest refresh or drift Job. `Unknown` before the first check, while a Job runs or waits for a lease, or when the durable inputs Secret is missing. Never feeds `Ready`. |
| [`DriftDetected`](../conditions.md#driftdetected) | `True` when a drift check found changes (reported, pending remediation or being remediated), `False` when it found none, `Unknown` before the first check. Never feeds `Ready`. |
| [`Paused`](../conditions.md#paused) | `True` when the object or its Cluster is paused; no Job starts. `False` otherwise; never `Unknown`. Never feeds `Ready`. |
| [`Deleting`](../conditions.md#deleting) | `True` once deletion has started, `False` before; never `Unknown`. Negative polarity: `True` makes `Ready` `False`. |

## Printer columns

`kubectl get terraformmachines` shows these columns. `-o wide` adds `Image`.

| Column | Source | Description |
| --- | --- | --- |
| `Cluster` | `.metadata.labels['cluster.x-k8s.io/cluster-name']` | The owning Cluster. |
| `Machine` | the `Machine` entry in `.metadata.ownerReferences` | The Machine that owns this object. |
| `Ready` | the `Ready` condition's `status` | `True`, `False` or `Unknown`. |
| `Provisioned` | `.status.initialization.provisioned` | Whether the infrastructure is provisioned. |
| `ProviderID` | `.spec.providerID` | The instance's provider ID. |
| `Image` (wide) | `.spec.source.image` | The module image. |
| `Age` | `.metadata.creationTimestamp` | Time since creation. |

## Validation

The admission webhook enforces these rules on create, update and delete. A
rejected request lists every violation it found. The CRD schema declares no
defaults; defaults come from the controller, the cluster and the manager flags
as noted in the field tables.

- `spec.source.image` is required and must parse as an image reference. The
  registry and content are not checked. Checked on create and update.
- `spec.source`, `spec.identityRef`, `spec.variables` and `spec.variablesFrom`
  are immutable. `variables` compares by value, so reordered keys or
  whitespace are no change. Checked on update.
- `spec.providerID` can change only from empty to non-empty, and only by the
  manager's ServiceAccount. Create accepts any value. Checked on update.
- `spec.jobs`: neither the container nor the pod security context may weaken
  the hardened defaults (privileged, privilege escalation, added capabilities,
  a writable root filesystem, `procMount: Unmasked`, running as root, an
  `Unconfined` seccomp profile, a Windows host process). Checked on create,
  and update when `spec.jobs` changed.
- `spec.jobs.lockTimeoutSeconds` must be less than `activeDeadlineSeconds`. A
  lone value is compared with the other's built-in default. A merge with the
  cluster's defaults is checked at reconcile, not here. Checked on create, and
  update when `spec.jobs` changed.
- `spec.variables` is a JSON object of at most 256 keys. Each key is a
  Terraform identifier that is not a `captf_` name, a `machine` role contract
  input or a module meta-argument. Checked on create and update.
- Each `spec.variablesFrom` entry sets exactly one of `configMapRef` and
  `secretRef`. Checked on create and update.
- `spec` must set at least one property. `spec.providerID` is 1 to 512
  characters. `spec.drift.intervalSeconds` is 0 or more.
  `spec.remediation.unhealthyThreshold` is 1 to 100.
  `spec.remediation.healthCheckIntervalSeconds` is 60 to 86400. Checked on
  create and update.
- A delete is refused while a Machine that is not itself being deleted
  references the object through `spec.infrastructureRef`. Delete the Machine
  instead. Checked on delete.

Metadata changes are always allowed: KubeadmControlPlane syncs labels and
annotations on every reconcile, and `clusterctl move` annotates an object
before it deletes it. A `jobs` policy stored before a rule existed does not
block later updates, because it is checked only when it changes, and never on
an object that is being deleted.

The delete rule has two exceptions. An object that no Machine references
(for example, its Machine is gone) can always be deleted. An object with the
`clusterctl move` delete annotation can be deleted while its Cluster is
paused. The annotation alone is not enough.

## Lifecycle

**Create.** Cluster API clones the template and creates the object with the
`cluster.x-k8s.io/cluster-name` label and an owner reference to the Machine.
The manager adds the finalizer, resolves the Cluster and `TerraformCluster`,
waits for the cluster's infrastructure, its exports and the bootstrap data
Secret, then starts an apply Job. Once the state carries a successful apply, the module's `provider_id` is
non-null and its health is not `pending`, the machine is provisioned. See [The reconcile
lifecycle](../../concepts/lifecycle.md) and [Job inputs](../../concepts/inputs.md).

**Change.** The machine definition is immutable, and the first apply's inputs
are pinned in a durable Secret: changing the cluster later does not re-apply
the machine. To change an instance, change the template and roll the Machine
through its MachineDeployment or KubeadmControlPlane. Policy fields
(`jobs`, `drift`, `remediation`) can change at any time.
Health and drift are sampled on the timers above.

**Delete.** Delete the Machine, not the `TerraformMachine`. Cluster API drains
the node and runs the lifecycle hooks, then deletes the infrastructure
object. The manager runs a destroy Job from the durable inputs, so it works
even when the Machine, the bootstrap Secret or the Cluster is already gone, then
removes the state and the finalizer. A `TerraformCluster` waits for its
machines to go before its own destroy. See [Deletion
order](../../concepts/lifecycle.md#deletion-order).
If state is missing or unreadable, deletion is held until you set
`captf.io/abandon-infrastructure` (see
[Annotations and labels](../annotations-labels.md)).

!!! related "See also"

    - [Common Fields](common-fields.md) for the shared workspace fields.
    - [TerraformMachineTemplate](terraformmachinetemplate.md) for how Cluster
      API creates machines.
    - [TerraformCluster](terraformcluster.md) for `spec.defaults`, which a
      machine inherits.
    - [TerraformClusterIdentity](terraformclusteridentity.md) for the
      credentials an identity holds.
    - [The Kinds](../../concepts/kinds.md)
    - [Drift and Health](../../concepts/drift-and-health.md)
    - [Machine Remediation](../../user-guide/remediation.md) and
      [Drift](../../user-guide/drift.md)
    - [Machine role contract](../../module-author/contract/v1alpha1/machine.md)
    - [Conditions](../conditions.md) and
      [Annotations and labels](../annotations-labels.md)
