---
title: "Troubleshooting Objects With No Job"
description: Find what a CAPTF object with no Job is waiting on, from its conditions and events, and what to do about each wait.
tags:
  - Troubleshooting
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/hourglass
subtitle: "Read the wait reason"
---

# Nothing Is Happening

An object that is not changing and has no Job is waiting on something. The
controller always records what: a condition, an event, or a requeue
reason in its log. Find it in this order.

```sh
# The conditions that carry a wait, and Ready's own message
kubectl get <kind> -n <ns> <name> \
  -o jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\t"}{.message}{"\n"}{end}'
# The Jobs of the object, newest last
kubectl get jobs -n <ns> -l captf.infrastructure.cluster.x-k8s.io/owner-name=<name> --sort-by=.metadata.creationTimestamp
# The events
kubectl events -n <ns> --for <kind>/<name>
```

Then match what you see.

## By wait reason

| You see | Meaning | What to do |
| --- | --- | --- |
| `ApplyJobSucceeded=Unknown`/`WaitingForRunLease`, message names a Job | A live Job, or another manager, holds the object's run lease or the Cluster's write lease | Wait; it clears when the holder finishes. If the holder Job does not exist, the lease frees after a minute. Never delete a Lease by hand. See [Leases](leases.md) |
| `…/WaitingForClusterOperation` on a machine or pool | Its `TerraformCluster` applies, destroys or restores | Wait. The cluster Job is named in the message; look at that Job if it is slow |
| `…/WaitingForMachineOperations` on a cluster | Machine and pool applies, destroys or restores of the Cluster are in flight; new ones wait behind the cluster | Wait; the message names up to five of them |
| The same reasons on `DriftJobSucceeded` or `RestoreJobSucceeded` | The op that waits is a refresh, a drift check or a restore | The same |
| `ApplyJobSucceeded=Unknown`/`PlanAwaitingApproval` | Manual approval of a plan | [Plan Approval](../../user-guide/plan-approval.md) |
| `ApplyJobSucceeded=False`/`DestructivePlanBlocked` | The destructive-plan guard stopped an apply | [Destructive-plan guard](../approvals/destructive-guard.md) |
| `ApplyJobSucceeded=False`/`JobPolicyInvalid` | The merged `lockTimeoutSeconds` is not below `activeDeadlineSeconds` | Fix one of them; see [Deadlines](deadlines.md#the-merged-policy-check) |
| `ApplyJobSucceeded=False`/`ApplyFailed`, message `Job <name>: disappeared while it ran…` | An apply Job was deleted while it ran; an apply of the current inputs is due and guarded | Wait for it, or approve its plan if it waits. See [Retries](retries.md#an-apply-job-deleted-while-it-ran) |
| `ApplyJobSucceeded=False`/`ApplyFailed`, `JobDeadlineExceeded`, `ImagePullFailed`, `ImageInvalid`, `InputsTooLarge` | The last Job failed and the op is in backoff, or nothing can start until the cause is fixed | [Failing Jobs](../../operator-guide/runbooks/job-failures.md), [Size Limits](../../operator-guide/runbooks/size-limits.md). The delay is in [Retries](retries.md) |
| `StateReadable=False`/`StateLost`, `StateCorrupt`, `StateEncrypted`, `StateInconsistent` | No Job runs until the state reads | [Unreadable State](../../operator-guide/runbooks/state-unreadable.md), [State Restore](../../operator-guide/runbooks/state-restore.md) |
| `StateReadable=False`/`StateLocked` | A foreign holder has the state lock; every Job waits `lockTimeoutSeconds` and fails | [Stale State Lock](../../operator-guide/runbooks/stale-lock.md); see [The state lock](state-lock.md) |
| `DependenciesReady=False` or `Unknown` | An owner, bootstrap data, cluster exports or a variables source is not there yet | [Reconcile Errors](../../operator-guide/runbooks/reconcile-errors.md) |
| `IdentityAllowed`, `CredentialsMirrored` or `RunnerRBACReady` not `True` | The credentials for the Job are not ready; retried every 30 seconds | [Identities and Credentials](../../operator-guide/runbooks/identity-and-credentials.md) |
| `Paused=True` | The object or its Cluster is paused: bookkeeping only, no Job starts | Unpause |
| `RestoreJobSucceeded=False`/`RestoreBackupNotFound` | The restore annotation names no complete backup | [State Restore](../../operator-guide/runbooks/state-restore.md) |
| `DeletionBlocked=True` | A cluster waits for its machines and pools | [Deletion order](../deletion/order.md#the-cluster-waits-for-its-machines) |

## No condition explains it

| Situation | What it is | What to do |
| --- | --- | --- |
| A Job exists and runs for a long time | The Job is the work; the object waits on it | Look at its pod logs; see [Slow Jobs](../../operator-guide/runbooks/slow-jobs.md). It ends at `activeDeadlineSeconds` |
| A Job exists, its pod is `Pending` | The image, the volume or the schedule | A Job older than a minute whose per-run Secret is missing and whose pods are all `Pending` is deleted and started again by the controller |
| Idle, healthy, `Ready=True` and no Job | Nothing is due: the next drift, health or membership deadline | Wait, or see [Schedules](schedules.md) for when the next check is due |
| The object looks right but is stale | The Job cache lags, or the manager is not the leader | [Cache lag](cache-lag.md); check the manager pods and [Leader election](leader-election.md) |
| No condition changes and no events | The manager is not reconciling this object | [Reconcile Errors](../../operator-guide/runbooks/reconcile-errors.md); check `--watch-filter` and `--namespace` |
| Writes to the object fail | The webhook is unavailable | [Webhook Unavailable](../../operator-guide/runbooks/webhook-unavailable.md) |

## What not to do

!!! danger "Do not delete a Lease or a failed Job to unstick a wait"

    - **Do not delete a Lease** to unstick a wait. Leases are taken over by the
      controller once the holder finishes, does not exist after a minute, or is
      past its deadline plus the backstop.
    - **Do not delete a failed Job** to skip a backoff. It is the record the
      retry and the remediation cap count from.
    - **Do not edit the object's annotations** to clear `block-move`; the
      controller clears it when no Job is active.


!!! related "See also"

    - [Runbooks](../../operator-guide/runbooks/README.md).
    - [Conditions reference](../../reference/conditions.md).
