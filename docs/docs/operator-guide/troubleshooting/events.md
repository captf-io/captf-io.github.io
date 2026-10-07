---
title: "Every CAPTF Event and What to Do"
description: Read the Warning and informational events CAPTF emits, with what each means and what to do about it.
hide:
  - toc
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/bell
subtitle: "Every event and what it means"
---

# Events

The controller records an event when something happens to an object, once
per transition or occurrence rather than on every reconcile. Read them with:

```sh
kubectl events -n <ns> --for <kind>/<name>
```

Most `Warning` events repeat what a condition already says, at the moment
it changed, and name the Job involved. Use them for the timeline: what
happened first. The [Events reference](../../reference/events.md) is the
generated list; this page adds what to do.

!!! note "Events expire; conditions do not"

    Kubernetes keeps events for a limited time (one hour by default), so
    the condition is the record to rely on. Messages never carry
    credentials, variable values, output values or raw stderr, and are cut
    at 512 bytes.

## Warning events

| Reason | Emitted on | When | What to do | See |
| --- | --- | --- | --- | --- |
| `ConditionChanged` | TerraformCluster, TerraformMachine, TerraformMachinePool | Any other owned condition changed. It is a `Warning` when the condition enters its bad state, `Normal` otherwise. The note reads `<Type>: <Status>/<Reason>: <message>`. | Find the type and reason in the [conditions table](conditions.md). | [Conditions](conditions.md) |
| `DestructivePlanBlocked` | TerraformCluster, TerraformMachinePool | An apply stopped before a plan that deletes or replaces resources: a cluster apply, or a pool apply of a change of the cluster's exports. Once per blocked Job, in place of `JobFailed`. | Review the plan summary in the condition and approve the `TerraformPlan` it names, or change the inputs. A blocked pool change is held while the pool keeps applying its last exports. | [Destructive-plan guard](../../concepts/approvals/destructive-guard.md) |
| `DigestUnknown` | TerraformCluster, TerraformMachine, TerraformMachinePool | No image digest is pinned, so an operation runs the spec's image reference, or a Job succeeded without a readable digest. | Usually clears after the next successful apply. Pin the image by digest in the spec if you need it fixed. | [Job inputs](../../concepts/inputs.md) |
| `DriftDetected` | TerraformCluster, TerraformMachine, TerraformMachinePool | A drift check found a difference. Once per finding. | Decide whether to accept it or remediate. | [Drift](../../user-guide/drift.md) |
| `ExportsNotPublished` | TerraformCluster | The module's `exports` exceed 64 KiB as compact JSON, so `status.exports` was cleared. | Shrink `exports` in the cluster module. Machines and pools keep reading `exports` from the state and are unaffected. | [TerraformCluster status](../../reference/resources/terraformcluster.md#status) |
| `ForceUnlocked` | TerraformCluster, TerraformMachine, TerraformMachinePool | A Job was started with a stale state lock to force-unlock: its holder pod no longer exists. | Nothing, unless it repeats. Frequent unlocks mean runners are being killed: check evictions and memory limits. | [The state lock](../../concepts/jobs/state-lock.md) |
| `IdentityNotAllowed` | TerraformCluster, TerraformMachine, TerraformMachinePool | `IdentityAllowed` entered `False`, whatever the reason: `IdentityNotFound`, `NamespaceNotAllowed` or `SecretNotFound`. Again when the reason or message changes. | Read the condition's reason and fix it. | [Identity runbook](../runbooks/identity-and-credentials.md) |
| `IdentitySecretNotFound` | TerraformClusterIdentity | The identity's credentials Secret went missing, or lacks a key listed in `spec.requiredKeys`. | Recreate the Secret at `spec.secretRef`, or add the missing keys. | [Identity runbook](../runbooks/identity-and-credentials.md#secretnotfound) |
| `ImageInspectFailed` | TerraformMachineTemplate | The registry could not be read for the template's capacity labels. | Fix the image reference or the registry credentials. | [Templates](../../user-guide/clusterclass.md) |
| `InstanceUnhealthy` | TerraformCluster, TerraformMachine, TerraformMachinePool | `InfrastructureHealthy` became `False` for an unhealthy, degraded, stopped or terminated instance. | Look at the instance. Remediation can replace it. | [Machine remediation](../../user-guide/remediation.md) |
| `JobDeadlineExceeded` | TerraformCluster, TerraformMachine, TerraformMachinePool | A Job hit `activeDeadlineSeconds`. Once per Job. | Raise the deadline or find what hangs. | [Deadlines](../../concepts/jobs/deadlines.md) |
| `JobFailed` | TerraformCluster, TerraformMachine, TerraformMachinePool | A Job failed, or an apply or destroy could not start (`ApplyJobSucceeded` is `False` without a Job). Once per Job. | Read the condition and the Job's logs. | [Failing Jobs](../runbooks/job-failures.md) |
| `JobInterrupted` | TerraformCluster, TerraformMachine, TerraformMachinePool | A Job was stopped from outside: a drain, an eviction or a deletion. It retries without backoff. | Nothing, unless it repeats: find what keeps stopping the pod. | [Retries](../../concepts/jobs/retries.md#counting-failures) |
| `OutputsInvalid` | TerraformCluster, TerraformMachine, TerraformMachinePool | `OutputsValid` entered `False`: `OutputsMissing`, `OutputsInvalid`, `FailureDomainMismatch` or `ProviderIDChanged`. Again when the reason or message changes. | Fix the output named in the condition. | [Module contract](../../module-author/contract/README.md) |
| `PlanChanged` | TerraformCluster | An approved apply planned other changes and stopped before applying them. Once per such approved apply, for `Manual` and `Destructive` plans. | Review the new plan, if any, and approve it. | [Manual plan approval](../../concepts/approvals/manual-approval.md) |
| `RemediationRequested` | TerraformMachine | The owner Machine was annotated with `cluster.x-k8s.io/remediate-machine`. | Expected with a MachineHealthCheck. Check why the instance is unhealthy. | [Machine remediation](../../user-guide/remediation.md) |
| `RetainedStateFound` | TerraformCluster, TerraformMachine, TerraformMachinePool | A new object found Secrets retained from an earlier object of the same kind, namespace and name. It holds on them: no Job runs and nothing is owned or backed up. | Set `spec.adoptRetainedState: true` to adopt them, or delete the Secrets labeled `captf.io/retained-from-uid` to discard them. | [A recreated object holds](../../concepts/deletion/retain.md#a-recreated-object-holds) |
| `ReplicasManagedExternally` | TerraformMachinePool | Valid autoscaler annotations, but another controller owns `spec.replicas`. | Pick one owner for the replicas. | [Machine pools](../../user-guide/machine-pools.md#choose-fixed-replicas-or-autoscaling) |
| `StateLocked` | TerraformCluster, TerraformMachine, TerraformMachinePool | The state lock is held by something other than the object's runner. | Release it with `force-unlock` once the holder is gone. | [Stale lock](../runbooks/stale-lock.md) |
| `StateLost` | TerraformCluster, TerraformMachine, TerraformMachinePool | A provisioned object's state is gone or carries no inputs hash. | Restore a backup. | [Unreadable state](../runbooks/state-unreadable.md#statelost) |
| `StateRestoreFailed` | TerraformCluster, TerraformMachine, TerraformMachinePool | A restore Job failed. It is not retried for the same serial. | Read the Job's logs, then retry with a fresh annotation. | [Other manual actions](../../concepts/approvals/other-manual-actions.md#restore-a-state) |
| `StateUnreadable` | TerraformCluster, TerraformMachine, TerraformMachinePool | The state could not be read: corrupt, encrypted or inconsistent. | See the `StateReadable` reason. | [Unreadable state](../runbooks/state-unreadable.md) |
| `StuckJobDeleted` | TerraformCluster, TerraformMachine, TerraformMachinePool | A Job that could never start, because its per-run Secret was missing and no pod started, was deleted. It starts again. | Nothing, unless it repeats: check quota and API errors in the manager's log. | [Naming and adoption](../../concepts/jobs/naming.md#adopting-a-job-that-exists) |
| `StepFailed` | TerraformCluster, TerraformMachine, TerraformMachinePool (runner) | A runtime step failed. The note carries the runner's curated summary, never raw stderr. Needs `--runner-events`. | Read the Job's logs for the full output. | [Failing Jobs](../runbooks/job-failures.md) |
| `RunFinished` | TerraformCluster, TerraformMachine, TerraformMachinePool (runner) | The run ended. A `Warning` when it did not succeed: failed, interrupted, blocked before a destructive plan, or stopped because the approved plan changed. Needs `--runner-events`. | As for `StepFailed`. | [Failing Jobs](../runbooks/job-failures.md) |

## Informational events

These are `Normal` and need no action. They are the record of what the
controller did.

| Reason | Emitted on | Meaning | See |
| --- | --- | --- | --- |
| `JobCreated` | TerraformCluster, TerraformMachine, TerraformMachinePool | A Job started: op, attempt, image and why. | [Jobs](../../concepts/jobs/README.md) |
| `JobSucceeded` | TerraformCluster, TerraformMachine, TerraformMachinePool | An apply, destroy, refresh or drift Job succeeded. | [Jobs](../../concepts/jobs/README.md) |
| `WaitingForRunLease` | TerraformCluster, TerraformMachine, TerraformMachinePool | An operation waits for the run lease. Once per wait. | [Leases](../../concepts/jobs/leases.md) |
| `WaitingForJobSlot` | TerraformCluster, TerraformMachine, TerraformMachinePool | An operation waits for a Job slot. Once per wait. | [Job limits](../../concepts/jobs/README.md#job-limits) |
| `WaitingForClusterOperation` | TerraformMachine, TerraformMachinePool | An operation waits for its cluster's. | [Leases](../../concepts/jobs/leases.md) |
| `WaitingForMachineOperations` | TerraformCluster | An operation waits for its machines' and pools'. | [Leases](../../concepts/jobs/leases.md) |
| `PlanReady` | TerraformCluster | A `Manual` `TerraformPlan` was created: its name, counts and the approve command. Also when the plan changes nothing and the apply runs without an approval. | [Manual plan approval](../../concepts/approvals/manual-approval.md) |
| `PlanApproved` | TerraformCluster, TerraformMachinePool | Bookkeeping first saw an approval on a `TerraformPlan` of the target, with `approvedBy`. | [Operating the gates](../../concepts/approvals/operating.md#the-terraformplan-lifecycle) |
| `PlanApplied` | TerraformCluster, TerraformMachinePool | The apply of an approved plan succeeded; the plan is `Applied`. | [Operating the gates](../../concepts/approvals/operating.md#the-terraformplan-lifecycle) |
| `PlanSuperseded` | TerraformCluster, TerraformMachinePool | A plan was superseded by a newer plan or became moot. A Warning when it had been approved. | [Operating the gates](../../concepts/approvals/operating.md#the-terraformplan-lifecycle) |
| `DeletionStarted` | TerraformCluster, TerraformMachine, TerraformMachinePool | The first reconcile with a deletion timestamp. | [Deletion and Teardown](../../concepts/deletion/README.md) |
| `Destroyed` | TerraformCluster, TerraformMachine, TerraformMachinePool | The destroy succeeded and cleanup ran. | [Cleanup](../../concepts/deletion/cleanup.md) |
| `FinalizerRemoved` | TerraformCluster, TerraformMachine, TerraformMachinePool | The finalizer was removed: after a destroy, with no state, or without an owner. | [Order and finalizers](../../concepts/deletion/order.md#the-finalizer) |
| `InfrastructureRetained` | TerraformCluster, TerraformMachine, TerraformMachinePool | A deletion with `spec.deletionPolicy: Retain` ended without a destroy. The note says how many state, backup and durable inputs Secrets were kept and the `captf.io/retained-from-uid` label. The infrastructure keeps running. | [What Retain keeps](../../concepts/deletion/retain.md#what-retain-keeps) |
| `RetainedStateAdopted` | TerraformCluster, TerraformMachine, TerraformMachinePool | `spec.adoptRetainedState: true` made the object remove the `captf.io/retained-from-uid` label from retained Secrets. It owns them from the next reconcile. | [Adopting retained state](../../concepts/deletion/retain.md#adopting-retained-state) |
| `Paused` | TerraformCluster, TerraformMachine, TerraformMachinePool | The `Paused` condition became `True`. | [Order and finalizers](../../concepts/deletion/order.md#pause-stops-a-deletion) |
| `Resumed` | TerraformCluster, TerraformMachine, TerraformMachinePool | The `Paused` condition became `False` again. | [Lifecycle](../../concepts/lifecycle.md#the-paused-branch) |
| `Provisioned` | TerraformCluster, TerraformMachine, TerraformMachinePool | `status.initialization.provisioned` latched true. | [Lifecycle](../../concepts/lifecycle.md) |
| `ProviderIDSet` | TerraformMachine, TerraformMachinePool | `spec.providerID` was written. | [Machine role](../../module-author/contract/v1alpha1/machine.md) |
| `ControlPlaneEndpointSet` | TerraformCluster | `spec.controlPlaneEndpoint` was written from the module output. | [Cluster role](../../module-author/contract/v1alpha1/cluster.md) |
| `FailureDomainsChanged` | TerraformCluster | `status.failureDomains` changed. | [Cluster role](../../module-author/contract/v1alpha1/cluster.md) |
| `InputsChanged` | TerraformCluster, TerraformMachine, TerraformMachinePool | The inputs hash differs from the state's and an apply starts. | [Choosing the operation](../../concepts/jobs/operations.md) |
| `DigestPinned` | TerraformCluster, TerraformMachine, TerraformMachinePool | An image digest was recorded, or re-pinned after an apply. | [Job inputs](../../concepts/inputs.md) |
| `StateAdopted` | TerraformCluster, TerraformMachine, TerraformMachinePool | The state a successful apply wrote was adopted with its inputs hash. | [Terraform State](../../concepts/state.md) |
| `StateBackedUp` | TerraformCluster, TerraformMachine, TerraformMachinePool | A new state serial was copied into a backup. | [Backups](../../concepts/secret-management/backups.md) |
| `StateRestored` | TerraformCluster, TerraformMachine, TerraformMachinePool | A restore Job pushed a backup and the annotation was removed. | [State restore](../runbooks/state-restore.md) |
| `DriftResolved` | TerraformCluster, TerraformMachine, TerraformMachinePool | `DriftDetected` went from `True` to `False`. | [Drift](../../user-guide/drift.md) |
| `DriftRemediationStarted` | TerraformCluster, TerraformMachine, TerraformMachinePool | An apply remediating drift started. | [Drift](../../user-guide/drift.md) |
| `InstanceHealthy` | TerraformCluster, TerraformMachine, TerraformMachinePool | `InfrastructureHealthy` became `True`. | [Drift and health](../../concepts/drift-and-health.md) |
| `RemediationWithdrawn` | TerraformMachine | The instance read healthy again and the remediation annotation was removed. | [Machine remediation](../../user-guide/remediation.md) |
| `ReplicasWrittenBack` | TerraformMachinePool | An autoscaled pool's observed replicas were written to `MachinePool.spec.replicas`. | [Machine pools](../../user-guide/machine-pools.md) |
| `IdentitySecretFound` | TerraformClusterIdentity | The credentials Secret appeared. | [Identities](../../user-guide/identities.md) |
| `MirrorCreated` | TerraformCluster, TerraformMachine, TerraformMachinePool | The namespace's credential mirror was created for this object. | [Identities](../../user-guide/identities.md#how-credentials-reach-a-job) |
| `OwnerReferencesRepaired` | TerraformCluster, TerraformMachine, TerraformMachinePool | Secrets of this object (state, backups, durable inputs, plan key, its mirror entry) were owned by it again after a restore, or because a chunk had no owner reference. | [State adoption](../../concepts/secret-management/state.md#adoption) |
| `MirrorRemoved` | TerraformCluster, TerraformMachine, TerraformMachinePool | The mirror was deleted: its last user went, or the identity no longer allows the namespace. | [Cleanup](../../concepts/deletion/cleanup.md) |
| `CapacityResolved` | TerraformMachineTemplate | A template's capacity or node info changed from its image labels. | [Templates](../../user-guide/clusterclass.md) |
| `RunStarted` | TerraformCluster, TerraformMachine, TerraformMachinePool (runner) | The runtime is ready and the first step is about to run. | [Job Environment](../../reference/environment.md) |
| `StepStarted` | TerraformCluster, TerraformMachine, TerraformMachinePool (runner) | A runtime step started. | [Job Environment](../../reference/environment.md) |
| `StepSucceeded` | TerraformCluster, TerraformMachine, TerraformMachinePool (runner) | A runtime step finished. | [Job Environment](../../reference/environment.md) |
| `PlanSummary` | TerraformCluster, TerraformMachine, TerraformMachinePool (runner) | A plan the runner parsed: counts only. | [Job Environment](../../reference/environment.md) |
| `ResourcesChanged` | TerraformCluster, TerraformMachine, TerraformMachinePool (runner) | What an apply or destroy step changed: counts only. | [Job Environment](../../reference/environment.md) |

!!! related "See also"

    - [Conditions](conditions.md).
    - [Observability](../observability.md).
