---
title: "Deletion and Teardown in CAPTF"
description: How deleting a TerraformCluster, machine or pool runs a destroy Job, what holds a deletion, and what is left behind if you short-circuit it.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/trash-2
subtitle: "How a cluster goes away"
---

# Deletion and Teardown

Deleting a `TerraformCluster`, `TerraformMachine` or `TerraformMachinePool`
means running Terraform's `destroy` in a Job, then removing what CAPTF
stored about the object. Most of the time nothing needs doing: you delete
the Cluster Cluster API owns and everything follows. This chapter explains
the order things happen in, what holds a deletion, how a deletion ends, and
what is left behind when you short-circuit it. The step-by-step recoveries
stay in the [runbooks](../../operator-guide/runbooks/README.md); this
chapter is the model behind them.

The pages:

1. This page: the rules in one table, and the pages that follow.
2. [Order and finalizers](order.md): who deletes what first, and when the
   finalizer comes off.
3. [The destroy Job](destroy-job.md): what runs, what does not gate it, and
   how it fails.
4. [Held deletions](held.md): missing or unreadable state, restore, and
   `Retain`.
5. [Retain and Adopt](retain.md): delete without a destroy, keep the state,
   and adopt it later.
6. [Terminating namespaces](namespaces.md): deletions that need no Job, and
   the Secrets that go with the namespace.
7. [Cleanup and garbage collection](cleanup.md): what the controller deletes,
   what Kubernetes deletes, and the RBAC sweep.
8. [`clusterctl move`](move.md): the delete that skips the delete path.
9. [Stripping a finalizer by hand](manual-finalizer.md): the consequences.
10. [My object will not delete](troubleshooting.md): a flowchart from the
    symptom to the action.

## In this section

<div class="grid cards" markdown>

-   :material-sort-variant-remove:{ .lg .middle } __Order and Finalizers__

    ---

    Who deletes what first, and when the finalizer comes off.

    [:octicons-arrow-right-24: Order and Finalizers](order.md)

-   :material-delete-forever-outline:{ .lg .middle } __The Destroy Job__

    ---

    What runs, what does not gate it, and how it fails.

    [:octicons-arrow-right-24: The Destroy Job](destroy-job.md)

-   :material-archive-arrow-down-outline:{ .lg .middle } __Retain and Adopt__

    ---

    Delete without a destroy, keep the state, and adopt it later.

    [:octicons-arrow-right-24: Retain and Adopt](retain.md)

-   :material-folder-remove-outline:{ .lg .middle } __Terminating Namespaces__

    ---

    Deletions that need no Job, and the Secrets that go with the namespace.

    [:octicons-arrow-right-24: Terminating Namespaces](namespaces.md)

-   :material-broom:{ .lg .middle } __Cleanup and Garbage Collection__

    ---

    What the controller deletes, what Kubernetes deletes, and the RBAC sweep.

    [:octicons-arrow-right-24: Cleanup and Garbage Collection](cleanup.md)

-   :material-lifebuoy:{ .lg .middle } __My Object Will Not Delete__

    ---

    A flowchart from the symptom to the action.

    [:octicons-arrow-right-24: My Object Will Not Delete](troubleshooting.md)

</div>

## The rules

A deleting object follows these rules, in this order. The first that
applies decides the pass.

| Situation | What happens | Page |
| --- | --- | --- |
| The object or its Cluster is paused | Nothing: a paused object runs only Job bookkeeping, so it neither destroys nor releases | [Order](order.md#pause-stops-a-deletion) |
| A Job of the object is running | The deletion waits for it; the destroy starts after | [Order](order.md#the-finalizer) |
| A `TerraformCluster` with machines or pools left | `DeletionBlocked=True`/`DependentsExist`, no destroy yet | [Order](order.md#the-cluster-waits-for-its-machines) |
| No state, and the object never applied | The finalizer comes off at once | [Held](held.md#ever-applied) |
| No state, and the object applied before | Held: `StateReadable=False`/`StateLost` | [Held](held.md) |
| State exists but cannot be read | Held: `StateCorrupt`, `StateEncrypted` or `StateInconsistent` | [Held](held.md) |
| `spec.deletionPolicy: Retain` | No destroy: the state, backups and durable inputs are kept, and the finalizer comes off | [Retain](retain.md) |
| Readable state | A destroy Job runs; no gate or approval applies | [Destroy](destroy-job.md) |
| The destroy succeeded | Cleanup runs and the finalizer comes off | [Cleanup](cleanup.md) |
| The destroy failed or cannot start | Retried with backoff, forever; `Retain` releases it | [Held](held.md#retain) |

## What the controller never does

- It never drops the finalizer while a state Secret may still describe
  live resources, except on an explicit `Retain`, which keeps the state.
- It never destroys against a state it cannot read.
- It never invents inputs to destroy with: the destroy renders from the
  durable inputs Secret (or, for a cluster or pool without one, the current
  inputs when they build).
- It never skips the destroy because it failed. There is no skip-destroy
  annotation, only [Retain](held.md#retain).

!!! related "See also"

    - [The Reconcile Lifecycle](../lifecycle.md#deletion-order) for the pass
      that runs all of this.
    - [Terraform State](../state.md#state-on-deletion) and [Lifecycle
      walkthroughs](../secret-management/lifecycle.md#delete) for the Secrets.
    - [Retain and Adopt](retain.md) and [Other manual
      actions](../approvals/other-manual-actions.md#retain-an-object) for
      `Retain` next to the other manual fixes.
    - [Stuck Destroy](../../operator-guide/runbooks/stuck-destroy.md),
      [Unreadable State](../../operator-guide/runbooks/state-unreadable.md#deleting-while-state-is-unreadable),
      [State Restore](../../operator-guide/runbooks/state-restore.md) and
      [clusterctl move](../../operator-guide/runbooks/move.md) for the
      commands.
