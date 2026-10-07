---
description: Know what removing a CAPTF finalizer by hand deletes or leaves behind, and what to preserve before you do it.
tags:
  - Troubleshooting
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/scissors
subtitle: "Last-resort finalizer removal"
---

# Stripping a Finalizer by Hand

Removing the finalizer yourself (`kubectl patch ... remove
/metadata/finalizers`) skips the controller entirely: no destroy, no
cleanup, no event. Sometimes that is the last resort, for example after a
destroy that can never succeed and a manual cloud cleanup. Prefer the
[`Retain`](held.md#retain), which releases the same cases but
deletes only the run data, keeps the state, its backups and the inputs
for a later adoption, and records it in an event. This page lists what a bare strip
causes, so you can decide what to preserve first. The commands are in the
[stuck destroy runbook](../../operator-guide/runbooks/stuck-destroy.md).

!!! danger "A bare strip leaves your cloud resources running and untracked"

    The state was the only record of them, and the state backups are collected with the object. Back up and clean up first; see "Before you strip" below.


## What happens when it is gone

The object is deleted as soon as the finalizer goes. Kubernetes then
garbage-collects everything the object owns, and the controller can no
longer act for it.

| What | Result |
| --- | --- |
| The cloud resources | **Keep running, untracked.** The state was the only record of them |
| The state Secrets | Collected if owned (owner reference). A chunk written since the last reconcile, or any chunk of an object paused since, has only the backend labels and is **left behind** |
| The state backups | Collected: they are owned by the object. The newest copy of a lost state goes with them |
| The durable and applied inputs Secrets | Collected, with the pinned image and the rendered module needed to destroy by hand |
| The plan key Secret, the Jobs and their pods | Collected |
| The state lock Lease, the run lease, the cluster write lease | **Left behind.** They carry no owner reference |
| The credential mirror | Collected once every owner is gone; the mirror's owner list is not updated |
| The runner ServiceAccount and RoleBinding | Stay until the [sweep](cleanup.md#the-namespace-rbac-sweep) finds the namespace empty |

Two of those bite later:

- **Untracked state.** A leftover state Secret has no owner and nothing that
  lists it. The state suffix is a hash of the namespace, kind and name, never the
  UID, so a new object with the same three derives the same suffix and
  reads that old state as its own.
- **Leftover leases.** A run or cluster write lease whose holder Job is gone
  is taken over by the next Job after the one-minute grace. The sweep
  deletes them once the namespace holds no `Terraform*` object.

## Before you strip

1. **Back up** the state Secrets, the backups and the durable inputs
   Secret, or remove their owner references so they survive: stuck destroy
   runbook, steps 2 and 3.
2. **Clean up the cloud resources.** Run the pinned image's `destroy`
   against the backed-up state, or use the cloud console.
3. **Check `metadata.finalizers`.** Something else may have added one.
   Remove only CAPTF's, by index.
4. **For a `TerraformCluster`, delete its machines first.** The destroy's
   dependents wait is skipped when you strip, and a machine left behind
   loses its cluster.

!!! related "See also"

    - [Held deletions](held.md#retain) and [Retain and Adopt](retain.md).
    - [Cleanup and garbage collection](cleanup.md).
    - [Stuck Destroy](../../operator-guide/runbooks/stuck-destroy.md).
