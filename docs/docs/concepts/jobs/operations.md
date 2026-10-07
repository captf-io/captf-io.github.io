---
title: "Choosing the Terraform Operation"
description: Read the priority order CAPTF uses to pick the next operation, the reasons it reports, and the refresh and drift schedule.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/split
subtitle: "How apply or destroy is picked"
---

# Choosing the Operation

When no Job of the object is active, one pure function decides what runs
next: `DecideOp`. It reads a snapshot (the Jobs, the state, the inputs hash,
the annotations and the clock), returns an operation or a wait, and has no
side effects. This page gives its order, the reasons it reports, and the
exceptions. The shorter version is in [The Reconcile
Lifecycle](../lifecycle.md#choosing-the-next-operation); this is the full
list.

## The order

The first rule that applies decides the pass.

| # | Condition | Decision | Reason |
| --- | --- | --- | --- |
| 0 | A Job is active | Nothing; requeue in a minute | `JobActive` |
| 1 | `captf.io/restore-state` names a complete, unconsumed backup, and the object is not deleting, or its deletion is held | `restore` | `RestoreRequested` |
| 2 | Deleting, state lost or unreadable | Wait one minute | `DeletionHeld` |
| 3 | Deleting, no state | Drop the finalizer | `DeletingWithoutState` |
| 4 | Deleting | `destroy` | `Deleting` |
| 5 | No state | `apply` | `NoState` |
| 6 | State without an inputs hash | `apply` | `StateWithoutInputsHash` |
| 7 | Mutable kind, and the current inputs hash differs from state's | `apply` | `InputsChanged` |
| 8 | Mutable kind, and the newest apply failed | `apply` | `LastApplyFailed` |
| 9 | Drift found, action `Remediate`, and fewer than the failed-limit remediations failed since the last drift check | `apply` | `DriftRemediation` |
| 10 | None of the above | The schedule below | |

An apply reason from 5 to 9 can still be turned into something else:

- **Under `applyPolicy: Manual`** (a `TerraformCluster` only), every apply
  reason but `NoState` becomes the plan flow: a `plan` Job when no plan of
  the current inputs is recorded, the apply with the approved plan hash once
  the approval annotation names it (or the plan changes nothing), else a
  wait. See [Approvals and Gates](../approvals/manual-approval.md).
- **Otherwise**, an apply whose newest attempt was blocked before a
  destructive plan, for the same inputs hash, waits for the approval
  annotation or new inputs. See [The destructive-plan
  guard](../approvals/destructive-guard.md).
- **Backoff** replaces any `ActionJob` of an op that failed recently with a
  wait; see [Retries and backoff](retries.md).

!!! note "An approval wait is bounded"

    The wait for an approval never requeues for longer than ten minutes,
    and approvals and input changes trigger a reconcile on their own.

### Why immutable kinds still retry

Rules 7 and 8 apply to mutable kinds (a `TerraformCluster` and a
`TerraformMachinePool`). A `TerraformMachine` is immutable: its inputs never
change after creation, so it has no `InputsChanged` and no `LastApplyFailed`.
It retries a failed apply through rules 5 and 6 instead: the state carries an
inputs hash only after a successful apply, so a partly written state still
reads as `StateWithoutInputsHash`, and the apply runs again after its
backoff.

## The schedule

With no apply to run, the reconcile checks these in order and stops at the
first that is due. Each interval has a deterministic jitter of up to a tenth
of the interval, derived from the object's UID.

| # | Check | Operation | Reason |
| --- | --- | --- | --- |
| 1 | A successful apply not yet followed by a refresh, for kinds that ask for one (machine, pool) | `refresh` | `RefreshAfterApply` |
| 2 | A pool's membership is converging | `refresh` every 30 s, fixed | `MembershipConverging` |
| 3 | Health reads pending | `refresh` after 30 s, doubling to 5 min | `HealthPending` |
| 4 | The membership interval (pools) | `refresh` | `MembershipRefreshDue` |
| 5 | The health-check interval (when remediation is on) | `refresh` | `HealthCheckDue` |
| 6 | The drift interval | `drift` | `DriftDue` |
| 7 | Otherwise | Requeue at the soonest deadline | `UpToDate` |

Notes:

- Rule 1 is skipped when the apply's own output reading is definite (neither
  pending nor unknown): the reading stands in for the refresh and
  `status.lastRefresh` advances to the apply's finish.
- Rules 3 and 2 are exclusive: while converging, the fixed 30 seconds
  replaces the doubling pending delay.
- The base of a periodic check is its own last run, else the last
  successful apply (so the first check comes one interval after
  provisioning), else the object's creation time. After a `clusterctl move`
  there is no history, so the creation time is the base and the jitter keeps
  moved objects from checking in lockstep.
- A drift or refresh Job runs against the current inputs for a mutable kind,
  and the durable ones for an immutable kind. A waiting input change pauses
  the whole schedule, the way a backoff does: a refresh would otherwise
  render the unapplied inputs and report the waiting change as drift.

## What each op reads and writes

| Op | Inputs it runs against | Writes the durable Secret |
| --- | --- | --- |
| `apply`, `plan` | The current inputs | `apply` only |
| `refresh`, `drift` | Current (mutable) or durable (immutable) | No |
| `destroy` | The durable inputs | No |
| `restore` | None: a backend-only root and the backup chunks | No |

Only `apply` and `plan` run the spec's image as written. Every other op runs
the digest pinned after the last successful apply, when one exists; without
one it falls back to the spec reference and emits `DigestUnknown`.

!!! related "See also"

    - [Drift and Health](../drift-and-health.md) for what the drift and refresh
      results mean.
    - [Machine Pools](../../user-guide/machine-pools.md) for membership
      convergence.
