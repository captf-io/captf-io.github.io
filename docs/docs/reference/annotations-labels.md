---
description: "Every annotation, label and finalizer CAPTF reads or sets: the keys you set to approve, restore or abandon, CAPTF's own bookkeeping keys and the captf_tags modules receive."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/bookmark
subtitle: "Keys CAPTF reads and sets"
---

# Annotations, Labels and Finalizers

CAPTF reads a few keys that you set to approve a plan, restore a state or
release a stuck deletion. It writes many more for its own bookkeeping, owns
three finalizers, and honors several Cluster API and clusterctl keys. This
page lists all of them, grouped by who uses them.

## The keys you are most likely to use

| Key | Put it on | Value | Effect |
| --- | --- | --- | --- |
| `captf.io/approve-plan` | `TerraformCluster` with `applyPolicy: Manual` | Plan hash from `status.plan.planHash` | Applies that one plan |
| `captf.io/approve-destructive-plan` | `TerraformCluster`, `TerraformMachine`, `TerraformMachinePool` | Hash from the `DestructivePlanBlocked` message | Lets one blocked apply delete or replace resources |
| `captf.io/restore-state` | `TerraformCluster`, `TerraformMachine`, `TerraformMachinePool` | Serial from `status.stateBackups` | Pushes that backup back as the state |
| `captf.io/abandon-infrastructure` | A deleting `Terraform*` object | The object's `metadata.uid` | Removes the finalizer without a destroy |
| `captf.io/variables` | A `ConfigMap` or `Secret` | `true` | Allows it as a `variablesFrom` source |
| `captf.io/runner` | A `ServiceAccount` | `true` | Allows it as a custom runner account |

## Keys you set

You set these on your own objects. Approvals and restores are one-shot:
CAPTF removes the annotation after it acts, so a later change needs a new
one.

### `captf.io/approve-plan`

Approves one plan of a `TerraformCluster` whose `spec.applyPolicy` is
`Manual`. Only `TerraformCluster` has an `applyPolicy`, so only it accepts
this key.

| | |
| --- | --- |
| Kind | `TerraformCluster` |
| Value | The plan hash in `status.plan.planHash` |
| Removed by CAPTF | Yes, once the apply of that plan succeeds |

The apply runs only if it plans exactly the same changes again. If the plan
changed, the apply stops, `status.plan` shows the new plan, and the old
approval no longer matches. Approving a plan also approves the deletes and
replacements it lists, so you do not also need
`captf.io/approve-destructive-plan`.

```sh
kubectl annotate terraformcluster <name> -n <namespace> \
  captf.io/approve-plan=<plan-hash> --overwrite
```

`<plan-hash>` is `status.plan.planHash`; the `PlanAwaitingApproval`
condition message prints the full command. See [Plan
Approval](../user-guide/plan-approval.md) and [Manual Plan
Approval](../concepts/approvals/manual-approval.md).

### `captf.io/approve-destructive-plan`

Approves one apply whose plan deletes or replaces resources, or one drift
remediation that would.

| | |
| --- | --- |
| Kinds | `TerraformCluster`, `TerraformMachine`, `TerraformMachinePool` |
| Value | The inputs hash from the `DestructivePlanBlocked` message. On a pool, the approval hash |
| Removed by CAPTF | Yes, after an apply of the approved hash succeeds |

The value names the inputs the apply renders, not the object. Any later
change to the inputs produces a different hash, so the approval stops
matching and the next destructive plan is blocked again. A value that does
not equal the hash CAPTF rendered approves nothing and is not an error.

CAPTF consumes the approval after any successful apply of that hash, even
one whose plan was not destructive, so a later destructive remediation of
the same inputs needs a new approval. On a pool, CAPTF also removes the
annotation when the cluster exports it approved a change of return to the
exports the pool already applied.

```yaml
metadata:
  annotations:
    captf.io/approve-destructive-plan: <inputs-hash>
```

