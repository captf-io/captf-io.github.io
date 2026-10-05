---
description: Pick the runbook for a symptom, alert or condition reason, from failing Jobs to lost state.
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/book-open-check
subtitle: "Start from what you see"
---

# Runbooks

If you already have a condition and a reason, [Troubleshooting by
Condition](../troubleshooting/README.md) looks it up directly.

Each runbook below covers one symptom: what it looks like, why it happens,
how to check, how to fix it, and how to confirm the fix worked. Alerts and
condition reasons are cross-references, not a substitute for reading the
page: start from whichever alert fired or condition you see, but read the
whole runbook before you act.

| Runbook | Covers | Alerts and conditions |
| --- | --- | --- |
| [Failing Jobs](job-failures.md) | A `TerraformCluster`, `TerraformMachine` or `TerraformMachinePool` whose Jobs keep failing. | [`CAPTFJobFailing`](../../reference/alerts.md#captfjobfailing), [`CAPTFNoRecentSuccess`](../../reference/alerts.md#captfnorecentsuccess); `ApplyJobSucceeded=False` and `DriftJobSucceeded=False` |
| [Stuck Destroy](stuck-destroy.md) | A `destroy` Job that cannot succeed, and how to remove the object's finalizer safely. | [`CAPTFDestroyStuck`](../../reference/alerts.md#captfdestroystuck); `ApplyJobSucceeded=False`/`DestroyFailed` |
| [Unreadable State](state-unreadable.md) | A state Secret CAPTF cannot parse. | [`CAPTFStateUnreadable`](../../reference/alerts.md#captfstateunreadable); `StateReadable=False`/`StateCorrupt`, `StateInconsistent` or `StateEncrypted` |
| [State Restore](state-restore.md) | Restoring a Terraform or OpenTofu state from a CAPTF-managed backup. | `StateReadable=False`/`StateLost`; `RestoreJobSucceeded` |
| [Stale State Lock](stale-lock.md) | Clearing a state lock left behind by a killed or evicted runner. | [`CAPTFForceUnlocks`](../../reference/alerts.md#captfforceunlocks); `StateReadable=False`/`StateLocked` |
| [Size Limits](size-limits.md) | A state or rendered inputs approaching the Secret size limit. | [`CAPTFStateNearSecretLimit`](../../reference/alerts.md#captfstatenearsecretlimit), [`CAPTFInputsNearLimit`](../../reference/alerts.md#captfinputsnearlimit); `ApplyJobSucceeded=False`/`InputsTooLarge` |
| [Slow Jobs](slow-jobs.md) | Jobs that take a long time to run, or a long time to start. | [`CAPTFJobSlow`](../../reference/alerts.md#captfjobslow), [`CAPTFJobQueueSlow`](../../reference/alerts.md#captfjobqueueslow) |
| [Reconcile Errors](reconcile-errors.md) | The controller itself failing to reconcile. | [`CAPTFReconcileErrors`](../../reference/alerts.md#captfreconcileerrors) |
| [Identities and Credentials](identity-and-credentials.md) | An object that cannot resolve or mirror its `TerraformClusterIdentity`. | `IdentityAllowed=False`, `CredentialsMirrored=False` |
| [Webhook Unavailable](webhook-unavailable.md) | Writes to a `Terraform*` object failing because the admission webhook cannot be reached. | None |
| [Total State Loss and Import](total-state-loss.md) | The state is gone with no backup: rebuild it from a workstation, or abandon and recreate the object with `import` blocks. | `StateReadable=False`/`StateLost` |
| [clusterctl move](move.md) | Moving a Cluster's `Terraform*` objects with `clusterctl move`: the procedure, what does and does not come along, and cleaning up what a move leaves behind. | None |

For how deletion works and a flowchart from a stuck object to the right
runbook, see [Deletion and
Teardown](../../concepts/deletion/README.md). For why an object has no Job
and is waiting, see [Nothing Is
Happening](../../concepts/jobs/troubleshooting.md).

Every runbook above applies to `TerraformCluster`, `TerraformMachine` and
`TerraformMachinePool` alike unless it says otherwise.

!!! related "See also"

    - [Observability](../observability.md) — the metrics and alerts these
      runbooks are reached from.
    - [Conditions reference](../../reference/conditions.md) — every condition
      type and reason named above.
