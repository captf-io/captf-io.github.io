---
description: What runs when a deleting object has readable state, what does not gate the destroy, what it waits on, and how it fails and retries.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "Steven Crothers"
icon: lucide/bomb
subtitle: "The Job that tears down infra"
---

# The Destroy Job

Once a deleting object has readable state, no running Job and (for a
cluster) no dependents, the controller decides a `destroy` Job. Every other
decision a live object makes is skipped: a deleting object never applies,
refreshes or checks drift.

## What is not in the way

- **No approval.** `applyPolicy: Manual` and the destructive-plan guard
  belong to applies. A destroy is never gated, on any kind. See
  [Approvals and Gates](../approvals/README.md#the-two-gates).
- **No policy check.** The merged Job policy check that refuses a
  `lockTimeoutSeconds` not below `activeDeadlineSeconds`
  (`JobPolicyInvalid`) is skipped for a destroy, so a teardown never wedges
  on it. See [Tuning Jobs](../../user-guide/job-tuning.md#deadlines-and-lock-waits).
- **No input gates.** A deleting object builds no inputs and ignores
  `DependenciesReady`. The destroy renders from the **durable inputs
  Secret** `captf-inputs-<kindshort>-<name>`, the files of the last
  successful apply. A `TerraformCluster` or `TerraformMachinePool` whose
  Secret is gone falls back to building its current inputs when they build;
  a `TerraformMachine` never does, since its Machine and bootstrap Secret
  are usually gone by then. See [The durable inputs Secret is
  missing](../../operator-guide/runbooks/stuck-destroy.md#the-durable-inputs-secret-is-missing).
- **The pinned image.** For a machine, the destroy runs the image and the
  identity recorded in the durable Secret, not the current
  spec, so changing a template cannot change how an existing machine is torn
  down.

## What is in the way

A destroy still takes the same leases as an apply:

- The object's **run lease**: one Job at a time per object.
- The **cluster operation gate**, when it is on (the default): a
  `TerraformCluster` destroy takes the Cluster's write lease and waits for
  any machine or pool apply or destroy in flight
  (`WaitingForMachineOperations`); a machine's destroy waits while a
  `TerraformCluster` apply is running (`WaitingForClusterOperation`).

The wait shows as `ApplyJobSucceeded=Unknown` with the wait reason, counts
toward no backoff, and re-checks every 30 seconds. See [Leases and the
operation gate](../lifecycle.md#run-leases-and-the-cluster-operation-gate).

## Credentials, only when needed

A live object prepares its runner credentials (the identity check, the
credential mirror and the runner ServiceAccount and RoleBinding) on every
pass. A deleting object does it only when a Job is about to start
(`deletionCredentials`). A deletion that needs no Job, such as an object
that never applied or one released by abandon, therefore never waits on
credentials. Why this matters in a terminating namespace is on [that
page](namespaces.md).

If the credentials are not ready the destroy waits, and the pass reports
the first condition that is not `True`:

- The identity no longer allows the namespace, or is gone:
  `ApplyJobSucceeded=False`/`IdentityNotAllowed`, message `Destroy waits
  until the identity allows this namespace again`.
- Otherwise the `Deleting` condition's message reads `The destroy Job waits
  for its credentials: <condition> is <status> (<reason>)`, naming
  `IdentityAllowed`, `CredentialsMirrored` or `RunnerRBACReady`.

Both retry every 30 seconds. Both are among the cases the [abandon
annotation](held.md#abandon) releases.

## Results and retries

| Outcome | `ApplyJobSucceeded` | What follows |
| --- | --- | --- |
| Destroy succeeded | `True`/`DestroySucceeded` | [Cleanup](cleanup.md), finalizer off |
| Destroy failed | `False`/`DestroyFailed` | Retry with backoff, forever |
| Killed at the deadline | `False`/`JobDeadlineExceeded` | Retry with backoff, forever |
| Image could not be pulled | `False`/`ImagePullFailed` | Retry with backoff |
| Image breaks the contract | `False`/`ImageInvalid` | Retry with backoff |
| Stopped from outside (drain, eviction, Job delete) | `JobInterrupted` event | Retry at once, no backoff |

The backoff is the one every operation uses: one minute after the first
failure, doubling to a ten-minute cap, and the cap from the point the
object's retained failed Jobs reach `failedJobsHistoryLimit` (default 3,
counted as at least 1). A destroy that the **deadline killed counts
as a failure** even though the runner reports it interrupted: a step that
always hangs must reach the cap. See [Failing Jobs](../../operator-guide/runbooks/job-failures.md).

!!! warning "There is no retry limit"

    A destroy that can never succeed stays at
    `ApplyJobSucceeded=False`/`DestroyFailed` and `Ready=False`, and
    [`CAPTFDestroyStuck`](../../reference/alerts.md#captfdestroystuck)
    fires. The way out is to fix the cause, to [abandon](held.md#abandon),
    or to clean up and [strip the finalizer](manual-finalizer.md).

A failed destroy may have destroyed part of the infrastructure. The next
attempt runs against the state the failed one left, so it continues rather
than starting over.

!!! related "See also"

    - [Held deletions](held.md).
    - [Stuck Destroy](../../operator-guide/runbooks/stuck-destroy.md).
    - [Reference: ApplyJobSucceeded](../../reference/conditions.md#applyjobsucceeded).
