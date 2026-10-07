---
title: "Job Retries and Backoff in CAPTF"
description: Learn what counts as a failed Job, how the retry delay grows, and which waits deliberately do not back off.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/rotate-cw
subtitle: "How failed Jobs are retried"
---

# Retries and Backoff

CAPTF retries a failed operation forever, with a delay that grows to a cap.
Nothing limits the number of attempts; what the failure limit bounds is the
delay and the remediation retries. This page defines what counts as a
failure, the delay, and the cases that deliberately do not back off.

## Counting failures

For each operation separately, the controller walks the object's finished
Jobs newest first and counts the failed ones until it meets a success of
that same op. A failing drift check therefore never delays an apply.

| Outcome of a finished Job | Counts as a failure |
| --- | --- |
| Failed: a step failed, the image would not pull, the image broke the contract | Yes |
| Killed by `activeDeadlineSeconds` | **Yes**, even if the runner reported itself interrupted |
| Stopped from outside: a drain, an eviction, a Job deletion | No (`JobInterrupted`) |
| An apply the runner blocked before a destructive plan | No (`DestructivePlanBlocked`) |
| An approved apply whose plan no longer matched | No (`PlanChanged`) |
| A plan Job that succeeded but whose plan could not be read | Yes: the next plan backs off instead of looping |
| A lease wait | No: no Job existed |

Two details explain the table:

- **Interrupted versus the deadline.** On a deadline, Kubernetes sends the
  runner SIGTERM, as it does for a drain, and the runner may report the run
  as `interrupted`. The controller still counts it, because a step that
  always hangs would otherwise retry at once forever and never reach the
  cap. Only an interruption that is not a deadline kill is free.
- **Blocked and plan-changed.** Both stopped before changing anything, and
  both are waiting for a person, not a timer. They count toward no backoff
  and no retry number; `DecideOp` waits for the approval or for new inputs
  instead (see [Choosing the operation](operations.md)).

## The delay

The delay after `n` consecutive failures of an op is

```text
min(1m × 2^(n-1), 10m)
```

counted from when the newest failed Job finished. Once `n` reaches the
failed-Jobs history limit, it is the 10-minute cap straight away. The limit
is `spec.jobs.failedJobsHistoryLimit`, default 3, and at least 1 (a limit
of 0 counts like 1, because pruning always keeps the newest unresolved
failure). The timing is compiled in: one minute base, ten minute cap.

| Limit | Delay after failure 1, 2, 3, 4, 5 |
| --- | --- |
| 0 or 1 | 10m, 10m, 10m, 10m, 10m |
| 3 (default) | 1m, 2m, 10m, 10m, 10m |
| 5 | 1m, 2m, 4m, 8m, 10m |

Pruning keeps at most the limit's worth of failures, so `n` cannot exceed
it; reaching the limit means "at least that many". A success of the op
resets the count. During the delay the decision is a requeue with the
reason `<reason>Backoff` (for example `InputsChangedBackoff`); there is no
way to skip it by hand.

## Retries by reason

| What failed | What retries it | Delay |
| --- | --- | --- |
| An apply of a mutable kind | `LastApplyFailed`, until an apply succeeds | Backoff |
| An apply of a `TerraformMachine` | `NoState` or `StateWithoutInputsHash` (state has no inputs hash until an apply succeeds) | Backoff |
| A drift remediation apply | The remediation cap, below | Backoff |
| An apply Job deleted while it ran (cluster, pool) | An apply of the current inputs stays due; see [below](#an-apply-job-deleted-while-it-ran) | Backoff |
| `refresh`, `drift` | The schedule: still due, so due again | Backoff |
| `destroy` | `Deleting`, forever | Backoff; see [Destroy](../deletion/destroy-job.md) |
| `plan` | The plan flow | Backoff |
| `restore` | Nothing: not retried for the same serial | None, see [below](#restore) |

### The remediation cap

An apply that remediates drift (`captf.io/drift-remediation` on the Job) is
not retried as an unconverged apply: `LastApplyFailed` ignores it. Instead,
`DecideOp` counts the failed apply Jobs that finished after the last
successful drift check, stopping at an apply success. Remediation starts only
while that count is below the failed limit (at least 1). At the limit, the
drift stays pending (`DriftDetected` stays `True`) and no more remediation
runs until the next successful drift check resets the count. Blocked and
plan-changed applies do not count. See [Drift](../../user-guide/drift.md).

### An apply Job deleted while it ran

If an apply Job of a `TerraformCluster` or `TerraformMachinePool` is deleted
while it runs, it never finishes and bookkeeping never reads its result, but it
may have applied part of its change. CAPTF confirms with live reads (the Job is
`NotFound` and the object's live `status.activeJob` still names it) and records
`captf.io/interrupted-apply=<job>` on the durable inputs Secret. An apply of
the current inputs then stays due, even when the inputs equal the state's, and
is guarded where the destructive guard applies. `ApplyJobSucceeded` is
`False`/`ApplyFailed`: `Job <name>: disappeared while it ran and may have applied
part of its change; an apply of the current inputs is due`. It clears when an
apply started afterwards succeeds. A stuck Job that CAPTF deleted itself, and a
`TerraformMachine`, record nothing. See [Machine
pools](../approvals/destructive-guard.md#an-apply-job-deleted-while-it-ran).

### Restore

!!! warning "A failed restore is not retried for the same serial"

    A failed restore is not retried for the same backup serial and counts
    toward no backoff. To try again, remove the annotation, wait for
    `status.lastRestoredSerial` to clear, and set it again. See [Other
    manual actions](../approvals/other-manual-actions.md#restore-a-state).

## What does not back off

These end the pass with a requeue, not a failure:

| Wait | Requeue |
| --- | --- |
| A lease (`WaitingForRunLease`, `WaitingForClusterOperation`, `WaitingForMachineOperations`) | 30 s |
| Credentials, dependencies or an owner not ready | 30 s |
| An unreadable or lost state | 1 min |
| A Job still running | 1 min fallback; the Job watch wakes the reconcile sooner |
| The Job cache behind the API server | 5 s |
| An approval for a blocked apply or a plan | At most 10 min; an annotation wakes the reconcile |
| `JobPolicyInvalid`, `InputsTooLarge`, missing durable inputs | 10 min; a change wakes the reconcile |

## Metrics and events

Each finished Job is counted once. `captf_job_attempts` records its retry
number (one plus the earlier failed Jobs of the op since the last success,
not counting blocked and plan-changed ones). The events are `JobFailed`,
`JobInterrupted`, `JobDeadlineExceeded` and `DestructivePlanBlocked`, each
once per Job. See [Metrics](../../reference/metrics.md) and
[Events](../../reference/events.md).

!!! related "See also"

    - [Failing Jobs](../../operator-guide/runbooks/job-failures.md).
    - [The Reconcile Lifecycle: retry backoff](../lifecycle.md#retry-backoff).
