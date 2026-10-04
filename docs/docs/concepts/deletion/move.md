---
description: "Understand how clusterctl move deletes the source objects, what moves and what does not, and what the target does on its first reconcile."
tags:
  - Operators
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "Steven Crothers"
icon: lucide/arrow-right-left
subtitle: "What a move deletes on purpose"
---

# clusterctl move

`clusterctl move` is a delete that skips the controller's delete path. It
copies a Cluster's objects to another management cluster, then deletes them
from the source with their finalizers stripped. No destroy runs and no
cleanup runs on the source; the infrastructure is not touched, because the
target takes it over. The procedure is the [clusterctl move
runbook](../../operator-guide/runbooks/move.md). This page explains how the
pieces behave.

## How the source is deleted

`clusterctl` pauses the Cluster, annotates each object
`clusterctl.cluster.x-k8s.io/delete-for-move`, and deletes it.

- The `TerraformMachine` delete webhook honors the annotation only while the
  owning Cluster, found through the machine's `cluster.x-k8s.io/cluster-name`
  label, has `spec.paused=true`. On an unpaused, missing or unlabeled
  Cluster the ordinary check applies and the delete is refused while a live
  Machine references the object. See [Order and
  finalizers](order.md#the-webhook-refuses-a-direct-machine-delete).
- A paused object runs only the paused branch, so the controller does not
  start a destroy for the objects being deleted.
- Before any of this, `clusterctl` waits for the `block-move` annotation to
  clear. The controller sets it before it creates a Job, persists it before
  the Job exists, and clears it once no Job is active, also while paused. A
  Job the Job cache has not shown yet keeps the annotation: the controller
  checks the API server and the live run lease before it clears. See [The
  clusterctl move block](../lifecycle.md#the-clusterctl-move-block).

## What moves

`clusterctl` follows a Cluster's owner-reference chain and any object
carrying the move label.

| Object | Moves by | Notes |
| --- | --- | --- |
| The `Terraform*` objects | Owner chain | Spec and metadata only |
| State Secrets, every chunk | `clusterctl.cluster.x-k8s.io/move` label, and the owner reference once the object owns it | The label is set by the backend config on every state Secret |
| State backups | The same label and owner reference | |
| The durable inputs Secret | Owner reference | No move label; it carries the `captf.io/applied` marker and the pinned digest |
| The plan key Secret | Owner reference | |
| The credential mirror | Owner reference | Recreated if missing |
| The `TerraformClusterIdentity` | Its CRD's `move-hierarchy` label | Cluster-scoped; the first namespace's move copies it, later ones skip it |

## What does not move

- **Status.** The target rebuilds it from the state on its first
  reconcile: outputs, health, `provisioned`. What status carried that
  nothing else does is the "ever applied" record, which is why the
  `captf.io/applied` marker lives on a Secret that does move. See [ever
  applied](held.md#ever-applied).
- **The Leases.** The state lock Lease is not a kind `clusterctl` moves;
  the backend recreates it at the target's next `init`. The run and
  cluster write leases are taken afresh. A lease whose Job was active
  during the move stays on the source.
- **The runner ServiceAccount and RoleBinding.** The target controller
  creates them before its first Job.
- **The credential source Secret.** The Secret a `TerraformClusterIdentity`
  names is deliberately neither owned nor labeled for move: labeling it
  would make `clusterctl` delete it from the source, where other namespaces
  may still use it. **You must recreate it on the target.** Until then the
  identity reports `Ready=False`/`SecretNotFound` and every object using it
  `IdentityAllowed=False`/`SecretNotFound`. See the [runbook
  step](../../operator-guide/runbooks/move.md#the-identitys-credentials-secret-does-not-move)
  for the command.
- **`variablesFrom` sources.** Not owned, so not moved. A `TerraformCluster`
  or `TerraformMachinePool` waits at `DependenciesReady=False`/`VariablesSourceNotFound`
  on the target until the source exists there.

The `captf.io/managed` Leases, ServiceAccounts and RoleBindings left on the
source are removed by the [namespace RBAC sweep](cleanup.md#the-namespace-rbac-sweep)
once the namespace holds no `Terraform*` object.

## After the move

On the target, the first reconcile reads the moved state. A state that did
not arrive, while the durable Secret's marker or a backup says the object
applied, reads as `StateLost`, not as a new object, so it is never applied a
second time next to the live resources; restore a backup or investigate.
Periodic checks have no history to count from, so the drift and health
schedules start from the object's creation time with a per-object jitter
rather than all at once.

Deleting the source namespace after a move has a limit; see [the known
limit](namespaces.md#the-known-limit).

!!! related "See also"

    - [clusterctl move runbook](../../operator-guide/runbooks/move.md).
    - [Lifecycle walkthroughs: `clusterctl move`](../secret-management/lifecycle.md#clusterctl-move).
