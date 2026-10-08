---
description: Understand the two clocks on a Job, activeDeadlineSeconds and lockTimeoutSeconds, and the check that keeps them consistent.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/alarm-clock
subtitle: "Time limits on Jobs and locks"
---

# Deadlines and Lock Timeouts

A Job runs against two clocks. `activeDeadlineSeconds` bounds the whole Job.
`lockTimeoutSeconds` bounds how long one runner step waits for the Terraform
state lock. They are set per object in `spec.jobs`, inherited by machines
and pools from their cluster's `spec.defaults.jobs` field by field, and the
second must stay below the first.

| Setting | Default | Range | Enforced by |
| --- | --- | --- | --- |
| `activeDeadlineSeconds` | 3600 | 1 to 86400 | Kubernetes, on the Job |
| `lockTimeoutSeconds` | 300 | 0 to 3600 | Terraform or OpenTofu, as `-lock-timeout` |

Neither is a manager flag. See [Tuning
Jobs](../../user-guide/job-tuning.md#deadlines-and-lock-waits) for how to
set them.

## The deadline

Kubernetes counts `activeDeadlineSeconds` from the Job's start. When it
passes, the pod is sent SIGTERM and then, after the grace period, SIGKILL.
The Job sets a termination grace period of **600 seconds** so that a
SIGTERM is not a SIGKILL in 30 seconds: the runner interrupts the runtime,
which finishes the provider calls in flight (a VM being created), writes the
state and releases the lock. The runner's own stop timeout is the grace
period less a 30 second margin, which leaves time to write its result.

A deadline kill is a failure, with three condition reasons by op:

| Op | Condition | Reason |
| --- | --- | --- |
| `apply`, `plan`, `destroy` | `ApplyJobSucceeded=False` | `JobDeadlineExceeded` |
| `refresh`, `drift` | `DriftJobSucceeded=False` | `DriftJobDeadlineExceeded` |
| `restore` | `RestoreJobSucceeded=False` | `RestoreFailed` |

!!! warning "A deadline kill counts toward backoff"

    It **counts toward backoff** like any other failure, even though the
    runner reports the interruption: see
    [Retries](retries.md#counting-failures).

An image that cannot be pulled also ends on the deadline, but its more
specific reason, `ImagePullFailed`, is checked first. CAPTF reads it from
the pod. If the deadline has already deleted the pod, it reads the reason
from the `captf.io/image-pull-failed` annotation, which it puts on a Job
whose module image has not pulled for 2 minutes.

!!! tip "Raise the deadline for a slow module"

    Raising it also lengthens the [lease
    backstop](leases.md#grace-and-backstop), because a lease is held up to
    the holder's deadline plus 15 minutes.

## The lock timeout

`lockTimeoutSeconds` is passed to the runner as `--lock-timeout`, and the
runner adds `-lock-timeout=<n>s` to the steps that take or wait for the
state lock:

| Step | Gets `-lock-timeout` |
| --- | --- |
| `init` | Yes: it succeeds while the lock is held |
| `apply`, `plan`, `destroy` | Yes |
| `apply -refresh-only` (refresh, and the first step of drift) | Yes |
| `plan -refresh=false` (the second step of drift) | Yes |
| `state push` (restore) | Yes |
| `force-unlock`, `validate`, `show -json`, `state list` | No |

A step that cannot get the lock within the timeout fails, and the Job
fails with it. That counts toward backoff. The lock itself is the
Terraform state lock, which is a different mechanism from CAPTF's leases:
see [The state lock and stale locks](state-lock.md).

A timeout of 0 means do not wait: fail at once on a held lock.

## The merged-policy check

The deadline must be longer than the lock wait, or a Job could reach its
deadline while still waiting for a lock. The admission webhook checks one
policy at a time against the built-in default of the field the policy does
not set. It cannot see the field-wise merge of a machine's policy over its
cluster's defaults, so the controller checks the **merged** policy again
before it starts a Job:

```text
lockTimeoutSeconds (default 300) must be less than
activeDeadlineSeconds (default 3600)
```

When it fails, the object reports `ApplyJobSucceeded=False`/`JobPolicyInvalid`
with a message naming both effective values and whether each is configured or
the built-in default, no Job starts, and the reconcile requeues in ten
minutes (a change to the object triggers it sooner). The message is on
`ApplyJobSucceeded` whichever op was due: a refresh or drift that cannot
start reports there too.

Two exceptions:

- **A destroy never waits on this check**, so a teardown cannot wedge on a
  policy error. See [The destroy Job](../deletion/destroy-job.md).
- **A restore does not run it either**: the restore path starts its Job
  without the check.

To fix it, lower `lockTimeoutSeconds` or raise `activeDeadlineSeconds` in
the policy that sets it, or in the cluster's `spec.defaults.jobs`.

!!! related "See also"

    - [Slow Jobs](../../operator-guide/runbooks/slow-jobs.md).
    - [Job Environment](../../reference/environment.md) for the Job's exact
      arguments.
