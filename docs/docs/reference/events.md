---
description: "Look up every Kubernetes Event the CAPTF manager and runner record: reason, type, object, when it fires and what to do."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/calendar-clock
subtitle: "Every event the manager emits"
hide:
  - toc
---

# Events

CAPTF records a Kubernetes Event for each step in the life of an object: the
manager once per transition, and a Job's runner in real time while the Job
runs. This page lists every reason, grouped by situation. Jump to:
[lifecycle](#lifecycle-and-readiness), [Jobs](#jobs),
[ordering and leases](#ordering-and-leases), [plans and approvals](#plans-and-approvals),
[state](#state), [drift and health](#drift-and-health),
[identity and credentials](#identity-and-credentials),
[deletion](#deletion), [pools and templates](#pools-and-templates),
[runner events](#runner-events).

## Reading events

Events are `events.k8s.io/v1` objects recorded on the CAPTF object they are
about. Read them in order with `kubectl events`:

```sh
kubectl events --for terraformcluster/<name> -n <namespace>
kubectl events --for terraformmachine/<name> -n <namespace>
kubectl events --for terraformmachinepool/<name> -n <namespace>
kubectl events --for terraformmachinetemplate/<name> -n <namespace>
kubectl events --for terraformclusteridentity/<name> -n default
```

`kubectl describe` shows the same events at the end of its output. A
`TerraformClusterIdentity` is cluster-scoped, so its events land in the
`default` namespace. Add `-o wide` to see which events the manager recorded
(`captf-manager`) and which a runner did (`captf.io/runner`).

Three rules hold for every event:

- The manager emits an event once per transition or occurrence, never on
  every reconcile. A reason that appears again means the thing happened
  again.
- A condition that first appears emits an event only when it starts in its
  bad state, so a new object's first reconcile is quiet.
- Notes never carry credentials, tfvars, outputs, plan values or raw
  stderr.

Where a table says "any provisioned kind", the event is recorded on a
`TerraformCluster`, `TerraformMachine` or `TerraformMachinePool`. The
**Type** column is the Kubernetes event type: `Normal` reports progress,
`Warning` reports something that needs a look. For a Warning, the
**Action** column says what to check next; the condition that backs the
event is in [Conditions](conditions.md).

!!! note "Events expire"

    Kubernetes keeps events for about an hour by default. For history, read
    the object's conditions and `status.lastRun`, or ship events to your
    log pipeline.

## Lifecycle and readiness

| Reason | Type | On | Fires when | Action |
| --- | --- | --- | --- | --- |
| `Provisioned` | Normal | any provisioned kind | `Provisioned` latched true: the first apply finished and the infrastructure exists. | None. |
| `InputsChanged` | Normal | any provisioned kind | The inputs hash differs from the state's and an apply of the new inputs starts. | None. See [Inputs](../concepts/inputs.md). |
| `ControlPlaneEndpointSet` | Normal | `TerraformCluster` | `spec.controlPlaneEndpoint` was written from the module output. | None. |
| `FailureDomainsChanged` | Normal | `TerraformCluster` | `status.failureDomains` changed. | None. |
| `ProviderIDSet` | Normal | `TerraformMachine`, `TerraformMachinePool` | `spec.providerID` was written. A pool's value can change later. | None. |
| `Paused` | Normal | any provisioned kind | The `Paused` condition became True. Reconciliation stops starting Jobs. | Resume when ready: clear the pause on the object or its `Cluster`. |
| `Resumed` | Normal | any provisioned kind | `Paused` went from True to False. Reconciliation resumes. | None. |
| `OutputsInvalid` | Warning | any provisioned kind | The module's outputs broke the contract. | Fix the module output named in the note. See [`OutputsValid`](conditions.md#outputsvalid). |
| `ConditionChanged` | Normal or Warning | any provisioned kind | Any owned condition without a more specific reason changed status or reason. Warning when it moved into its bad state, Normal otherwise. | For a Warning, read the condition named in the note. |
| `DigestPinned` | Normal | any provisioned kind | An image digest was recorded on the durable inputs Secret, or pinned again after an apply of a mutable kind. | None. |
| `DigestUnknown` | Warning | any provisioned kind | No digest could be pinned, or an operation runs the `spec` reference for lack of one. | Check that the registry is reachable and the reference resolves. |

## Jobs

| Reason | Type | On | Fires when | Action |
| --- | --- | --- | --- | --- |
| `JobCreated` | Normal | any provisioned kind | A Job started. The note gives the operation, attempt, image and why. | None. |
| `JobSucceeded` | Normal | any provisioned kind | An apply, destroy, refresh or drift Job succeeded. | None. |
| `JobFailed` | Warning | any provisioned kind | A Job failed, or an apply or destroy could not start. | Read the Job logs and `status.lastRun`. See the [job failures runbook](../operator-guide/runbooks/job-failures.md). |
| `JobDeadlineExceeded` | Warning | any provisioned kind | A Job hit `activeDeadlineSeconds`. | Find the slow step in the runner events, then raise the deadline or fix the module. See the [slow jobs runbook](../operator-guide/runbooks/slow-jobs.md). |
| `JobInterrupted` | Warning | any provisioned kind | Something outside CAPTF stopped the Job, such as a node drain, an eviction or a deletion. CAPTF retries without backoff. | None if it was planned. Otherwise check node pressure and preemption. |
| `StuckJobDeleted` | Warning | any provisioned kind | A Job that could never start, because its per-run Secret is missing, was deleted so it can start again. | None. Repeats mean something removes the Secret. |

## Ordering and leases

An object runs one operation at a time, and a machine waits for its
cluster. These events say what an operation waits for. See
[Leases](../concepts/jobs/leases.md).

| Reason | Type | On | Fires when | Action |
| --- | --- | --- | --- | --- |
| `WaitingForRunLease` | Normal | any provisioned kind | Another live Job holds the object's run lease. | Wait. If no Job is running, see the [stale lock runbook](../operator-guide/runbooks/stale-lock.md). |
| `WaitingForClusterOperation` | Normal | `TerraformMachine`, `TerraformMachinePool` | A machine's apply or destroy waits for its `TerraformCluster`'s apply or destroy. | Wait. Check the cluster if it never ends. |
| `WaitingForMachineOperations` | Normal | `TerraformCluster` | A cluster's apply or destroy waits for its machines' applies and destroys in flight. | Wait. Check the machines if it never ends. |

## Plans and approvals

These events belong to the destructive-plan guard and to `applyPolicy:
Manual`. See [Approvals](../concepts/approvals/README.md).

| Reason | Type | On | Fires when | Action |
| --- | --- | --- | --- | --- |
| `PlanReady` | Normal | `TerraformCluster` | A plan Job planned a change under `applyPolicy: Manual`. The note has the counts, the plan hash and the approve command. Once per plan Job. | Review the plan, then approve it. |
| `PlanApproved` | Normal | `TerraformCluster` | The apply of an approved plan started. | None. |
| `PlanApplied` | Normal | `TerraformCluster` | The approved plan was applied and its approval annotation removed. | None. |
| `PlanChanged` | Warning | `TerraformCluster` | An approved apply planned other changes and stopped before applying them. Once per such Job. | Review the new plan and approve it again. |
| `DestructivePlanBlocked` | Warning | `TerraformCluster` | An apply stopped before a plan that deletes or replaces resources. Once per blocked Job, in place of `JobFailed`. | Read the plan and approve it if the deletes are intended. See [Destructive guard](../concepts/approvals/destructive-guard.md). |
| `DestructivePlanApprovalConsumed` | Normal | `TerraformCluster` | The approved destructive apply succeeded and its approval annotation was removed. | None. |

`DestructivePlanBlocked` is also recorded for a `TerraformMachinePool`
apply that would change the cluster's exports. The pool keeps applying with
the exports of its last successful apply until you approve the change. If an
earlier apply may have left such a change partly applied, the pool waits for
the approval, as a cluster does.

## State

See [State](../concepts/state.md) and
[Backups](../concepts/secret-management/backups.md).

| Reason | Type | On | Fires when | Action |
| --- | --- | --- | --- | --- |
| `StateAdopted` | Normal | any provisioned kind | The state written by a successful apply was adopted with its new inputs hash. | None. |
| `StateBackedUp` | Normal | any provisioned kind | A new state serial was copied into a backup. Once per backup. | None. |
| `StateRestored` | Normal | any provisioned kind | A restore Job pushed a backup into the backend and the `captf.io/restore-state` annotation was removed. | None. |
| `StateRestoreFailed` | Warning | any provisioned kind | A restore Job failed. CAPTF does not retry it for the same serial. | Read the restore Job logs. See the [state restore runbook](../operator-guide/runbooks/state-restore.md). |
| `StateLocked` | Warning | any provisioned kind | Something else holds the state lock (`StateReadable` False, reason `StateLocked`). | Wait, or find the holder. See the [stale lock runbook](../operator-guide/runbooks/stale-lock.md). |
| `ForceUnlocked` | Warning | any provisioned kind | CAPTF force-unlocked a stale state lock. | Find out why the previous Job died. Alert: [`CAPTFForceUnlocks`](alerts.md#captfforceunlocks). |
| `StateUnreadable` | Warning | any provisioned kind | The state could not be read. | See the [state unreadable runbook](../operator-guide/runbooks/state-unreadable.md). Alert: [`CAPTFStateUnreadable`](alerts.md#captfstateunreadable). |
| `StateLost` | Warning | any provisioned kind | A provisioned object's state is gone or carries no inputs hash (`StateReadable` False, reason `StateLost`). | Restore from a backup. See the [total state loss runbook](../operator-guide/runbooks/total-state-loss.md). |
| `OwnerReferencesRepaired` | Normal | any provisioned kind | Secrets of the object (state, backups, durable inputs, plan key or its credential mirror entry) had no owner reference, or one to an earlier UID, as a management-cluster restore leaves them. They are owned by the object again. | None. See the [move runbook](../operator-guide/runbooks/move.md). |

## Drift and health

See [Drift and health](../concepts/drift-and-health.md).

| Reason | Type | On | Fires when | Action |
| --- | --- | --- | --- | --- |
| `DriftDetected` | Warning | any provisioned kind | A drift check found a difference. Once per finding. | Read the drift plan summary. With `drift.action: Report` you decide; with `Remediate` CAPTF applies. Alert: [`CAPTFClusterDrift`](alerts.md#captfclusterdrift). |
| `DriftRemediationStarted` | Normal | any provisioned kind | An apply that remediates drift started. | None. |
| `DriftResolved` | Normal | any provisioned kind | `DriftDetected` went from True to False. | None. |
| `InstanceHealthy` | Normal | any provisioned kind | `InfrastructureHealthy` became True. | None. |
| `InstanceUnhealthy` | Warning | any provisioned kind | `InfrastructureHealthy` became False for an unhealthy, degraded, stopped or terminated instance. | Check the instance in the cloud console. See [`InfrastructureHealthy`](conditions.md#infrastructurehealthy). |
| `RemediationRequested` | Warning | `TerraformMachine` | CAPTF annotated the owner `Machine` with `cluster.x-k8s.io/remediate-machine`. | Cluster API replaces the machine if a `MachineHealthCheck` acts on it. |
| `RemediationWithdrawn` | Normal | `TerraformMachine` | The instance read healthy again and CAPTF removed the annotation it set. | None. |

## Identity and credentials

See [Identity and credentials](../operator-guide/runbooks/identity-and-credentials.md).

| Reason | Type | On | Fires when | Action |
| --- | --- | --- | --- | --- |
| `IdentityNotAllowed` | Warning | any provisioned kind | The identity does not allow the object's namespace, or does not exist. | Add the namespace to the identity's allowed namespaces. See [`IdentityAllowed`](conditions.md#identityallowed). |
| `IdentitySecretFound` | Normal | `TerraformClusterIdentity` | The identity's credentials Secret appeared. | None. |
| `IdentitySecretNotFound` | Warning | `TerraformClusterIdentity` | The identity's credentials Secret went missing. | Recreate the Secret. |
| `MirrorCreated` | Normal | any provisioned kind | The credential mirror of the namespace was created on behalf of the object. | None. |
| `MirrorRemoved` | Normal | any provisioned kind | The credential mirror of the namespace was deleted on behalf of the object. | None. |

## Deletion

See [Deletion](../concepts/deletion/README.md).

| Reason | Type | On | Fires when | Action |
| --- | --- | --- | --- | --- |
| `DeletionStarted` | Normal | any provisioned kind | The first reconcile with a `deletionTimestamp`. | None. |
| `Destroyed` | Normal | any provisioned kind | The destroy succeeded and cleanup ran. | None. |
| `FinalizerRemoved` | Normal | any provisioned kind | The finalizer was removed. The object goes away. | None. |
| `InfrastructureAbandoned` | Warning | any provisioned kind | A deletion held on lost or unreadable state, or whose destroy failed or cannot start, was released by `captf.io/abandon-infrastructure` naming the object's UID. The finalizer was removed without a destroy. | Delete the orphaned cloud resources by hand. See [Manual finalizer](../concepts/deletion/manual-finalizer.md). |

## Pools and templates

| Reason | Type | On | Fires when | Action |
| --- | --- | --- | --- | --- |
| `ReplicasWrittenBack` | Normal | `TerraformMachinePool` | An autoscaled pool's observed `replicas` output was written to `MachinePool.spec.replicas`. The note reads `X → Y`. | None. |
| `ReplicasManagedExternally` | Warning | `TerraformMachinePool` | The autoscaler annotations are valid, but another owner holds `replicas-managed-by`. CAPTF does not write `spec.replicas` back. | Decide which controller owns the replica count. |
| `CapacityResolved` | Normal | `TerraformMachineTemplate` | The template's `capacity` or `nodeInfo` changed from its image labels. | None. |
| `ImageInspectFailed` | Warning | `TerraformMachineTemplate` | The registry could not be read for capacity. | Check registry access and credentials. |

## Runner events

A Job's runner posts its own progress as events on the object the Job is
for, related to the Job itself. They fire in real time, which makes them the
quickest way to see which step a long Job is in. The manager enables them
with `--runner-events`, which defaults to `true`; see
[Manager flags](manager-flags.md). The runner needs `create` on `events` in
its ClusterRole, which the shipped manifests grant.

| Reason | Type | Fires when |
| --- | --- | --- |
| `RunStarted` | Normal | The runtime is ready and the first step is about to run. The note gives the operation, image reference and runtime version. |
| `StepStarted` | Normal | A runtime step started. |
| `StepSucceeded` | Normal | A runtime step finished. |
| `StepFailed` | Warning | A runtime step failed. The note is the runner's curated failure summary, never raw stderr. |
| `PlanSummary` | Normal | The runner parsed a plan (drift, or a guarded cluster apply). The note has counts only. |
| `ResourcesChanged` | Normal | An apply or destroy step finished. The note has the counts from the runtime's summary line. |
| `RunFinished` | Normal or Warning | The run ended. The note gives the result and total duration. Warning when the run did not succeed. |

!!! note "Runner events are best effort"

    Each request has a two-second timeout. After three consecutive
    failures the runner stops emitting for the rest of that run. Emission
    never fails or slows the run. Turn `--runner-events` off on a large
    fleet: a single scheduled drift check alone produces several events.

For where to read events during an incident, see
[Observability](../operator-guide/observability.md#reading-events).
