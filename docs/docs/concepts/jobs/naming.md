---
description: Learn how deterministic Job names make creation idempotent, how attempts count, and how finished Jobs are kept and pruned.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/tag
subtitle: "How Jobs are named and kept"
---

# Job Names, Attempts and History

A Job's name is a function of what it does, so the controller can create
the same Job twice without starting two. This page covers the name, the
attempt number, what happens when the Job already exists, and how finished
Jobs are kept and pruned.

## The name

```text
captf-<kindshort>-<name>-<op>-a<attempt>-<hash6>
```

| Part | Value |
| --- | --- |
| `kindshort` | `c` for a `TerraformCluster`, `m` for a `TerraformMachine`, `mp` for a `TerraformMachinePool` |
| `name` | The object's name; replaced by the first 16 hex characters of its SHA-256 when the whole name would pass 57 characters |
| `op` | `apply`, `plan`, `destroy`, `refresh`, `drift` or `restore` |
| `attempt` | One more than the highest attempt among the retained Jobs of the same op, whatever their outcome |
| `hash6` | The first six hex characters of SHA-256 over the inputs hash, the op, the attempt and a tick |

!!! note "The 57-character cap is deliberate"

    The Job controller names pods `<job>-<5 characters>`, and the kubelet
    truncates a pod's hostname at 63. At 57 the full pod name is the
    hostname Terraform records as the lock holder, so [stale-lock
    detection](state-lock.md) can find the pod by name.

### What goes into the hash

The inputs hash and the tick differ by op, so that a repeated op gets a new
name only when it should:

| Op | Inputs hash | Tick |
| --- | --- | --- |
| `apply`, `plan` | The hash of the current rendered inputs | none |
| A drift-remediation `apply` | The same | `remediate/<last drift check>` |
| `refresh` | The hash recorded in state | The time of the last successful refresh |
| `drift` | The hash recorded in state | The time of the last successful drift check |
| `restore` | The backup's hash | `restore/<backup name>` |
| `destroy` | The hash recorded in state | none |

A refresh or drift retry therefore has the same name until one of them
succeeds, and the next one has a new name. A remediation apply of unchanged
inputs would otherwise collide with the retained first apply, so it carries
its own tick.

## Attempts

The attempt number is `max(attempt of retained Jobs of this op) + 1`, not
the count of failures. Counting failures would reuse a name twice over:
once pruning removed older failures (a1 to a5 failed, the newest three kept,
a count of three would reuse a4), and again with a retained success when an
apply repeats the same inputs. Taking the highest retained attempt makes a
new name never equal a retained one.

The attempt is also a label (`captf.infrastructure.cluster.x-k8s.io/attempt`)
next to `.../op`, the owner kind and name, the cluster name and
`captf.io/managed=true`, on the Job and its pods.

## Adopting a Job that exists

The controller creates the Job, then its per-run Secret, then records
`status.activeJob`. A crash between any two, or a pass whose Job cache has
not yet seen the Job, repeats the sequence with the same name:

1. Creating the Job returns `AlreadyExists`. The controller reads the
   existing Job and carries on with it, so no second Job starts.
2. The per-run Secret, owned by the Job, is created if missing. One that
   already belongs to the same Job (by UID) is left as is, because the name
   embeds the inputs hash and so the content is identical. One owned by a
   different Job of the same name, left over from an earlier pruned Job whose
   garbage collection is pending, is deleted and recreated; adopting it
   would let that collection delete it under the new pod.

Any other create error is returned. A **rejected** create (invalid,
forbidden, unauthorized, bad request, too large or namespace gone) proves no
Job exists, so the controller [gives the leases back](leases.md#release);
a timeout or server error proves nothing and the leases are kept.

A Job that can never start is deleted. If an active Job is more than a
minute old, its per-run Secret is missing and every pod is still `Pending`,
the controller deletes it and emits `StuckJobDeleted`; the next pass starts
the operation again with its Secret. This also runs on a paused object, so
a Job that can never start does not hold `clusterctl move`.

## The Job itself

- `backoffLimit: 0`: a failed pod is a failed Job. The controller retries,
  with its own backoff.
- `activeDeadlineSeconds`: the [deadline](deadlines.md).
- Pod `restartPolicy: Never`, a termination grace period of 600 seconds, and
  no TTL: finished Jobs stay until pruned, because the controller derives
  backoff, digest pinning and conditions from them.
- The pod mounts the per-run Secret (`captf-run-<job name>`) that holds the
  rendered files. It is deleted when the Job finishes, so rendered inputs do
  not outlive the run; see [Inside the Job](../secret-management/job.md).

## Annotations the controller writes

| Annotation | On | Meaning |
| --- | --- | --- |
| `captf.io/bookkept` | Any finished Job | Its pod was read, its Secret deleted and its completion counted |
| `captf.io/interrupted` | A bookkept Job | The runner was stopped from outside, not by the deadline |
| `captf.io/destructive-plan-blocked` | An apply | The runner stopped before a plan that deletes or replaces |
| `captf.io/plan-changed` | An apply | The approved plan no longer matched |
| `captf.io/plan-unreadable` | A plan | It succeeded without a readable plan, and counts as a failure |
| `captf.io/drift-remediation` | An apply | The apply remediates drift |
| `captf.io/approved-plan` | An apply under `Manual` | The plan hash it had to plan again |

The marks exist because a bookkept Job's pod is not read again: the result
lives on in the annotation, the conditions and `status.lastRun`.

## History

After bookkeeping, the controller prunes finished Jobs beyond
`successfulJobsHistoryLimit` and `failedJobsHistoryLimit` (default 3 each),
**per object and per op**, oldest first. Refresh and drift history never
pushes out an apply's. Two Jobs of an op stay whatever the limits say:

- its newest success, so that an older failure cannot pose as the op's
  latest outcome in `ApplyJobSucceeded`;
- its newest failure while no newer success exists, since backoff and the
  remediation cap count it.

Running Jobs are never touched. Pruned Jobs take their pods with them
(background propagation). Because pruning caps the number of retained
failures at the limit, the limit also bounds the retry count; see [Retries
and backoff](retries.md).

!!! related "See also"

    - [The Reconcile Lifecycle: Job names and history](../lifecycle.md#job-names-and-history).
    - [Tuning Jobs: history limits](../../user-guide/job-tuning.md#history-limits).
