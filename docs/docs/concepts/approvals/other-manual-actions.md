---
title: "Other Manual Actions on CAPTF Objects"
description: "The manual actions besides plan approval: restore state, abandon an object, fix a Job policy, release a foreign lock and opt a ServiceAccount in."
tags:
  - Operators
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/pointer
subtitle: "Other annotations you can set"
---

# Other Manual Actions

Not every wait is an approval. Some conditions need a person to do
something that is not "approve the plan". This page lists them, with what
CAPTF does and where the procedure is.

## Restore a state

`captf.io/restore-state=<serial>` asks for a backup to be pushed back as the
state. A value that is not a serial, or that names no complete backup, sets
`RestoreJobSucceeded=False`/`RestoreBackupNotFound` and starts nothing. A
restore takes precedence over apply, drift and refresh, waits on the run
lease and, for a cluster, the cluster write lease, and is never gated by an
approval. See [Backups and restore](../secret-management/backups.md#restore)
and the [state restore runbook](../../operator-guide/runbooks/state-restore.md).

A failed restore is not retried for the same serial, and does not count
toward backoff. To retry it: remove the annotation, wait until
`status.lastRestoredSerial` clears, then set the annotation again. Deleting
the failed Job does not retry.

## Abandon an object

`captf.io/abandon-infrastructure=<metadata.uid>` releases a deleting
object whose destroy cannot run: held on missing or unreadable state, a
failed last destroy, a missing durable inputs Secret, or an identity or
credentials the destroy cannot start with. The value must equal the UID;
anything else is ignored.

!!! danger "Abandoning leaves the infrastructure running, untracked"

    The infrastructure keeps running, untracked. An object whose destroy can
    run is destroyed as usual, even with the annotation set.

See the [stuck destroy
runbook](../../operator-guide/runbooks/stuck-destroy.md#abandon-instead).

## Fix an inconsistent Job policy

`ApplyJobSucceeded=False`/`JobPolicyInvalid` means the merged Job policy
has a `lockTimeoutSeconds` that is not below `activeDeadlineSeconds`, counting
inherited and built-in defaults (300 and 3600 seconds). No Job other than a
destroy starts until you change one of the two values. See
[Tuning Jobs](../../user-guide/job-tuning.md#deadlines-and-lock-waits).

## Release a foreign state lock

`StateReadable=False`/`StateLocked` means the state lock is held by
something that is not one of the object's own runner pods, for example a
workstation running `terraform state rm`. The controller does not unlock
it: every Job for the object waits `lockTimeoutSeconds` for it and fails. A
lock held by the object's own pod that is now gone is unlocked by the next
Job on its own. See the [stale lock
runbook](../../operator-guide/runbooks/stale-lock.md).

## Opt a ServiceAccount in

A Job runs as the ServiceAccount `captf-runner`. If you set another
ServiceAccount in `spec.jobs.serviceAccountName`, it must exist and carry the
label `captf.io/runner=true`. Otherwise `RunnerRBACReady` is
`False`/`ServiceAccountNotOptedIn`, the ServiceAccount is not bound to the
runner role, no Job starts and the controller retries every 30 seconds.
Add the label, or use the default. See [RBAC](../../operator-guide/rbac.md).

!!! related "See also"

    - [Runbooks](../../operator-guide/runbooks/README.md).
    - [Operating the gates](operating.md).
    - [Deletion and Teardown](../deletion/README.md) for the whole delete path.
