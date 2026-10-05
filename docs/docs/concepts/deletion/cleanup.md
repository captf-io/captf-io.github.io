---
description: Which of the controller's cleanup, Kubernetes garbage collection and the namespace RBAC sweep removes what, and what nothing deletes.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/brush-cleaning
subtitle: "What is removed after destroy"
---

# Cleanup and Garbage Collection

Three things remove what CAPTF stored for an object: the controller's own
cleanup, Kubernetes garbage collection through owner references, and the
namespace RBAC sweep. Which one removes what is what decides what survives
a finalizer that comes off early.

## The controller's cleanup

Cleanup runs in exactly three situations: after a successful destroy, on a
deletion with nothing to destroy, and on [abandon](held.md#abandon). It
never runs while a state Secret may still describe live resources, and it
waits (five-second retries) while a Job of the object still holds a live
run lease. Its steps, in order:

1. **The state Secrets**, every chunk, deleted one by one (the manager role
   has no `deletecollection`), then the **state lock Lease**
   `lock-tfstate-default-<suffix>`. Neither Terraform nor OpenTofu deletes
   its own state: a destroy only empties it.
2. **The durable inputs Secret** `captf-inputs-<kindshort>-<name>`.
3. **The plan key Secret.** It is owned by the object too, but is removed
   here so it does not outlive a finished destroy while it waits for
   garbage collection.
4. **The run lease** `captf-run-<suffix>` and, for a `TerraformCluster`, the
   **cluster write lease** `captf-cluster-<hash>`: every run or cluster
   lease carrying the object's owner labels, whoever holds it.
5. **The mirror's ownership.** The object is removed from the owners of the
   credential mirror `captf-creds-<identity>`. The mirror is deleted when
   this was its last owner, with a `MirrorRemoved` event.
6. **The finalizer**, in the same patch that writes the status.

A destroy then reports a `Destroyed` event ("Infrastructure destroyed;
state and inputs removed") and `FinalizerRemoved`; an abandon reports the
`InfrastructureAbandoned` warning; a no-state deletion reports only
`FinalizerRemoved`. The object's per-object metric series go with the
finalizer.

## What Kubernetes collects

These are owned by the object and carry no deletion of their own. They go
when the object does, after the finalizer:

| Object | Owner | Notes |
| --- | --- | --- |
| State backups `captf-state-backup-<suffix>-<serial>` | The object, not as a controller | Deliberately not deleted by cleanup; the finalizer keeps them for a held deletion |
| Jobs and their pods | The object, as a controller | Also pruned earlier by the history limits |
| Per-run Secrets | Their Job | Normally deleted much earlier, when the Job finishes and is bookkept |
| Anything left of the state chunks, durable inputs or plan key | The object | Only when cleanup did not run: a stripped finalizer |

!!! note "Owner references never delay the owner's deletion"

    An owner reference without `blockOwnerDeletion` never delays the
    owner's deletion.

## What nothing deletes

- **The cloud resources**, after an abandon or a stripped finalizer.
- **The credential source Secret** and the `TerraformClusterIdentity`. A
  `variablesFrom` ConfigMap or Secret. A Cluster Cluster API still owns.
- **The runner ServiceAccount and RoleBinding**, until the namespace is
  empty of `Terraform*` objects (below).
- **The credential mirror**, while another object of the namespace still
  uses it.

## The namespace RBAC sweep

When a reconcile removed a finalizer, it then sweeps the object's
namespace. If the namespace holds no `TerraformCluster`,
`TerraformMachine` or `TerraformMachinePool`, the sweep deletes the
`captf.io/managed=true` ServiceAccounts, RoleBindings and Leases in it. If
objects remain, it only prunes the RoleBinding's subjects down to the
ServiceAccounts some object still runs as.

- The sweep runs after the finalizer's removal is persisted, but the
  deleted object still counts until it is gone. When it is the last one,
  this sweep therefore may find the namespace non-empty, and the periodic
  sweep removes the runner objects instead: at manager start, then every
  `--sync-period` (default 10 minutes) on the leader, with 10% jitter.
- It reads through the uncached API reader without `--watch-filter`, so an
  object another manager instance owns keeps the namespace.
- A failed sweep is logged, never an error: the next tick retries.
- Templates run no Jobs, so they do not keep a namespace.

The same sweep is what clears the runner objects a `clusterctl move`
leaves on the source. See [RBAC](../../operator-guide/rbac.md#the-orphan-sweep).

!!! related "See also"

    - [Secret Management](../secret-management/README.md) for what each Secret
      holds.
    - [Terraform State: state on deletion](../state.md#state-on-deletion).
    - [Stripping a finalizer by hand](manual-finalizer.md).
