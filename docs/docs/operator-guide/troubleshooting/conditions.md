---
title: "Condition Types, Reasons and Actions"
description: Look up every CAPTF condition type, status and reason with its meaning, likely cause, action and a link to the deeper page.
hide:
  - toc
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/badge-info
subtitle: "Every reason, cause and fix"
---

# Conditions

Every condition CAPTF sets, with what each reason means and what to do about
it. Find the object's condition type below, then its status and reason. The
tables list **every** status and reason a type can take, so a reason that is
healthy is here too. [Start here](README.md#start-here) explains how to get
from `Ready` to the right row.

Jump to: [Ready](#ready) [Paused](#paused) [Deleting](#deleting)
[DependenciesReady](#dependenciesready) [IdentityAllowed](#identityallowed)
[CredentialsMirrored](#credentialsmirrored) [RunnerRBACReady](#runnerrbacready)
[ApplyJobSucceeded](#applyjobsucceeded) [StateReadable](#statereadable)
[RestoreJobSucceeded](#restorejobsucceeded) [OutputsValid](#outputsvalid)
[InfrastructureHealthy](#infrastructurehealthy)
[DriftJobSucceeded](#driftjobsucceeded) [DriftDetected](#driftdetected)
[DeletionBlocked](#deletionblocked) [EndpointAvailable](#endpointavailable)
[AutoscalingActive](#autoscalingactive) [CapacityResolved](#capacityresolved).

How to read the tables:

- **Status** is the condition's status: `True`, `False` or `Unknown`. For
  the three negative-polarity types (`Deleting`, `DriftDetected` and
  `DeletionBlocked`) `True` is the problem.
- **Meaning** is what the reason says about the object.
- **Likely cause** is what usually puts the object there. A transient wait is
  said to be transient.
- **What to do** is the next action. "Wait" means the controller will move on
  by itself, and a link leads to how long that takes.
- The generated [Conditions reference](../../reference/conditions.md) lists
  the same reasons with the code's own wording.

## Ready

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool,
TerraformClusterIdentity. Polarity: normal (`True` is healthy).

The only condition Cluster API reads. It summarizes other conditions; the
message names the inputs that decide it. A `TerraformClusterIdentity` sets it
from its credentials Secret instead.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `Ready` | Every input of Ready is `True`. | A healthy object. | Nothing. | [Ready summarization](../../reference/conditions.md#ready-summarization) |
| `True` | `SecretFound` | Identity only: the credentials Secret named by `spec.secretRef` exists. | A healthy identity. | Nothing. | [Identities](../../user-guide/identities.md) |
| `False` | `NotReady` | At least one input of Ready is `False`. The message names it. | Any failing input: dependencies, credentials, the apply, the state, outputs or health. | Read the message, then find the named condition below. Before the object is provisioned the inputs are `DependenciesReady`, `IdentityAllowed`, `CredentialsMirrored`, `RunnerRBACReady`, `ApplyJobSucceeded`, `StateReadable`, `OutputsValid`, `InfrastructureHealthy` and `Deleting`. | [Start here](README.md#start-here) |
| `False` | `SecretNotFound` | Identity only: the credentials Secret does not exist. | Never created, `spec.secretRef` names the wrong Secret or namespace, or the Secret was not copied after a `clusterctl move`. | Create or copy the Secret. | [Identity runbook](../runbooks/identity-and-credentials.md#secretnotfound) |
| `Unknown` | `ReadyUnknown` | No input is `False`, but at least one is `Unknown`. | The object is waiting: for its owner, the cluster infrastructure, bootstrap data, a first apply or a lease. | Find the `Unknown` input in the status. This is usually transient. | [Start here](README.md#start-here) |

## Paused

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
normal (`True` is healthy).

Whether reconciliation is paused. A paused object runs bookkeeping only and
starts no Job.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `Paused` | The object, or its Cluster, is paused. | `spec.paused` on the Cluster, or the `cluster.x-k8s.io/paused` annotation on the object. `clusterctl move` pauses on purpose. | Unpause when the pause is no longer wanted. A deletion under a paused object waits, and `Deleting` says so. | [Order and finalizers](../../concepts/deletion/order.md#pause-stops-a-deletion) |
| `False` | `NotPaused` | The object is not paused. | The normal state. | Nothing. | [Lifecycle](../../concepts/lifecycle.md#the-paused-branch) |

## Deleting

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
negative (`True` is the problem).

Whether the object is being deleted. A deleting object's message can say what
the destroy waits for.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `Deleting` | The object has a deletion timestamp. | A delete, usually through Cluster API. The message may read `The destroy Job waits for its credentials`, or `Deletion waits until the object is unpaused` when the object or its Cluster is paused: a paused object keeps its finalizer, starts no Job and never runs a destroy, so that `clusterctl move` can delete source objects safely. | Wait for the destroy. If the message says unpaused, unpause. Otherwise follow the flowchart. | [My object will not delete](../../concepts/deletion/troubleshooting.md) |
| `True` | `DeletionPolicyUnresolved` | A deleting machine or pool sets no `spec.deletionPolicy`, and the `TerraformCluster` it inherits one from cannot be found, so neither a destroy nor a Retain runs. | An ownerRef that does not resolve to a Machine of a Cluster with a `TerraformCluster`, or a `TerraformCluster` deleted before its machines. | Set `spec.deletionPolicy` (`Destroy` or `Retain`) on the object. | [Deletion policy](../../reference/resources/common-fields.md#deletion-policy) |
| `False` | `NotDeleting` | The object has no deletion timestamp. | The normal state. | Nothing. | [Deletion and Teardown](../../concepts/deletion/README.md) |

## DependenciesReady

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
normal (`True` is healthy).

The gates before a Job can render inputs: the owner, the Cluster, the cluster
infrastructure and exports, bootstrap data and variables. While a gate is closed
nothing is rendered or run. While the object is deleting, owner gates do not
apply: the destroy still runs.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `DependenciesReady` | Every gate is open. | The normal state. | Nothing. | [Lifecycle](../../concepts/lifecycle.md) |
| `False` | `ClusterNotTerraform` | The owning Cluster's `infrastructureRef` is not a `TerraformCluster`. | A machine or pool was created for a Cluster that uses another infrastructure provider. | Point the Cluster at a `TerraformCluster`, or move the machine to the right Cluster. | [Kinds](../../concepts/kinds.md) |
| `False` | `OwnerMismatch` | An owner reference of the expected kind resolves to an object that does not reference this one back. The reference is treated as forged or stale. | A wrong or missing `infrastructureRef`, a UID mismatch, or a `cluster-name` label that disagrees with the owner. | Fix the owner's `infrastructureRef` or the label. The message says which check failed. | [Kinds](../../concepts/kinds.md) |
| `False` | `OwnerNotFound` | The owner Machine, MachinePool or Cluster is gone. | The owner was deleted before this object, or a stale owner reference remains. | Delete this object if it is orphaned. A deleting object still destroys from its durable inputs. | [Deletion order](../../concepts/deletion/order.md) |
| `False` | `VariablesInvalid` | A `variablesFrom` source has a key that is not a Terraform identifier or is reserved, or a value that is not UTF-8 or valid JSON. The message names the key, never the value. | A malformed ConfigMap or Secret. | Correct the source. No Job starts until you do. | [Module variables](../../user-guide/variables.md#troubleshooting) |
| `False` | `VariablesSourceNotFound` | A required `variablesFrom` ConfigMap or Secret is missing or lacks the `captf.io/variables=true` label. | Not created, wrong name, a missing label, or not recreated after a `clusterctl move`. | Create the source and label it, or mark the reference optional. | [Module variables](../../user-guide/variables.md#troubleshooting) |
| `False` | `WaitingForOwnerMachine` | A fresh `TerraformMachine` has only a control-plane owner reference so far. | The control-plane provider created it before Cluster API set the Machine owner reference. | Wait. If it persists, check the Machine's `infrastructureRef` and the object's owner references. | [Control planes](../../module-author/control-planes/README.md) |
| `False` | `WaitingForOwnerMachinePool` | A `TerraformMachinePool` has owner references but none to its MachinePool yet. | Cluster API has not set the MachinePool owner reference. | Wait. If it persists, check the MachinePool's `infrastructureRef`. | [Machine pools](../../user-guide/machine-pools.md) |
| `Unknown` | `WaitingForOwner` | The owner is not set yet. For a machine or pool: the Cluster named by the `cluster.x-k8s.io/cluster-name` label is not found. | The object was just created, or the label is missing or wrong. | Wait. Check the label and the Cluster's name. | [Lifecycle](../../concepts/lifecycle.md) |
| `Unknown` | `WaitingForClusterInfrastructure` | The `TerraformCluster` is not provisioned yet. | The cluster's first apply has not finished or failed. | Read the `TerraformCluster`'s `ApplyJobSucceeded` and `Ready`. | [Failing Jobs](../runbooks/job-failures.md) |
| `Unknown` | `WaitingForClusterExports` | The cluster module's `exports` output is not readable. | The cluster's state is not readable, or its module declares no exports output. | Check the `TerraformCluster`'s `StateReadable` and `OutputsValid`. | [Unreadable state](../runbooks/state-unreadable.md) |
| `Unknown` | `WaitingForBootstrapData` | The Machine's or MachinePool's bootstrap data Secret is not set or not found. | The bootstrap provider has not produced it yet, or the control plane is waiting. | Check the bootstrap config object and the control plane. Nothing in CAPTF creates this Secret. | [Control planes](../../module-author/control-planes/README.md) |

## IdentityAllowed

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
normal (`True` is healthy).

Whether the object's `TerraformClusterIdentity` exists, allows the namespace and
has its credentials Secret. While it is not `True` no Job starts, except that a
deletion that needs no Job still finishes.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `IdentityAllowed` | The identity exists, allows the namespace and its Secret exists. | The normal state. | Nothing. | [Identities](../../user-guide/identities.md) |
| `False` | `IdentityNotFound` | No identity resolved. | No `identityRef` on the object or the cluster defaults, or the named identity does not exist. | Set `identityRef.name` to an existing identity, or create it. | [Identity runbook](../runbooks/identity-and-credentials.md#identitynotfound) |
| `False` | `NamespaceNotAllowed` | The identity's `allowedNamespaces` excludes this namespace. The mirror is revoked. | The namespace was never added, or was removed. | Add the namespace to the identity. | [Identity runbook](../runbooks/identity-and-credentials.md#namespacenotallowed) |
| `False` | `SecretNotFound` | The identity allows the namespace but its credentials Secret does not exist. | Not created, deleted, or not copied after a `clusterctl move`. | Create the Secret at the name and namespace in `spec.secretRef`. | [Identity runbook](../runbooks/identity-and-credentials.md#secretnotfound) |
| `Unknown` | `IdentityCheckFailed` | The check could not be completed. | A read of the identity, the namespace labels or the Secret failed for a reason other than not found, such as an API error. | Usually clears on its own. If it persists, read the manager's log for the error. | [Identity runbook](../runbooks/identity-and-credentials.md#identitycheckfailed) |

## CredentialsMirrored

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
normal (`True` is healthy).

Whether the identity's credentials were copied into the object's namespace as
the mirror Secret the Job mounts.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `Mirrored` | The mirror exists and is current. | The normal state. | Nothing. | [Identities](../../user-guide/identities.md#how-credentials-reach-a-job) |
| `False` | `MirrorFailed` | Creating or updating the mirror failed. | An API error, or a Secret with the mirror's name that is not a mirror of this identity. | Remove or rename the conflicting Secret. Another message names an API error: fix it and retry. | [Identity runbook](../runbooks/identity-and-credentials.md#mirrorfailed) |
| `Unknown` | `MirrorPending` | No mirror yet. | `IdentityAllowed` is not `True`, or this is before the first mirror. | Fix `IdentityAllowed`; this follows it. | [Identity runbook](../runbooks/identity-and-credentials.md#mirrorpending) |

## RunnerRBACReady

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
normal (`True` is healthy).

Whether the runner ServiceAccount exists and is bound to the runner role in the
namespace.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `RBACReady` | The runner ServiceAccount and RoleBinding are in place. | The normal state. | Nothing. | [RBAC](../rbac.md) |
| `False` | `RBACFailed` | Creating the ServiceAccount or the `captf-runner` RoleBinding failed. | An API error, or a RoleBinding named `captf-runner` that CAPTF does not own. | Remove or rename the conflicting RoleBinding. Otherwise fix the error in the message. | [Identity runbook](../runbooks/identity-and-credentials.md#rbacfailed) |
| `False` | `ServiceAccountNotOptedIn` | An override ServiceAccount lacks the `captf.io/runner=true` label. | `spec.jobs.serviceAccountName` names a ServiceAccount that does not exist or is not labeled. | Label it, create it, or drop the override. The controller retries every 30 seconds. | [Identity runbook](../runbooks/identity-and-credentials.md#serviceaccountnotoptedin) |

## ApplyJobSucceeded

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
normal (`True` is healthy).

The outcome of the newest apply, plan or destroy, and the reason an apply or
destroy waits or cannot start. A plan Job stands for the apply it plans. The
`Unknown` wait reasons here are also used by `DriftJobSucceeded` and
`RestoreJobSucceeded`.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `ApplySucceeded` | The newest apply succeeded. | The normal state. | Nothing. | [Jobs](../../concepts/jobs/README.md) |
| `True` | `DestroySucceeded` | The destroy succeeded; cleanup follows. | A deletion that completed its destroy. | Nothing. | [Cleanup](../../concepts/deletion/cleanup.md) |
| `False` | `ApplyFailed` | An apply Job failed. The message names the Job and the failed step. A message `Job <name>: disappeared while it ran and may have applied part of its change; an apply of the current inputs is due` means the Job was deleted while it ran (cluster or pool): an apply of the current inputs stays due and is guarded, with a suffix saying whether it is guarded. This message takes precedence over an older blocked or plan-changed apply, and stays until an apply started after the vanished Job (carrying `captf.io/after-interrupted-apply`) reports its own outcome. | A module error, a provider or cloud error, a lock timeout, or a runner error. For the `disappeared` message, a `kubectl delete job` of a running apply. | Read `status.lastRun` and the Job's pod logs. The controller retries with backoff. For `disappeared`, let the due apply run, or approve its plan if it waits; it clears when an apply started afterwards succeeds. | [Failing Jobs](../runbooks/job-failures.md) |
| `False` | `DestroyFailed` | A destroy Job failed, or a destroy cannot be rendered because the durable inputs Secret is missing. | A provider or cloud error; a dependency still in use; a deleted inputs Secret. | Fix the cause. It retries forever. If it cannot succeed, set `spec.deletionPolicy: Retain` or clean up by hand. | [Stuck destroy](../runbooks/stuck-destroy.md) |
| `False` | `JobDeadlineExceeded` | The Job hit `activeDeadlineSeconds`. It counts toward backoff. | A slow module or provider, or a hung call. | Raise `spec.jobs.activeDeadlineSeconds`, or find what hangs. | [Deadlines](../../concepts/jobs/deadlines.md) |
| `False` | `ImagePullFailed` | The pod stayed in `ErrImagePull` or `ImagePullBackOff` past the deadline. | A wrong image or tag, a missing pull secret, or a registry outage. | Fix the image reference or `imagePullSecrets`. | [Failing Jobs](../runbooks/job-failures.md#image-pull-failures) |
| `False` | `ImageInvalid` | The runner reported an image-layout error: no `/captf/module` or a non-executable command. | The image does not follow the image contract. | Rebuild the image to the contract; check it with `tfcapi-lint`. | [Image contract](../../module-author/image-contract.md) |
| `False` | `InputsTooLarge` | The rendered root module and variables exceed what a Secret can carry. No Job starts. | Large variables, bootstrap data or exports. | Shrink the inputs. | [Size limits](../runbooks/size-limits.md) |
| `False` | `JobPolicyInvalid` | The merged Job policy has a `lockTimeoutSeconds` that is not below `activeDeadlineSeconds`. No Job starts except a destroy. | A cluster default merged with a machine's policy, or one of the two left at its default. | Lower the lock timeout or raise the deadline. | [Deadlines](../../concepts/jobs/deadlines.md#the-merged-policy-check) |
| `False` | `DestructivePlanBlocked` | A `TerraformCluster` apply, or a `TerraformMachinePool` apply of a change of the cluster's exports, stopped before a plan that deletes or replaces resources. It counts toward no backoff. For a pool the change is held: the pool keeps applying the exports of its last successful apply, and its `Ready` is `False` until the change is approved. | The guard: no approved `TerraformPlan` names this plan (for a pool, its approval hash: the inputs hash without `bootstrap_data`). For a pool, the exports changed and the plan deletes or replaces something; after a failed guarded apply every pool apply is guarded; and a pool that applied before exports were recorded, without proof of them, has every apply guarded (the message says the exports of the last successful apply are unknown). | Review the plan in the message and run the command it gives to approve the named `TerraformPlan`, or change the inputs. A pool's plan is superseded if the exports return to the applied ones. | [Destructive-plan guard](../../concepts/approvals/destructive-guard.md#machine-pools) |
| `False` | `IdentityNotAllowed` | A pending destroy cannot start because the identity no longer allows the namespace, or is gone. | The identity's `allowedNamespaces` changed, or the identity was deleted. | Allow the namespace again, or set `spec.deletionPolicy: Retain`. | [Held deletions](../../concepts/deletion/held.md#retain) |
| `Unknown` | `NoApplyYet` | No apply has completed. | A new object, or one waiting on a gate or credentials. | Check `DependenciesReady`, `IdentityAllowed` and the Jobs. | [Jobs](../../concepts/jobs/troubleshooting.md) |
| `Unknown` | `PlanAwaitingApproval` | Under `applyPolicy: Manual`, a `Manual` `TerraformPlan` waits for approval. | A change of inputs under Manual policy. | Review the plan and approve the `TerraformPlan` the message names. | [Manual plan approval](../../concepts/approvals/manual-approval.md) |
| `Unknown` | `PlanChanged` | An approved apply planned other changes and stopped before applying them. | The inputs or the infrastructure changed after approval. | Review the new plan the message names and approve it. | [Manual plan approval](../../concepts/approvals/manual-approval.md) |
| `Unknown` | `WaitingForClusterOperation` | A machine's or pool's apply, destroy or restore waits for its `TerraformCluster`'s. | The cluster is applying or destroying. No Job exists yet and nothing counts as a failure. | Wait. The message names the cluster's Job. | [Leases](../../concepts/jobs/leases.md) |
| `Unknown` | `WaitingForMachineOperations` | A `TerraformCluster`'s apply, destroy or restore waits for its machines' and pools' operations in flight. | Machine or pool Jobs are running. New ones wait behind the cluster. | Wait. The message names up to five Jobs. | [Leases](../../concepts/jobs/leases.md) |
| `Unknown` | `WaitingForRunLease` | Another live Job, perhaps another manager's, holds the run lease or the Cluster's write lease. | A Job of the same object or a second cluster operation is running. | Wait. Never delete a Lease by hand. | [Slow Jobs](../runbooks/slow-jobs.md#waiting-for-a-lease) |

## StateReadable

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
normal (`True` is healthy).

Whether the object's Terraform state can be read. While it is `False`, no Job
runs, and a deleting object's deletion is held, except for `StateLocked`.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `StateRead` | The state was read. | The normal state. | Nothing. | [Unreadable state](../runbooks/state-unreadable.md#stateread) |
| `False` | `StateLost` | The state Secret of an object that applied before is missing, or an immutable object's state carries no inputs hash. | A state Secret deleted by hand or with its namespace. For a provisioned machine: a state without an inputs hash. | Restore a backup with `captf.io/restore-state`. A deleting object can be released with `spec.deletionPolicy: Retain` instead. | [Unreadable state](../runbooks/state-unreadable.md#statelost) |
| `False` | `RetainedStateFound` | A new object found Secrets retained from an earlier object of the same kind, namespace and name. It never adopts them silently: no Job runs and nothing is owned or backed up. | A same-name object was deleted with `spec.deletionPolicy: Retain`, and this one was created in its place. | Set `spec.adoptRetainedState: true` to adopt the state, or delete the Secrets labeled `captf.io/retained-from-uid` to discard it. | [A recreated object holds](../../concepts/deletion/retain.md#a-recreated-object-holds) |
| `False` | `StateCorrupt` | The state cannot be decoded, exceeds the reader's caps, or has an unsupported version. | A hand edit, a partial write, or a state too large. | Restore a backup taken before the corruption. | [Unreadable state](../runbooks/state-unreadable.md#statecorrupt) |
| `False` | `StateEncrypted` | The state carries OpenTofu's client-side encryption. CAPTF cannot read it. | State encryption is enabled in the module. | Disable it and push a decrypted state; no backup exists. | [Unreadable state](../runbooks/state-unreadable.md#stateencrypted) |
| `False` | `StateInconsistent` | The state chunks do not form one complete state. | A missing or duplicated chunk, or a stray Secret in the set. | Repair the set or restore a backup. | [Unreadable state](../runbooks/state-unreadable.md#stateinconsistent) |
| `False` | `StateLocked` | Something other than the object's own runner holds the state lock. Every Job waits `lockTimeoutSeconds` for it and fails. | A workstation running Terraform against the same backend. | Release it with `force-unlock` once the holder is gone. | [Stale lock](../runbooks/stale-lock.md) |
| `Unknown` | `StateNotFound` | No state exists yet. | The object has never applied. | Nothing; the first apply creates it. | [Unreadable state](../runbooks/state-unreadable.md#statenotfound) |

## RestoreJobSucceeded

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
normal (`True` is healthy).

The outcome of a state restore requested with `captf.io/restore-state`. Never an
input of Ready.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `StateRestored` | The restore Job pushed the backup into the backend. | A completed restore. | Nothing; the annotation is removed. | [State restore](../runbooks/state-restore.md) |
| `False` | `RestoreBackupNotFound` | The annotation names no complete backup, or is not a serial. No Job starts. | A typo, a pruned backup or an incomplete one. | Pick a serial from `status.stateBackups`. | [State restore](../runbooks/state-restore.md#list-the-backups) |
| `False` | `RestoreFailed` | The restore Job failed. It is not retried for the same serial. | A lock, a bad backup or a runner error. | Read the Job's logs, remove the annotation, wait for `status.lastRestoredSerial` to clear, and set it again. | [Other manual actions](../../concepts/approvals/other-manual-actions.md#restore-a-state) |
| `Unknown` | `WaitingForRunLease` | Another live Job holds the run lease. | A Job of the object is running. | Wait. | [Leases](../../concepts/jobs/leases.md) |
| `Unknown` | `WaitingForClusterOperation` | A machine's or pool's restore waits for its cluster's operation. | The cluster is applying, destroying or restoring. | Wait. | [Leases](../../concepts/jobs/leases.md) |
| `Unknown` | `WaitingForMachineOperations` | A cluster's restore waits for its machines' and pools' operations. | Machine or pool Jobs are in flight. | Wait. | [Leases](../../concepts/jobs/leases.md) |

## OutputsValid

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
normal (`True` is healthy).

Whether the module's outputs, read from state, match the role's contract.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `OutputsValid` | The outputs are valid. | The normal state. | Nothing. | [Module contract](../../module-author/contract/README.md) |
| `True` | `InstancesTruncated` | A pool's `instances` output had more than 1000 entries; `status.instances` keeps the first 1000. The pool still provisions. | A very large pool. | Usually nothing. Count against the contract's cap. | [MachinePool role](../../module-author/contract/v1alpha1/machinepool.md) |
| `False` | `OutputsMissing` | A required output is not declared. | The module lacks an output its role requires. | Add the output. Check the module with `tfcapi-lint`. | [tfcapi-lint](../../module-author/tfcapi-lint.md) |
| `False` | `OutputsInvalid` | An output breaks the contract or a Cluster API marker. | A wrong type, shape or value. The message names the output. | Fix the module's output. | [Module contract](../../module-author/contract/README.md) |
| `False` | `FailureDomainMismatch` | The Machine requested a failure domain (`spec.failureDomain`) and the module's `failure_domain` output is null or differs from it. With no request, any placement is fine. | The module placed the instance elsewhere, or does not report `failure_domain`. | Honor the requested failure domain in the module. | [Machine role](../../module-author/contract/v1alpha1/machine.md) |
| `False` | `ProviderIDChanged` | `provider_id` changed after it was first written. It is immutable. | The module replaced the instance outside Cluster API's replacement, or the output is unstable. | Do not edit `spec.providerID`. Delete the Machine to replace the instance. | [Machine role](../../module-author/contract/v1alpha1/machine.md) |
| `Unknown` | `OutputsPending` | Required outputs are null, or there is no state yet. | The first apply has not finished. | Wait for the apply. | [Jobs](../../concepts/jobs/troubleshooting.md) |

With several problems at once, the reason is the first that applies:
`OutputsMissing`, `OutputsInvalid`, `FailureDomainMismatch`,
`ProviderIDChanged`, `OutputsPending`, `InstancesTruncated`, `OutputsValid`.
The message lists every problem, separated by `; `, so read it in full.

## InfrastructureHealthy

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
normal (`True` is healthy).

The health the module reports, read from state at each refresh. After
provisioning it is the input that moves Ready.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `Healthy` | The instance is running and healthy. | The normal state. | Nothing. | [Drift and health](../../concepts/drift-and-health.md#from-module-health-to-infrastructurehealthy) |
| `False` | `Provisioning` | The first apply is running. | The first apply started and has not finished. | Wait for the Job. | [Jobs](../../concepts/jobs/README.md) |
| `False` | `InstancePending` | The module reports `pending`. | The instance is still starting. | Wait; refresh runs on a doubling schedule up to five minutes. | [Schedules](../../concepts/jobs/schedules.md) |
| `False` | `InstanceUnhealthy` | The module reports running but not healthy. | A failing health check on the instance. | Look at the instance. Remediation can replace it. | [Machine remediation](../../user-guide/remediation.md) |
| `False` | `InstanceDegraded` | The module reports `degraded`. | A partial failure of the instance. | As above. | [Machine remediation](../../user-guide/remediation.md) |
| `False` | `InstanceStopped` | The module reports `stopped`. | The instance was stopped outside CAPTF. | Start it, or let remediation replace it. | [Machine remediation](../../user-guide/remediation.md) |
| `False` | `InstanceTerminated` | The module reports `terminated`, or the instance vanished. | The instance was deleted outside CAPTF. | Let remediation replace it, or delete the Machine. | [Machine remediation](../../user-guide/remediation.md#terminated-instances) |
| `Unknown` | `WaitingForProvisioning` | Before the first apply. | A new object. | Nothing; see `ApplyJobSucceeded`. | [Jobs](../../concepts/jobs/troubleshooting.md) |
| `Unknown` | `HealthUnknown` | The module reports `unknown`, or no health at all. | The module has no health signal yet. | Check the module's `health` output. | [Drift and health](../../concepts/drift-and-health.md) |
| `Unknown` | `ProviderIDMissing` | `provider_id` turned null after provisioning. It is reported terminated only if the next sample is null too. | A transient read, or the instance vanished. | Wait one sample. | [Drift and health](../../concepts/drift-and-health.md) |

## DriftJobSucceeded

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
normal (`True` is healthy).

The outcome of the newest refresh or drift Job. Never an input of Ready.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `DriftChecked` | The newest refresh or drift Job succeeded. | The normal state. | Nothing. | [Drift](../../user-guide/drift.md) |
| `False` | `DriftJobFailed` | A refresh or drift Job failed. | A provider error, a lock timeout or a module error. | Read the Job's logs. The check retries with backoff. | [Failing Jobs](../runbooks/job-failures.md) |
| `False` | `DriftJobDeadlineExceeded` | The Job hit `activeDeadlineSeconds`. | A slow provider read. | Raise the deadline. | [Deadlines](../../concepts/jobs/deadlines.md) |
| `Unknown` | `DriftNotChecked` | No drift check has run. | A new object, or drift is disabled. | Nothing, or enable drift checks. | [Drift](../../user-guide/drift.md) |
| `Unknown` | `DriftJobRunning` | A drift Job runs. | A drift check is in progress. | Wait. | [Drift and health](../../concepts/drift-and-health.md) |
| `Unknown` | `WaitingForRunLease` | A refresh or drift waits for the run lease. | Another live Job of the object holds it. | Wait. | [Leases](../../concepts/jobs/leases.md) |

## DriftDetected

Carried by: TerraformCluster, TerraformMachine, TerraformMachinePool. Polarity:
negative (`True` is the problem).

Whether the last drift check found differences. `True` is the problem, though it
never feeds Ready.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `DriftReported` | Drift was found and the action is `Report`. | Infrastructure changed outside CAPTF. | Decide whether to accept it, or set the action to `Remediate`. | [Drift](../../user-guide/drift.md#remediate-drift) |
| `True` | `DriftPending` | Drift was found with action `Remediate`, and the remediation apply has not succeeded yet. The message names a failed, blocked or changed remediation Job. | The apply waits for backoff, a lease or an approval, or failed. | Wait, or read `ApplyJobSucceeded`. After the failed limit it waits for the next drift check. | [Retries](../../concepts/jobs/retries.md#the-remediation-cap) |
| `True` | `DriftRemediating` | A remediation apply runs. | Action `Remediate` and drift found. | Wait. | [Drift](../../user-guide/drift.md#remediate-drift) |
| `False` | `NoDrift` | The last check found none. | The normal state. | Nothing. | [Drift](../../user-guide/drift.md) |
| `Unknown` | `DriftNotChecked` | No check has run. | A new object, or drift is disabled. | Nothing. | [Drift](../../user-guide/drift.md) |

## DeletionBlocked

Carried by: TerraformCluster. Polarity: negative (`True` is the problem).

Whether a deleting `TerraformCluster` waits for dependents. Never an input of
Ready.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `DependentsExist` | Machines or pools of the cluster still exist. No destroy runs. | Cluster API has not finished deleting them, or one is stuck. | List them with `-l cluster.x-k8s.io/cluster-name=<name>` and work on the stuck one. | [Order and finalizers](../../concepts/deletion/order.md#the-cluster-waits-for-its-machines) |
| `False` | `NotBlocked` | Nothing blocks the deletion. | The normal state. | Nothing. | [Deletion and Teardown](../../concepts/deletion/README.md) |

## EndpointAvailable

Carried by: TerraformCluster. Polarity: normal (`True` is healthy).

Whether the cluster has a control-plane endpoint. Never an input of Ready.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `EndpointAvailable` | A valid endpoint exists in the module output, the spec or the Cluster. | The normal state. | Nothing. | [Cluster role](../../module-author/contract/v1alpha1/cluster.md) |
| `False` | `WaitingForEndpoint` | The cluster is provisioned and neither the module's `control_plane_endpoint` output nor `Cluster.spec.controlPlaneEndpoint` is set. | The module does not output an endpoint and none was supplied. | Output one from the module or set it on the Cluster. | [Cluster role](../../module-author/contract/v1alpha1/cluster.md) |

## AutoscalingActive

Carried by: TerraformMachinePool. Polarity: normal (`True` is healthy).

Whether a pool's replicas follow the autoscaler. Informational; never an input
of Ready.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `ReplicasManagedByModule` | Both autoscaler annotations are valid and the controller writes the observed replicas back to the MachinePool. | An autoscaled pool. | Nothing. | [Machine pools](../../user-guide/machine-pools.md#choose-fixed-replicas-or-autoscaling) |
| `False` | `AutoscalingDisabled` | Neither annotation is set; `spec.replicas` is the only source of capacity. | A fixed-replica pool. | Nothing, unless you want autoscaling. | [Machine pools](../../user-guide/machine-pools.md#choose-fixed-replicas-or-autoscaling) |
| `False` | `AutoscalingAnnotationsInvalid` | An annotation is present but the pair is incomplete, unparsable or has min above max. The pool applies without autoscaling. | A typo or one annotation missing. | Fix the annotations; the message names the problem. | [Machine pools](../../user-guide/machine-pools.md#choose-fixed-replicas-or-autoscaling) |
| `False` | `ReplicasManagedExternally` | The annotations are valid but another controller owns `spec.replicas` through `cluster.x-k8s.io/replicas-managed-by`. Observed replicas are not written back. | Another autoscaler manages the MachinePool. | Choose one owner. A `Warning` event is emitted on the transition. | [Machine pools](../../user-guide/machine-pools.md#choose-fixed-replicas-or-autoscaling) |

## CapacityResolved

Carried by: TerraformMachineTemplate. Polarity: normal (`True` is healthy).

Whether a template's capacity and node info were read from its image's labels.

| Status | Reason | Meaning | Likely cause | What to do | See |
| --- | --- | --- | --- | --- | --- |
| `True` | `CapacityResolved` | Both labels parsed. | The normal state. | Nothing. | [Templates](../../user-guide/clusterclass.md) |
| `True` | `CapacityNotDeclared` | The image carries neither label. | Not every image declares capacity. | Nothing, unless a ClusterClass autoscaler needs it. | [Templates](../../user-guide/clusterclass.md) |
| `False` | `ImageInspectFailed` | The registry fetch or authentication failed. | A wrong reference, a registry outage or missing credentials. | Fix the reference or credentials. A `Warning` event is emitted. | [Templates](../../user-guide/clusterclass.md) |
| `False` | `CapacityLabelInvalid` | A label is present but invalid. | A malformed capacity or node-info label on the image. | Fix the label in the image. | [Image contract](../../module-author/image-contract.md) |

!!! related "See also"

    - [Events](events.md).
    - [Runbooks](../runbooks/README.md).
    - [Conditions reference](../../reference/conditions.md).
