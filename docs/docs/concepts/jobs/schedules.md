---
title: "Requeue Intervals and Schedules"
description: Look up every requeue interval and schedule the CAPTF controller uses, with defaults and where each is set.
tags:
  - Reference
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/repeat
subtitle: "How often objects are requeued"
---

# Requeue Intervals and Schedules

The controller is event-driven first: a change to the object, a Job
finishing or an annotation triggers a reconcile. Requeues are the fallback
for time and for waits that have no event. This page lists every interval,
its default, and where it comes from. All of them are compiled in unless a
field or flag is named.

## Schedules (when a Job is due)

| Schedule | Default | Set by | Notes |
| --- | --- | --- | --- |
| Drift check | 30 min | `spec.drift.intervalSeconds`; else `--drift-default-interval` | `0` disables it for a cluster or machine; a pool's drift is never disabled |
| Health check | 300 s | `remediation.healthCheckIntervalSeconds` | Only while `remediation.annotateMachine` is true; otherwise health is sampled at the drift or refresh cadence |
| Membership refresh | 60 s | A pool's `membershipRefreshIntervalSeconds` | Pools only |
| Pending-health refresh | 30 s, doubling to 5 min | Compiled in | Doubles per consecutive pending reading: 30 s, 1 min, 2 min, 4 min, 5 min |
| Converging-membership refresh | 30 s | Compiled in | Fixed, not doubled: members join on the provider's schedule |
| Refresh after apply | Once, at once | Compiled in | Machines and pools; skipped when the apply's own reading is definite |

Each schedule's deadline adds a **jitter** of up to a tenth of its interval.
It is deterministic: derived from a hash of the object's UID, so the same
object always gets the same offset, and objects created together (a
`MachineDeployment`'s machines, or everything after a `clusterctl move`) do
not check in lockstep. An object with no UID gets none.

## Waits (when the controller looks again)

| Interval | Value | Used while |
| --- | --- | --- |
| `GateRequeue` | 30 s | An owner reference, a dependency, credentials, deletion order or a lease is not ready |
| `StateRequeue` | 1 min | The state is lost or unreadable, including a held deletion |
| `LagRequeue` | 5 s | The Job cache trails the API server, or a live Job holds the run lease at cleanup, or an annotation write conflicted |
| `ActiveJobRequeue` | 1 min | A Job runs; the Job watch normally wakes the reconcile first |
| `RetryBase` and `RetryMax` | 1 min, 10 min | The backoff after a failed Job; see [Retries](retries.md) |
| `RetryMax` | 10 min | An approval wait, `JobPolicyInvalid`, `InputsTooLarge`, or missing durable inputs: nothing to do until something changes, and the change wakes the reconcile |
| Stuck-Job age | 1 min | A Job younger than this is not checked for a missing per-run Secret |
| Lease grace | 1 min | A lease whose holder Job does not exist stays held this long |
| Identity re-read | 5 min | A `TerraformClusterIdentity` re-reads its credentials Secret |

## The resync

`--sync-period` (default 10 minutes) is the minimum interval at which the
informers re-enqueue every cached object. It reads the local cache, not the
API server, and sets no schedule of drift or health. It recovers a requeue
that was missed, at the cost of more reconciles. The orphan sweep ticks at
the same interval, with 10% jitter, on the leader. See [Configuration](../../operator-guide/configuration.md#sync-period-and-the-orphan-sweep).

## How they combine

A reconcile with nothing to run requeues at the **soonest** of the due
times: the next refresh, health, membership or drift deadline, whichever
applies. A reconcile that waits on something requeues at that wait's
interval. A failed op's backoff replaces its Job with a requeue for the
remaining delay, and pauses nothing else: another op still runs on its own
schedule. A waiting input change is the exception: it pauses the refresh
and drift schedule, because they would render the unapplied inputs and
report the change as drift.

| Object state | Typical next reconcile |
| --- | --- |
| Idle, healthy | The sooner of the drift and health deadlines, and any event |
| A Job running | The Job's finish event; a minute at the latest |
| Backing off after a failure | The end of the backoff |
| Waiting for a lease | 30 s |
| Waiting for an approval | The annotation, or 10 min |
| Held on the state | 1 min |

## See also

- [Choosing the operation](operations.md).
- [Drift and Health](../drift-and-health.md).
- [Configuring drift](../../user-guide/drift.md).
