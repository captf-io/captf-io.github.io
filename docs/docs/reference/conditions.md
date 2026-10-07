---
title: "CAPTF Status Conditions Reference"
description: "Every status condition CAPTF sets, which kinds carry it, how to read its polarity, and what each reason means and what to do about it."
hide:
  - toc
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/list-checks
subtitle: "Every status condition"
---

# Conditions

Conditions are the typed status entries in `status.conditions` of a CAPTF
object. Each has a `type`, a `status` (`True`, `False` or `Unknown`), a
machine-readable `reason` and a human-readable `message`. The type says what
is being tracked, the status says how it stands, and the reason says why. This
page lists every type and every reason CAPTF sets. To go from a stuck object to
the right fix, start with [Troubleshooting conditions][troubleshooting], which
adds the likely cause of each reason.

Five kinds carry conditions: `TerraformCluster`, `TerraformMachine`,
`TerraformMachinePool`, `TerraformMachineTemplate` and
`TerraformClusterIdentity`. Below, "all three" means the first three. The
per-kind pages list which types each kind sets:
[`TerraformCluster`](resources/terraformcluster.md#conditions),
[`TerraformMachine`](resources/terraformmachine.md#conditions),
[`TerraformMachinePool`](resources/terraformmachinepool.md#conditions) and
[`TerraformClusterIdentity`](resources/terraformclusteridentity.md#conditions).

## Read conditions

`Ready` is the only condition Cluster API reads. Cluster API mirrors it into
`InfrastructureReady` on the owning `Cluster`, `Machine` or `MachinePool`.
Every other type is informational: it explains why `Ready` is what it is, and
nothing outside CAPTF acts on it.

List every condition of an object with `jsonpath`:

```sh
kubectl get terraformcluster -n <namespace> <name> \
  -o jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\t"}{.message}{"\n"}{end}'
```

`kubectl describe` prints the same list under `Conditions:`, with the events
below it. To see the whole Cluster API tree, with each object's `Ready` and the
reason it is not ready, run `clusterctl describe cluster <name>`. See
[Observability](../operator-guide/observability.md) for how conditions surface
in events and metrics.

Most types follow normal polarity: `True` is healthy and `False` is a problem.
Three types have negative polarity, where `True` is the problem or the
unwanted state: `Deleting`, `DriftDetected` and `DeletionBlocked`. `Paused` is
a state rather than a health reading: `True` means paused. A type that has no
reason for `Unknown` is never `Unknown`. A type that is absent has not been set
yet. In the `Ready` summary an absent input counts as `Unknown`, except
`Deleting`.

!!! note "Waiting is `Unknown`, not `False`"

    Waiting for a lease, for another object or for an approval sets `Unknown`.
    A wait never turns `Ready` `False`, and it never counts toward retry
    backoff.

## Summary

| Type | Carried by | Polarity | Meaning |
| --- | --- | --- | --- |
| [`Ready`](#ready) | All three, and `TerraformClusterIdentity` | Normal | Summary of the object's other conditions. The one Cluster API reads. |
| [`DependenciesReady`](#dependenciesready) | All three | Normal | The owner, cluster, exports, bootstrap data and variable sources the object waits for exist. |
| [`IdentityAllowed`](#identityallowed) | All three | Normal | The identity exists, allows the namespace and has its Secret. |
| [`CredentialsMirrored`](#credentialsmirrored) | All three | Normal | The identity's credentials are copied into the namespace for the Jobs. |
| [`RunnerRBACReady`](#runnerrbacready) | All three | Normal | The runner ServiceAccount and its RoleBinding exist. |
| [`ApplyJobSucceeded`](#applyjobsucceeded) | All three | Normal | Outcome of the newest apply or destroy, and why one waits or cannot start. |
| [`StateReadable`](#statereadable) | All three | Normal | The Terraform state can be read. |
| [`RestoreJobSucceeded`](#restorejobsucceeded) | All three | Normal | Outcome of a state restore you requested. |
| [`OutputsValid`](#outputsvalid) | All three | Normal | The module's outputs satisfy the contract. |
| [`InfrastructureHealthy`](#infrastructurehealthy) | All three | Normal | The health the module reports. |
| [`InputsApplied`](#inputsapplied) | All three | Normal | The current inputs are what the infrastructure was last applied with. Never feeds `Ready`. |
| [`DriftJobSucceeded`](#driftjobsucceeded) | All three | Normal | Outcome of the newest refresh or drift Job. |
| [`DriftDetected`](#driftdetected) | All three | Negative | The last drift check found differences. |
| [`DeletionBlocked`](#deletionblocked) | `TerraformCluster` | Negative | A deleting cluster waits for its machines and pools. |
| [`EndpointAvailable`](#endpointavailable) | `TerraformCluster` | Normal | A valid control-plane endpoint is known. |
| [`AutoscalingActive`](#autoscalingactive) | `TerraformMachinePool` | Normal | The module owns the pool's desired count. |
| [`CapacityResolved`](#capacityresolved) | `TerraformMachineTemplate` | Normal | Capacity and node info were read from the image's labels. |
| [`VariablesValid`](#variablesvalid) | `TerraformMachineTemplate` | Normal | The template's variables fit the variables schema its image publishes. |
| [`Paused`](#paused) | All three | State | The object or its Cluster is paused. |
| [`Deleting`](#deleting) | All three | Negative | The object is being deleted. |
| [`TerraformPlan` conditions](#terraformplan) | `TerraformPlan` | Normal | `Ready` and `Approved`: where a plan waiting for an approval is. |

[troubleshooting]: ../operator-guide/troubleshooting/conditions.md

## Ready

Carried by `TerraformCluster`, `TerraformMachine`, `TerraformMachinePool` and
`TerraformClusterIdentity`. Polarity: normal.

`Ready` summarizes other conditions; see [Ready
summarization](#ready-summarization) for which. `True` means every input is
`True`. `False` means at least one input is `False`, and `Unknown` means none is
`False` but at least one is `Unknown`. The message names the inputs that decide
it, and the input's own reason, such as `Provisioning`, appears there, not in
`Ready`'s reason. A `TerraformClusterIdentity` does not summarize: it sets
`Ready` from whether its credentials Secret exists.

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `Ready` | Every input is healthy. Nothing to do. |
| `True` | `SecretFound` | Identity only: the Secret named by `spec.secretRef` exists and holds every key in `spec.requiredKeys`. |
| `False` | `NotReady` | An input is `False`. Read the message, then the named condition below. |
| `False` | `SecretNotFound` | Identity only: the Secret does not exist, and objects that use the identity start no Job until it does. See the [identity runbook](../operator-guide/runbooks/identity-and-credentials.md#secretnotfound). |
| `False` | `CredentialsIncomplete` | Identity only: the Secret lacks a key listed in `spec.requiredKeys`, and objects that use the identity start no Job until it holds them. See the [identity runbook](../operator-guide/runbooks/identity-and-credentials.md#credentialsincomplete). |
| `Unknown` | `ReadyUnknown` | No input is `False`, but one is `Unknown`: the object waits for its owner, a first apply, a lease or an approval. Usually transient. |

## DependenciesReady

Carried by all three. Polarity: normal.

The gates that must open before CAPTF renders inputs or starts a Job: the
owner, the `Cluster`, the cluster's infrastructure and exports, bootstrap data
and variable sources. While a gate is closed, nothing is rendered or run. A
deleting object skips the owner gates, so its destroy still runs.

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `DependenciesReady` | Every gate is open. |
| `False` | `ClusterNotTerraform` | The owning `Cluster`'s `infrastructureRef` is not a `TerraformCluster`. Nothing is rendered or run. Point the `Cluster` at a `TerraformCluster`, or move the object to the right one. |
| `False` | `OwnerMismatch` | An `ownerReference` of the expected kind resolves to an object that does not reference this one back: a wrong or missing `infrastructureRef`, a UID mismatch, or a `cluster.x-k8s.io/cluster-name` label that disagrees with the owner. CAPTF treats the reference as forged or stale, so the object has no valid owner, no Job runs and nothing is written to the named owner or its `Cluster`. The message says which check failed. |
| `False` | `OwnerNotFound` | The owner object is gone. Delete this object if it is orphaned. See [deletion order](../concepts/deletion/order.md). |
| `False` | `VariablesInvalid` | A `variablesFrom` source has a key that is not a Terraform identifier or is reserved, or a value that is not UTF-8 or, for format `json`, not valid JSON; or the merged variables do not fit the variables schema the image publishes (`io.captf.variables-schema`): an unknown key, a required variable nothing sets, or a value of the wrong type. The message names the key, never the value. No Job starts until you correct the variables or the source. See [module variables](../user-guide/variables.md#troubleshooting). |
| `False` | `VariablesSourceNotFound` | A ConfigMap or Secret named in `spec.variablesFrom`, not marked optional, is missing or lacks the `captf.io/variables=true` label. No Job starts. See [module variables](../user-guide/variables.md#troubleshooting). |
| `False` | `WaitingForOwnerMachine` | A fresh `TerraformMachine` has only a non-controller control-plane `ownerReference` and no `Machine` one yet. Wait for Cluster API to set it. |
| `False` | `WaitingForOwnerMachinePool` | A `TerraformMachinePool` has `ownerReferences` but none to a `MachinePool` yet. Wait for Cluster API to set it. |
| `Unknown` | `WaitingForOwner` | The owner is not set yet. Wait, and check the object's `cluster.x-k8s.io/cluster-name` label. |
| `Unknown` | `WaitingForClusterInfrastructure` | The `TerraformCluster` is not provisioned yet. Read its `ApplyJobSucceeded` and `Ready`. |
| `Unknown` | `WaitingForClusterExports` | The cluster module's `exports` output is not readable. Check the `TerraformCluster`'s [`StateReadable`](#statereadable) and [`OutputsValid`](#outputsvalid). |
| `Unknown` | `WaitingForBootstrapData` | The `Machine`'s or `MachinePool`'s bootstrap data Secret is not set or not found. The bootstrap provider creates it, not CAPTF. See [control planes](../module-author/control-planes/README.md). |

## IdentityAllowed

Carried by all three. Polarity: normal.

Whether the resolved `TerraformClusterIdentity` exists, allows this namespace
and has its credentials Secret. While it is not `True`, no Job starts, except
that a deletion that needs no Job still finishes. See
[Identities](../user-guide/identities.md) and the
[identity runbook](../operator-guide/runbooks/identity-and-credentials.md).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `IdentityAllowed` | The identity exists, allows the namespace and its Secret exists with every required key. |
| `True` | `LocalSecret` | `identityRef.kind` is `Secret` and that Secret exists in the object's namespace. It is used as it is: no mirror and no `allowedNamespaces` check. |
| `False` | `IdentityNotFound` | No identity resolved: none is set on the object or the cluster defaults, or the named one does not exist. [Fix](../operator-guide/runbooks/identity-and-credentials.md#identitynotfound). |
| `False` | `NamespaceNotAllowed` | The identity's `allowedNamespaces` excludes this namespace. CAPTF revokes the mirror. [Fix](../operator-guide/runbooks/identity-and-credentials.md#namespacenotallowed). |
| `False` | `SecretNotFound` | The identity allows the namespace but its credentials Secret does not exist. [Fix](../operator-guide/runbooks/identity-and-credentials.md#secretnotfound). With `kind: Secret`, the Secret does not exist in the object's namespace. |
| `False` | `CredentialsIncomplete` | The identity's Secret lacks a key in its `spec.requiredKeys`. The message names the keys. [Fix](../operator-guide/runbooks/identity-and-credentials.md#credentialsincomplete). |
| `Unknown` | `IdentityCheckFailed` | CAPTF could not finish the check, for example because an API read failed. It usually clears by itself. [Fix](../operator-guide/runbooks/identity-and-credentials.md#identitycheckfailed). |

## CredentialsMirrored

Carried by all three. Polarity: normal.

Whether the identity's credentials are copied into the object's namespace as
the mirror Secret that its Jobs mount.

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `Mirrored` | The mirror exists and is current. |
| `False` | `MirrorFailed` | Creating or updating the mirror failed, for example because a Secret with the mirror's name belongs to something else. [Fix](../operator-guide/runbooks/identity-and-credentials.md#mirrorfailed). |
| `Unknown` | `MirrorPending` | No mirror exists yet, either before the first mirror or because [`IdentityAllowed`](#identityallowed) is not `True`. Fix that first. [Details](../operator-guide/runbooks/identity-and-credentials.md#mirrorpending). |

## RunnerRBACReady

Carried by all three. Polarity: normal. Never `Unknown`; until the controller
first reaches it, the condition is absent and counts as `Unknown` in `Ready`.

Whether the runner ServiceAccount exists and is bound to the runner role in the
object's namespace. See [RBAC](../operator-guide/rbac.md).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `RBACReady` | The ServiceAccount and RoleBinding are in place. |
| `False` | `RBACFailed` | Creating the ServiceAccount or the `captf-runner` RoleBinding failed, for example because a RoleBinding with that name is not CAPTF's. [Fix](../operator-guide/runbooks/identity-and-credentials.md#rbacfailed). |
| `False` | `ServiceAccountNotOptedIn` | An override ServiceAccount lacks the `captf.io/runner=true` label. Label it, create it or drop the override; the controller retries every 30 seconds. [Fix](../operator-guide/runbooks/identity-and-credentials.md#serviceaccountnotoptedin). |

## ApplyJobSucceeded

Carried by all three. Polarity: normal.

The outcome of the newest apply, plan or destroy Job, and the reason one waits
or cannot start. A plan Job stands for the apply it plans. After one has
completed the status is not `Unknown`, except while the next operation waits
for a lease or an approval. A running apply keeps the last result. The three
lease reasons are shared with [`DriftJobSucceeded`](#driftjobsucceeded) and
[`RestoreJobSucceeded`](#restorejobsucceeded). To diagnose a failure, read
`status.lastRun` and the Job's pod logs; see [Failing
Jobs](../operator-guide/runbooks/job-failures.md).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `ApplySucceeded` | The newest apply succeeded. |
| `True` | `DestroySucceeded` | The destroy succeeded and cleanup follows. |
| `False` | `ApplyFailed` | An apply Job failed, or disappeared while it ran because it was deleted before it finished. The message names the Job and the failed step. The controller retries with backoff. After a Job vanished, an apply of the current inputs stays due until one succeeds; this message outranks an older blocked or plan-changed apply. See [retries](../concepts/jobs/retries.md#an-apply-job-deleted-while-it-ran). |
| `False` | `DestroyFailed` | A destroy Job failed, or a destroy cannot be rendered because the durable inputs Secret is missing. It retries until it succeeds. If it cannot, see [stuck destroy](../operator-guide/runbooks/stuck-destroy.md); [`deletionPolicy: Retain`](../concepts/deletion/retain.md) ends the deletion without a destroy. |
| `False` | `DestructivePlanBlocked` | An apply stopped before a plan that deletes or replaces resources, and no approved `TerraformPlan` names exactly this plan. The message says what the apply would delete or replace, and names the `TerraformPlan` to approve with the command. After `clusterctl move`, a wait with no blocked Job has a message that starts `TerraformPlan <name> plans inputs hash ...` and emits no event. If the runner reported no plan, no `TerraformPlan` exists: the message says "The runner reported no plan to approve, so the apply plans again later", and the apply runs again after `RetryMax` (10 minutes). On a `TerraformCluster`, which includes a drift remediation, no apply of the inputs runs until the plan is approved or the inputs change. On a `TerraformMachinePool`, it is an apply of a change of the cluster's exports that stopped, and the plan (reason `ExportsChange`) binds the pool's approval hash (the inputs hash without `bootstrap_data`). The reason stays while the change waits. The pool keeps applying everything else with the exports of its last successful apply, and the condition reports that apply, `True`, again once the change is approved, or the exports change or return to the applied ones. A pool that cannot fall back to those exports waits for approval as a cluster does, and the message says why. See the [destructive-plan guard](../concepts/approvals/destructive-guard.md#machine-pools). |
| `False` | `IdentityNotAllowed` | No Job could be created because the identity does not allow the namespace or is gone. Allow the namespace again, or set [`deletionPolicy: Retain`](../concepts/deletion/retain.md) on a deleting object. |
| `False` | `ImageInvalid` | The runner reported an image-layout error: no `/captf/module` or a non-executable command. Rebuild the image to the [image contract](../module-author/image-contract.md). |
| `False` | `ImagePullFailed` | The pod stayed in `ErrImagePull` or `ImagePullBackOff` past `activeDeadlineSeconds`. See [image pull failures](../operator-guide/runbooks/job-failures.md#image-pull-failures). |
| `False` | `InputsTooLarge` | The rendered root module and variables exceed what a Secret can carry, so no Job starts. See [size limits](../operator-guide/runbooks/size-limits.md). |
| `False` | `JobDeadlineExceeded` | The Job hit `activeDeadlineSeconds`. See [deadlines](../concepts/jobs/deadlines.md). |
| `False` | `JobPolicyInvalid` | The effective job policy, the object's own merged over the cluster defaults and the built-in defaults, gives a `lockTimeoutSeconds` that is not below `activeDeadlineSeconds`, so no Job starts. See [the merged-policy check](../concepts/jobs/deadlines.md#the-merged-policy-check). |
| `Unknown` | `NoApplyYet` | No apply has completed yet. Check [`DependenciesReady`](#dependenciesready), [`IdentityAllowed`](#identityallowed) and the Jobs. |
| `Unknown` | `PlanAwaitingApproval` | A `TerraformCluster` with `applyPolicy: Manual` waits for approval of a `Manual` [`TerraformPlan`](resources/terraformplan.md). The message starts `TerraformPlan <name> plans inputs hash <hash>: <counts>. Nothing is applied until it is approved:` and ends with the approve command. See [manual approval](../concepts/approvals/manual-approval.md). |
| `Unknown` | `PlanChanged` | An approved apply planned other changes than the approved plan and stopped before applying them. The message reads `Job <apply>: the plan changed since TerraformPlan <old> was approved, so nothing was applied. TerraformPlan <new> plans ...`, with the approve command, and the new `TerraformPlan` waits for approval. See [manual approval](../concepts/approvals/manual-approval.md). |
| `Unknown` | `WaitingForClusterOperation` | A machine's or pool's apply or destroy waits for its `TerraformCluster`'s to finish. |
| `Unknown` | `WaitingForMachineOperations` | A `TerraformCluster`'s apply or destroy waits for the applies and destroys of its machines and pools in flight. New ones wait behind it. |
| `Unknown` | `WaitingForRunLease` | Another live Job, such as one another manager instance started, holds the object's run lease. No Job starts until it finishes. Never delete a Lease by hand. See [leases](../operator-guide/runbooks/slow-jobs.md#waiting-for-a-lease). |
| `Unknown` | `WaitingForJobSlot` | The manager's active Jobs reached `--max-active-jobs`, or the cluster's reached `spec.maxActiveJobs` (`--cluster-max-active-jobs`). No Job starts until one finishes; the check repeats about every 15 seconds. See [Job limits](../concepts/jobs/README.md#job-limits). |

## StateReadable

Carried by all three. Polarity: normal.

Whether CAPTF can read the object's Terraform state from its backend Secrets.
While it is `False`, no Job runs, and a deleting object's deletion is held,
except for `StateLocked` and `RetainedStateFound`. See [unreadable
state](../operator-guide/runbooks/state-unreadable.md) and
[State](../concepts/state.md).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `StateRead` | The state was read. |
| `False` | `StateCorrupt` | The state cannot be decoded. Restore a backup taken before the damage. [Fix](../operator-guide/runbooks/state-unreadable.md#statecorrupt). |
| `False` | `StateEncrypted` | The state carries OpenTofu client-side encryption, which CAPTF does not support in v1. [Fix](../operator-guide/runbooks/state-unreadable.md#stateencrypted). |
| `False` | `StateInconsistent` | The state chunks disagree and do not form one complete state. [Fix](../operator-guide/runbooks/state-unreadable.md#stateinconsistent). |
| `False` | `StateLocked` | Something other than the object's own runner, such as a workstation, holds the state lock. Every Job waits `lockTimeoutSeconds` for it and then fails. See the [stale-lock runbook](../operator-guide/runbooks/stale-lock.md). |
| `False` | `StateLost` | The state Secret of an object that applied before is missing, or carries no inputs hash for an immutable kind. An object counts as having applied if it is provisioned, marked applied, digest-pinned or backed up on its own Secrets, which survive a `clusterctl move`. No Job runs until you restore the state. A deleting object keeps its finalizer until you restore it with `captf.io/restore-state` or set `spec.deletionPolicy: Retain`, which keeps what is left for a later adoption. [Fix](../operator-guide/runbooks/state-unreadable.md#statelost). |
| `False` | `RetainedStateFound` | The object's state Secrets, state backups or durable inputs carry `captf.io/retained-from-uid` with another object's UID: an earlier object of the same kind, namespace and name was deleted with `deletionPolicy: Retain`. Retained state is never adopted silently, so no Job runs. Set `spec.adoptRetainedState: true` to manage that infrastructure as this object's, or delete those Secrets to start afresh. Deleting the object removes its finalizer without touching them. See [Retain and Adopt](../concepts/deletion/retain.md#a-recreated-object-holds). |
| `Unknown` | `StateNotFound` | No state exists yet. The first apply creates it. [Details](../operator-guide/runbooks/state-unreadable.md#statenotfound). |

## RestoreJobSucceeded

Carried by all three. Polarity: normal. Set only once you request a restore
with the `captf.io/restore-state` annotation. Never feeds `Ready`.

The outcome of the newest state restore Job. A requested serial without a
backup, or a restore that waits for a lease, is reported here too. See
[state restore](../operator-guide/runbooks/state-restore.md).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `StateRestored` | The restore Job pushed the backup into the backend. |
| `False` | `RestoreBackupNotFound` | The annotation names no existing backup, or is not a serial. No Job starts. Pick a serial from `status.stateBackups`. |
| `False` | `RestoreFailed` | The restore Job failed. CAPTF does not retry it for the same serial, in `status.lastRestoredSerial`. To retry, remove the annotation, wait for `lastRestoredSerial` to clear and set it again. |
| `Unknown` | `WaitingForClusterOperation` | A machine's or pool's restore waits for its `TerraformCluster`'s operation to finish. |
| `Unknown` | `WaitingForMachineOperations` | A `TerraformCluster`'s restore waits for the operations of its machines and pools in flight. |
| `Unknown` | `WaitingForRunLease` | Another live Job holds the object's run lease. No Job starts until it finishes. |
| `Unknown` | `WaitingForJobSlot` | The restore waits for a Job slot. See [Job limits](../concepts/jobs/README.md#job-limits). |

## OutputsValid

Carried by all three. Polarity: normal.

Whether the module's outputs, read from state, satisfy the contract for the
object's role and the Cluster API field markers. See the [module
contract](../module-author/contract/README.md).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `OutputsValid` | The outputs are valid. |
| `True` | `InstancesTruncated` | A pool's `instances` output had more entries than the controller keeps, and CAPTF shortened it. The pool still provisions and nothing else about its outputs is invalid. See the [`MachinePool` role](../module-author/contract/v1alpha1/machinepool.md). |
| `False` | `FailureDomainMismatch` | The Machine requested a failure domain (`spec.failureDomain`) and the module's `failure_domain` output is `null` or differs from it. With no request, any placement is valid. |
| `False` | `OutputsInvalid` | An output violates the contract or a Cluster API marker. The message names it. |
| `False` | `OutputsMissing` | A required output is not declared. Check the module with [`tfcapi-lint`](../module-author/tfcapi-lint.md). |
| `False` | `ProviderIDChanged` | `provider_id` changed after it was first written. It is immutable. Delete the `Machine` to replace the instance. |
| `Unknown` | `OutputsPending` | Required outputs are `null`, so the first apply has not produced them yet. |

When several problems exist at once, the reason is the first that applies, in
this order: `OutputsMissing`, `OutputsInvalid`, `FailureDomainMismatch`,
`ProviderIDChanged`, `OutputsPending`, `InstancesTruncated`, `OutputsValid`.
The message is not limited to that reason: it lists every problem found,
separated by `; `.

## InfrastructureHealthy

Carried by all three. Polarity: normal.

The health the module reports, read from state at each refresh. After
provisioning it is the input that moves `Ready`. See [Drift and
health](../concepts/drift-and-health.md#from-module-health-to-infrastructurehealthy).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `Healthy` | The health state is `running` and healthy. |
| `False` | `InstanceDegraded` | The module reports `degraded`. |
| `False` | `InstancePending` | The module reports `pending`. Refresh runs on a doubling schedule up to five minutes. |
| `False` | `InstanceStopped` | The module reports `stopped`. |
| `False` | `InstanceTerminated` | The module reports `terminated`, or the instance vanished. See [terminated instances](../user-guide/remediation.md#terminated-instances). |
| `False` | `InstanceUnhealthy` | The state is `running` but healthy is `false`. |
| `False` | `Provisioning` | The first apply started and the object is not provisioned yet. This starts the clock for a MachineHealthCheck. |
| `Unknown` | `HealthUnknown` | The module reports `unknown`, an unrecognized state or no health at all. |
| `Unknown` | `ProviderIDMissing` | `provider_id` turned `null` after provisioning, for the first time. CAPTF reports the instance terminated only if the next sample is `null` too. |
| `Unknown` | `WaitingForProvisioning` | Before the first apply. |

To replace an unhealthy machine, see [machine
remediation](../user-guide/remediation.md).

## InputsApplied

Carried by all three. Polarity: normal. Never feeds `Ready`.

Whether the state's last successful apply used the object's current inputs and
no apply is pending. `Ready` does not say this: a provisioned object stays
`Ready` while an edit waits for an approval or a Job, because `Ready`'s inputs
after provisioning are unchanged. Consumers that wait for a change to land
(kstatus, Flux, Argo CD) should read `InputsApplied`. A `TerraformMachine`
has a fixed hash, so it is `True` once applied. The condition is set once per
pass, and left as it is while the object is deleting, paused, or when the pass
stopped before reading the state. It has no event of its own. `kubectl get -o
wide` shows it as a column.

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `InputsApplied` | The applied inputs hash equals the current one and no apply is pending. |
| `False` | `ApplyPending` | The current inputs differ from the applied ones, or nothing was applied yet, and no Job runs: the apply has not started, is gated, or is backing off. |
| `False` | `AwaitingApproval` | A `TerraformPlan` waits for its approval. |
| `False` | `ApplyRunning` | An apply Job is active. |
| `False` | `InputsApplyFailed` | The last apply failed and none has succeeded since. |
| `Unknown` | `InputsUnavailable` | The current inputs cannot be built (a dependency or the variables gate them), so they cannot be compared with the applied ones. |

## DriftJobSucceeded

Carried by all three. Polarity: normal. Never feeds `Ready`.

The outcome of the newest refresh or drift Job. See [Drift](../user-guide/drift.md).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `DriftChecked` | The newest refresh or drift Job succeeded. |
| `False` | `DriftJobDeadlineExceeded` | The drift Job hit `activeDeadlineSeconds`. Raise the deadline. |
| `False` | `DriftJobFailed` | The drift Job failed. The check retries with backoff. Read the Job's logs. |
| `Unknown` | `DriftJobRunning` | A drift Job runs. |
| `Unknown` | `DriftNotChecked` | No drift check has completed, or drift checks are disabled. |
| `Unknown` | `DurableInputsMissing` | A refresh or drift Job is due but has nothing to run against: the durable inputs Secret `captf-inputs-<kindshort>-<name>` is gone, and the object renders no current inputs in its place (a `TerraformMachine`, which is immutable, never does). No refresh or drift check runs until you restore the Secret, so `InfrastructureHealthy` keeps its last reading and drift goes unchecked. |
| `Unknown` | `WaitingForRunLease` | A refresh or drift Job waits for the object's run lease, which another live Job holds. |
| `Unknown` | `WaitingForJobSlot` | A refresh or drift Job waits for a Job slot: background Jobs start only below 80% of a limit. See [Job limits](../concepts/jobs/README.md#job-limits). |

## DriftDetected

Carried by all three. Polarity: negative. Never feeds `Ready`.

Whether the last drift check found the infrastructure differing from the
desired inputs. `True` is the problem. See [Drift](../user-guide/drift.md#read-the-results).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `DriftPending` | Remediation is pending, or a cluster re-apply failed. The message names a failed, blocked or changed remediation Job. See [the remediation cap](../concepts/jobs/retries.md#the-remediation-cap). |
| `True` | `DriftRemediating` | A remediation apply runs. |
| `True` | `DriftReported` | The drift action is `Report`, so CAPTF reports the drift and changes nothing. Accept it or set the action to `Remediate`; see [Remediate drift](../user-guide/drift.md#remediate-drift). |
| `False` | `NoDrift` | The last check found no drift. |
| `Unknown` | `DriftNotChecked` | No drift check has completed. CAPTF sets this on the first visit. |

## DeletionBlocked

Carried by `TerraformCluster`. Polarity: negative. Never feeds `Ready`.

Whether a deleting `TerraformCluster` waits for dependents. CAPTF sets it on the
first visit as `False`.

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `DependentsExist` | `TerraformMachines` or `TerraformMachinePools` of the cluster still exist, so no destroy runs. The message names them. See [the cluster waits for its machines](../concepts/deletion/order.md#the-cluster-waits-for-its-machines). |
| `False` | `NotBlocked` | Nothing blocks the deletion. |

## EndpointAvailable

Carried by `TerraformCluster`. Polarity: normal. Never feeds `Ready`. Not set
before the cluster is provisioned.

Whether a valid control-plane endpoint is known. See the [cluster
role](../module-author/contract/v1alpha1/cluster.md).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `EndpointAvailable` | A valid endpoint exists. |
| `False` | `WaitingForEndpoint` | The cluster is provisioned, and neither the module's `control_plane_endpoint` output nor `Cluster.spec.controlPlaneEndpoint` has a valid endpoint. Output one from the module or set it on the `Cluster`. |

## AutoscalingActive

Carried by `TerraformMachinePool`. Polarity: normal. Never `Unknown`. Never
feeds `Ready`, and Cluster API does not mirror it to the `MachinePool`.

Whether the pool's autoscaler annotations are present and valid, so the module
owns the desired count. See [Machine
pools](../user-guide/machine-pools.md#choose-fixed-replicas-or-autoscaling).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `ReplicasManagedByModule` | Both annotations are present and valid, and the controller writes the observed replicas back to `MachinePool.spec.replicas`. |
| `False` | `AutoscalingAnnotationsInvalid` | An annotation is present but the pair is incomplete, unparsable or has min above max. The message names the problem. The pool still applies without autoscaling. |
| `False` | `AutoscalingDisabled` | Neither annotation is set. `MachinePool.spec.replicas` is the only source of desired capacity. |
| `False` | `ReplicasManagedExternally` | Both annotations are valid, but the `MachinePool`'s `cluster.x-k8s.io/replicas-managed-by` annotation names another controller. CAPTF does not write the observed replicas back, so the two controllers do not fight over `spec.replicas`. Choose one owner. |

## CapacityResolved

Carried by `TerraformMachineTemplate`, which has no `Ready` condition.
Polarity: normal. Never `Unknown`.

Whether the template's capacity and node info were read from the module image's
labels. See [Templates](../user-guide/clusterclass.md).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `CapacityNotDeclared` | The image carries neither label. Fine unless a ClusterClass autoscaler needs the capacity. |
| `True` | `CapacityResolved` | Both labels parsed. |
| `False` | `CapacityLabelInvalid` | A label is present but invalid. Fix the label in the image; see the [image contract](../module-author/image-contract.md). |
| `False` | `ImageInspectFailed` | The registry fetch or authentication failed. Fix the image reference or the credentials. The controller also emits a `Warning` event. |

## VariablesValid

Carried by `TerraformMachineTemplate`, which has no `Ready` condition.
Polarity: normal.

Whether the template's `variables` and `variablesFrom` fit the variables
schema its image publishes in `io.captf.variables-schema` ([image
contract](../module-author/image-contract.md#oci-labels)). It is set when
the template's image is first inspected, with the capacity, so a ClusterClass
author sees a bad variable before any machine uses the template. A machine
or cluster made from the template is checked again, with its own sources,
before its Job (see [`DependenciesReady`](#dependenciesready)).

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `VariablesValid` | The variables fit the image's schema. |
| `True` | `VariablesSchemaNotDeclared` | The image carries no usable schema, so nothing is checked. |
| `False` | `VariablesRejected` | A variable is unknown to the module, required and not set, or of the wrong type, or a source has an invalid key. The message names the variable, never the value. `spec.template.spec` is immutable: create a new template. |
| `Unknown` | `VariablesSourcePending` | A `variablesFrom` source of the template is missing or unlabeled. The controller retries every 30 seconds. |
| `Unknown` | `VariablesSchemaUnavailable` | The image could not be read, so the schema is unknown. The same failure is reported on [`CapacityResolved`](#capacityresolved) as `ImageInspectFailed`. |

## Paused

Carried by all three. Polarity: a state, not a health reading. Never `Unknown`.
Never feeds `Ready`.

Whether reconciliation is paused. A paused object does bookkeeping only and
starts no Job. CAPTF sets it on the first visit.

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `Paused` | The object or its `Cluster` is paused: `spec.paused` on the `Cluster`, or the `cluster.x-k8s.io/paused` annotation on the object. `clusterctl move` pauses on purpose. A deletion waits until you unpause; see [pause stops a deletion](../concepts/deletion/order.md#pause-stops-a-deletion). |
| `False` | `NotPaused` | The object is not paused. |

## Deleting

Carried by all three. Polarity: negative. Never `Unknown`.

Whether the object is being deleted. `True` makes `Ready` `False`. The message
can say what the destroy waits for. CAPTF sets it on the first visit.

| Status | Reason | Meaning |
| --- | --- | --- |
| `True` | `Deleting` | The `deletionTimestamp` is set and no more specific reason applies. Wait for the destroy. If the object does not delete, follow [my object will not delete](../concepts/deletion/troubleshooting.md). |
| `True` | `DeletionPolicyUnresolved` | A deleting `TerraformMachine` or `TerraformMachinePool` sets no `spec.deletionPolicy`, and the `TerraformCluster` it inherits one from cannot be found. An inherited policy is never guessed, so neither a destroy nor a Retain runs. Set `spec.deletionPolicy` on the object to proceed. See [Deletion policy](resources/common-fields.md#deletion-policy). |
| `False` | `NotDeleting` | The `deletionTimestamp` is not set. |

## TerraformPlan

Carried by [`TerraformPlan`](resources/terraformplan.md) only. Polarity:
normal. The manager sets them; they do not feed the target's `Ready`. The
condition type `Ready` is the same constant as above (`ReadyCondition`); the
other type is `Approved` (`PlanApprovedCondition`).

| Type | Status | Reason | Meaning |
| --- | --- | --- | --- |
| `Ready` | `True` | `Pending` | The plan is live and waits for an approval (`PlanPendingReason`). |
| `Ready` | `True` | `Approved` | The plan is approved and its apply has not finished (`PlanApprovedReason`). |
| `Ready` | `True` | `Applied` | The approved apply succeeded (`PlanAppliedReason`). |
| `Ready` | `False` | `Superseded` | A newer plan replaced it, or it became moot (`PlanSupersededReason`). |
| `Ready` | `False` | `Failed` | The approved apply planned other changes and stopped (`PlanFailedReason`). A failed step or a deadline does not fail the plan. |
| `Approved` | `True` | `Approved` | `spec.approved` is `true`: the plan is `Approved`, `Applied` or `Failed` (`PlanApprovedReason`). |
| `Approved` | `False` | `Pending` | The plan is live and not approved (`PlanPendingReason`). |
| `Approved` | `False` | `NotApproved` | The plan is finished and was never approved (`PlanNotApprovedReason`). |
| `Approved` | `False` | `ApprovalIgnored` | The plan was approved, then superseded before it was applied (`PlanApprovalIgnoredReason`). A `PlanSuperseded` warning names the current plan. |

## Ready summarization

`Ready` is built with the Cluster API `SetSummaryCondition` helper from the
inputs below. Which inputs it uses depends on the kind and on whether
`status.initialization.provisioned` has latched `True`; it latches once and
stays. `Deleting` has negative polarity, so `True` there makes `Ready` `False`.

Before provisioning, all three kinds summarize the same nine inputs:

- `DependenciesReady`
- `IdentityAllowed`
- `CredentialsMirrored`
- `RunnerRBACReady`
- `ApplyJobSucceeded`
- `StateReadable`
- `OutputsValid`
- `InfrastructureHealthy`
- `Deleting`

`InputsApplied` is never an input. After provisioning, the inputs differ per kind:

| Kind | Inputs after provisioning |
| --- | --- |
| `TerraformCluster` | `InfrastructureHealthy`, `Deleting` |
| `TerraformMachine` | `InfrastructureHealthy`, `Deleting` |
| `TerraformMachinePool` | `InfrastructureHealthy`, `ApplyJobSucceeded`, `Deleting` |

!!! warning "A failed re-apply does not flip a cluster's or machine's `Ready`"

    After provisioning, a `TerraformCluster`'s `Ready` ignores
    `ApplyJobSucceeded`. If it did not, a failed re-apply would flip the
    `Cluster`'s `InfrastructureReady` and suspend every MachineHealthCheck of
    the cluster. A `TerraformMachine` is immutable and behaves the same. A
    `TerraformMachinePool` is mutable and re-applied regularly, so a failed
    re-apply shows in its `Ready`.

These types never feed `Ready`: [`Paused`](#paused),
[`DriftDetected`](#driftdetected), [`DriftJobSucceeded`](#driftjobsucceeded),
[`DeletionBlocked`](#deletionblocked),
[`EndpointAvailable`](#endpointavailable),
[`RestoreJobSucceeded`](#restorejobsucceeded) and
[`AutoscalingActive`](#autoscalingactive). An input that has not been set yet
counts as `Unknown`, so a new object is `Ready: Unknown`, never `True`. Only
`Deleting` is ignored while missing. `Ready`'s reason is always `Ready`,
`NotReady` or `ReadyUnknown`.

A `TerraformClusterIdentity` does not summarize. It sets its own `Ready` from
whether its credentials Secret exists (`SecretFound` or `SecretNotFound`).

!!! related "See also"

    - [Troubleshooting conditions](../operator-guide/troubleshooting/conditions.md)
    - [Troubleshooting: start here](../operator-guide/troubleshooting/README.md#start-here)
    - [Events](events.md)
    - [Observability](../operator-guide/observability.md)
    - [Runbooks](../operator-guide/runbooks/README.md)
    - [Drift and health](../concepts/drift-and-health.md)
    - [Annotations and labels](annotations-labels.md)