Approving needs only `patch` on the object. The `ApplyJobSucceeded`
condition message prints the exact `kubectl annotate` command. See [The
Destructive-Plan Guard](../concepts/approvals/destructive-guard.md#approving).

### `captf.io/restore-state`

Restores a state backup. A restore Job pushes the backup into the backend
with `state push -force`, replacing the current state.

| | |
| --- | --- |
| Kinds | `TerraformCluster`, `TerraformMachine`, `TerraformMachinePool` |
| Value | The serial of a backup listed in `status.stateBackups` |
| Removed by CAPTF | Yes, once the restore Job succeeds |

A value that is not a serial, or that names no complete backup, sets
`RestoreJobSucceeded=False` with reason `RestoreBackupNotFound` and starts
nothing. A restore takes precedence over apply, drift and refresh, and no
approval gates it. A failed restore is not retried for the same serial: set
another serial, or remove the annotation, wait until
`status.lastRestoredSerial` clears, and set it again.

On an object that is being deleted, the annotation is ignored while the
state reads. It runs only while the deletion is held because the state is
missing or unreadable; the restore then runs first and the destroy follows.

```sh
kubectl annotate terraformcluster <name> -n <namespace> \
  captf.io/restore-state=<serial> --overwrite
```

`<serial>` is a number from `kubectl get terraformcluster <name> -n
<namespace> -o jsonpath='{.status.stateBackups}'`. See the [state restore
runbook](../operator-guide/runbooks/state-restore.md) and [Backups and
Restore](../concepts/secret-management/backups.md#restore).

### `captf.io/abandon-infrastructure`

Releases a deletion that cannot finish, without running a destroy.

| | |
| --- | --- |
| Kinds | `TerraformCluster`, `TerraformMachine`, `TerraformMachinePool`, while deleting |
| Value | The object's `metadata.uid`. Any other value is ignored |
| Removed by CAPTF | No. The object is deleted with it |

The annotation applies when the deletion is held because the state is
missing or unreadable, the last destroy failed, or the destroy cannot
start: the durable inputs are gone, the identity no longer allows the
namespace or no longer exists, or the runner credentials cannot be
prepared. CAPTF then runs its normal cleanup, removes the finalizer
without a destroy, and records an `InfrastructureAbandoned` `Warning`
event naming the cause. An object whose state reads and whose destroy can
start is destroyed as usual, even with the annotation set.

!!! danger "Abandoning leaves the infrastructure running and untracked"

    CAPTF does not destroy anything. Whatever the module created keeps
    running and costing money, and the state backups are deleted with the
    object. Back up what you need and clean up the resources yourself.

```sh
kubectl annotate terraformcluster <name> -n <namespace> \
  captf.io/abandon-infrastructure="$(kubectl get terraformcluster <name> \
  -n <namespace> -o jsonpath='{.metadata.uid}')"
```

See [Held Deletions](../concepts/deletion/held.md#abandon) and the [stuck
destroy runbook](../operator-guide/runbooks/stuck-destroy.md#abandon-instead).
Prefer this key to removing the finalizer by hand, which skips cleanup;
see [Stripping a Finalizer by Hand](../concepts/deletion/manual-finalizer.md).

### `captf.io/variables`

A label that opts a `ConfigMap` or `Secret` in as a `variablesFrom` source.

| | |
| --- | --- |
| Put it on | The `ConfigMap` or `Secret` that `spec.variablesFrom` names |
| Value | `true` |
| Removed by CAPTF | Never. It is a standing opt-in |

The manager reads and watches only labeled sources, so an unlabeled source
counts as missing. Create it in each namespace that uses it.

```sh
kubectl label configmap <name> -n <namespace> captf.io/variables=true
```

See [Module Variables](../user-guide/variables.md#set-a-variable-from-a-configmap-or-secret).

### `captf.io/runner`

A label that opts a custom runner `ServiceAccount` in.

| | |
| --- | --- |
| Put it on | The `ServiceAccount` named by `spec.jobs.serviceAccountName` |
| Value | `true` |
| Removed by CAPTF | Never |

The default `captf-runner` account needs no label. Without the label on a
custom account, `RunnerRBACReady` is `False` with reason
`ServiceAccountNotOptedIn` and CAPTF creates no Job. The label is consent,
not authorization: anyone who can label the account opts it in.

```sh
kubectl label serviceaccount <name> -n <namespace> captf.io/runner=true
```

See [RBAC](../operator-guide/rbac.md#custom-serviceaccounts-and-the-runner-opt-in).

## Keys CAPTF sets

CAPTF writes these for its own bookkeeping and reads them back on the next
reconcile. Don't edit or remove them: a wrong value can cause a repeated
apply, a skipped approval or an orphaned Secret. They are listed so you can
recognize them in `kubectl get -o yaml` output.

### On your objects and their Machines

| Key | Kind | On | Records |
| --- | --- | --- | --- |
| `captf.io/endpoint-source` | annotation | `TerraformCluster` | Who owns the control-plane endpoint: `user` if one existed before the first apply, `module` if the module created it. Written once, never changed |
| `captf.io/remediation-requested` | annotation | `Machine` | That CAPTF set `cluster.x-k8s.io/remediate-machine`; the value is the reason. CAPTF removes only a request it made |
| `clusterctl.cluster.x-k8s.io/block-move` | annotation | `TerraformCluster`, `TerraformMachine`, `TerraformMachinePool` | That a Job is starting or running, so `clusterctl move` waits. Set before a Job is created and cleared when none is active |

### On state and backup Secrets

| Key | Kind | On | Records |
| --- | --- | --- | --- |
| `captf.io/managed` | label | Everything CAPTF owns: state Secrets, Leases, mirrors, run Jobs, the default runner `ServiceAccount` | Selects the objects the manager caches and sweeps |
| `captf.infrastructure.cluster.x-k8s.io/owner-kind` | label | State Secrets, Leases | The owning object's kind |
| `captf.infrastructure.cluster.x-k8s.io/owner-name` | label | State Secrets, Leases | The owning object's name |
| `captf.io/inputs-hash` | annotation | The base state Secret, chunk 0 of a backup | The inputs hash of the state currently adopted |
| `captf.io/state-backup` | label | Backup chunk Secrets | Marks a Secret as a state backup chunk |
| `captf.io/state-backup-suffix` | label | Backup chunk Secrets | The backend Secret suffix the backup came from |
| `captf.io/state-backup-serial` | annotation | Backup chunk Secrets | The backup's state serial; the value `captf.io/restore-state` names |
| `captf.io/state-backup-lineage` | annotation | Backup chunk Secrets | The state's lineage ID at backup time |
| `captf.io/state-backup-taken-at` | annotation | Backup chunk Secrets | When the backup was taken |
| `captf.io/state-backup-source-job` | annotation | Backup chunk Secrets | The Job whose apply produced the backed-up state |
| `captf.io/state-backup-digest` | annotation | Backup chunk Secrets | A digest of the state, used to detect a conflicting concurrent backup |
| `captf.io/state-backup-resources` | annotation | Backup chunk Secrets | The backup's managed resource count |
| `captf.io/state-backup-set` | annotation | Backup chunk Secrets | Groups the chunks of one backup |
| `captf.io/state-backup-chunk` | annotation | Backup chunk Secrets | The chunk's index within its set |
| `captf.io/state-backup-chunks` | annotation | Backup chunk Secrets | The set's total chunk count |

The `captf.io/inputs-hash` key is an annotation, not a label.

### On leases and the identity mirror

| Key | Kind | On | Records |
| --- | --- | --- | --- |
| `captf.io/lease` | label | `coordination.k8s.io` Leases | Tells a CAPTF run or cluster lease from the backend's own lock Lease |
| `captf.io/lease-op` | annotation | Leases | The operation the holder runs, for diagnostics |
| `captf.io/lease-acquired-at` | annotation | Leases | When the lease was acquired |
| `captf.io/mirrored` | label | The identity credential mirror Secret | Marks a Secret as a credential mirror |
| `captf.io/source-hash` | annotation | The identity credential mirror Secret | A hash of the source identity's credentials, so a change rewrites the mirror |

### On the durable inputs Secret

The durable inputs Secret holds what CAPTF needs to re-render and destroy
an object. Unlike `status`, these annotations move with the Secret.

| Key | Kind | On | Records |
| --- | --- | --- | --- |
| `captf.io/image` | annotation | Durable inputs Secret | `spec.source.image` as last written |
| `captf.io/image-digest` | annotation | Durable inputs Secret | The resolved image digest, so a floating tag stays pinned across reconciles |
| `captf.io/identity` | annotation | Durable inputs Secret, identity mirror | The `TerraformClusterIdentity` the credentials came from |
| `captf.io/applied` | annotation | Durable inputs Secret | `true` once an apply succeeded or a state with an inputs hash was read, so a later missing state reads as lost, not never written |
| `captf.io/interrupted-apply` | annotation | Durable inputs Secret of a cluster or pool | An apply Job that was deleted while it ran. It may have applied part of its change, so an apply stays due, and is guarded, until one started after it succeeds |
| `captf.io/pending-cluster-outputs` | annotation | A pool's durable inputs Secret | A change of the cluster's exports whose pool apply was blocked before a destructive plan, as JSON. The pool keeps applying the exports of its last successful apply until you approve |
| `captf.io/partial-cluster-outputs` | annotation | A pool's durable inputs Secret | A change of the cluster's exports whose pool apply failed, so the state may hold part of it, as JSON. Every apply is guarded until one succeeds |
| `captf.io/applied-cluster-outputs-hash` | annotation | A pool's durable inputs Secret | The hash of the cluster exports the last successful pool apply rendered. A hash, never an exported value |

### On run Jobs

| Key | Kind | On | Records |
| --- | --- | --- | --- |
| `captf.infrastructure.cluster.x-k8s.io/op` | label | Job and pod | The operation: `apply`, `destroy`, `refresh`, `drift`, `restore` or `plan` |
| `captf.infrastructure.cluster.x-k8s.io/attempt` | label | Job and pod | The Job's attempt number |
| `captf.io/bookkept` | annotation | Job | That a finished Job is already counted in `status`, so it is not counted twice |
| `captf.io/interrupted` | annotation | Job | That the Job stopped without a clean result, for example it was evicted |
| `captf.io/drift-remediation` | annotation | Job | That the apply is a drift remediation, not an ordinary apply |
| `captf.io/destructive-plan-blocked` | annotation | Job | That the apply stopped because its plan was destructive and unapproved |
| `captf.io/plan-changed` | annotation | Job | That the apply stopped because a re-plan under `Manual` no longer matched the approved plan |
| `captf.io/plan-unreadable` | annotation | Job | That the Job's plan result could not be parsed |
| `captf.io/approved-plan` | annotation | Job | The plan hash an apply Job was created to satisfy under `Manual` |
| `captf.io/after-failed-apply` | annotation | Job | That the apply started while the newest apply had failed, so an earlier failure still counts and the apply waits for approval instead of being dropped |
| `captf.io/after-interrupted-apply` | annotation | Job | The vanished apply Job that this apply started after. Its success removes the `captf.io/interrupted-apply` record |
| `captf.io/restore-serial` | annotation | Restore Job | The backup serial the Job pushes |
| `captf.io/approval-hash` | annotation | Pool apply Job | The approval hash of a pool apply guarded for a change of the cluster's exports: what `captf.io/approve-destructive-plan` must name |
| `captf.io/cluster-outputs-hash` | annotation | Pool apply Job | The hash of the cluster exports the apply renders |
| `captf.io/held-cluster-outputs` | annotation | Pool apply Job | That the apply rendered the exports of the last successful apply while a change waited for approval, so its success does not count as applying that change |

## Finalizers

CAPTF puts one finalizer on each workload kind. It blocks deletion until
the controller has destroyed the object's Terraform-managed resources and
cleaned up its Secrets.

| Finalizer | Kind | Guards |
| --- | --- | --- |
| `terraformcluster.infrastructure.cluster.x-k8s.io` | `TerraformCluster` | The cluster's Terraform-managed resources |
| `terraformmachine.infrastructure.cluster.x-k8s.io` | `TerraformMachine` | The machine's Terraform-managed resources |
| `terraformmachinepool.infrastructure.cluster.x-k8s.io` | `TerraformMachinePool` | The pool's Terraform-managed resources |

`TerraformClusterIdentity` and the `*Template` kinds have no finalizer.
Nothing external depends on an identity directly, so a delete webhook
protects an identity that is still in use instead. When a deletion is
stuck, see [Held Deletions](../concepts/deletion/held.md); the finalizer is
removed by the controller, or by [`captf.io/abandon-infrastructure`](#captfioabandon-infrastructure).
Each kind's page under [Resources](resources/README.md) names its
finalizer.

## Cluster API and clusterctl keys

These keys belong to Cluster API or clusterctl. CAPTF reads or writes them
as noted.

| Key | Kind | On | CAPTF |
| --- | --- | --- | --- |
| `cluster.x-k8s.io/cluster-name` | label | `Terraform*` objects, run Jobs, state Secrets, Leases | Reads it to find the owning `Cluster`, and scopes everything it creates with it. Cluster API sets it on the objects it creates |
| `cluster.x-k8s.io/remediate-machine` | annotation | `Machine` | Sets it with `captf.io/remediation-requested` when health sampling finds an unhealthy instance, and removes it once the instance reads `Healthy` and only if CAPTF set it. Cluster API then remediates the `Machine` |
| `cluster.x-k8s.io/replicas-managed-by` | annotation | `MachinePool` | Sets it to `captf` on an autoscaled pool, so Cluster API stops treating `spec.replicas` as authoritative. Removes only a `captf` value. A foreign value is left alone and CAPTF stops writing replicas back |
| `cluster.x-k8s.io/cluster-api-autoscaler-node-group-min-size` | annotation | `MachinePool` | You set it. The pool's minimum replica count |
| `cluster.x-k8s.io/cluster-api-autoscaler-node-group-max-size` | annotation | `MachinePool` | You set it. The pool's maximum replica count |
| `cluster.x-k8s.io/cloned-from-name` | annotation | `Terraform*` objects | Reads it as the `captf.io/template` tag. Cluster API sets it when it clones from a template |
| `clusterctl.cluster.x-k8s.io/move` | label | State Secrets, Leases | Sets it so `clusterctl move` copies them |
| `clusterctl.cluster.x-k8s.io/move-hierarchy` | label | The `TerraformClusterIdentity` CRD | Ships it on the CRD so `clusterctl move` brings objects that reference an identity |
| `clusterctl.cluster.x-k8s.io/block-move` | annotation | `Terraform*` objects | Sets it while a Job runs, so `clusterctl move` waits |
| `clusterctl.cluster.x-k8s.io/delete-for-move` | annotation | `TerraformMachine` | Reads it in the delete webhook. clusterctl sets it when it deletes the source of a move |

The two autoscaler annotations go on the Cluster API `MachinePool`, not the
`TerraformMachinePool`. You must set both, as non-negative integers with
the minimum not above the maximum; otherwise the pool reports
`AutoscalingActive=False` and applies without autoscaling.

```yaml
apiVersion: cluster.x-k8s.io/v1beta2
kind: MachinePool
metadata:
  name: <pool-name>
  namespace: <namespace>
  annotations:
    cluster.x-k8s.io/cluster-api-autoscaler-node-group-min-size: "3"
    cluster.x-k8s.io/cluster-api-autoscaler-node-group-max-size: "10"
```

See [Choose fixed replicas or
autoscaling](../user-guide/machine-pools.md#choose-fixed-replicas-or-autoscaling).

CAPTF honors `delete-for-move` only while the owning `Cluster` is paused,
which clusterctl sets before it deletes anything. On an unpaused cluster
the annotation changes nothing, so setting it by hand does not skip the
ordinary delete checks. See [clusterctl move](../concepts/deletion/move.md)
and [Machine Remediation](../user-guide/remediation.md#the-remediate-machine-annotation).

## `captf_tags` keys

These are not Kubernetes metadata. CAPTF renders them into the
`captf_tags` input of every module, as a Terraform map of strings that the
module should put on the resources it creates. All six keys are always
present. See [Job Inputs](../concepts/inputs.md).

| Key | Value |
| --- | --- |
| `captf.io/cluster` | The owning `Cluster`'s name |
| `captf.io/namespace` | The owning object's namespace |
| `captf.io/kind` | The owning object's kind: `TerraformCluster`, `TerraformMachine` or `TerraformMachinePool` |
| `captf.io/name` | The owning object's name |
| `captf.io/managed-by` | Always `captf` |
| `captf.io/template` | The object's `cluster.x-k8s.io/cloned-from-name` annotation, or empty when absent |
