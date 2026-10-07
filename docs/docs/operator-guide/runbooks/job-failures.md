---
title: "Runbook: Failing CAPTF Jobs"
description: Diagnose a failing apply, destroy, drift check or refresh Job from the object's conditions, status and pod logs, and fix the cause.
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/circle-x
subtitle: "Find why a Job failed"
---

# Failing Jobs

This page helps you diagnose a Job that failed, or an object whose apply,
destroy, drift check or health refresh keeps failing. It covers the
`CAPTFJobFailing` and `CAPTFNoRecentSuccess` alerts and reading a failure
directly from an object's status, for a `TerraformCluster`,
`TerraformMachine` or `TerraformMachinePool`.

!!! info "Before you begin"

    - `kubectl` access to read the failing object and its Job's pod logs, in
      its namespace, on the management cluster.
    - The object's kind, namespace and name. `CAPTFJobFailing` carries only
      `kind` and `op`, so find the object through its conditions (step 1);
      `CAPTFNoRecentSuccess` already carries `namespace` and `name`.

## 1. Find the failing objects

```sh
kubectl get terraformclusters,terraformmachines,terraformmachinepools -A -o json \
  | jq -r '.items[] | select(any(.status.conditions[]?; (.type=="ApplyJobSucceeded" or .type=="DriftJobSucceeded") and .status=="False")) | "\(.kind) \(.metadata.namespace)/\(.metadata.name)"'
```

`ApplyJobSucceeded` covers apply and destroy; `DriftJobSucceeded` covers
drift checks and health refreshes. `CAPTFNoRecentSuccess` fires when a
scheduled drift check or refresh has not succeeded for six hours, which
usually means one of these Jobs is failing repeatedly rather than missing
once.

## 2. Read the condition's reason

The reason on `ApplyJobSucceeded` or `DriftJobSucceeded` says where to
look next; see [Conditions](../../reference/conditions.md) for the full
list of reasons each condition can carry. The ones that matter here:

| Reason | What it means | Go to |
| --- | --- | --- |
| `ApplyFailed`, `DestroyFailed` or `DriftJobFailed` | A Job ran and its runtime failed partway through. `status.lastRun` carries the detail. | Step 3 |
| `ImagePullFailed` | A container stayed in `ErrImagePull` or `ImagePullBackOff` until the Job's deadline. No step ever ran, so `status.lastRun` carries nothing useful. | [Image pull failures](#image-pull-failures) |
| `ImageInvalid` | The image does not follow the module contract. | [Image layout errors](#image-layout-errors) |
| `JobDeadlineExceeded` | The Job's pod ran past `activeDeadlineSeconds` without finishing. | [Deadline exceeded](#deadline-exceeded) |
| `DestructivePlanBlocked` or `PlanChanged` | Not a failure: an apply stopped on purpose, waiting for an approval, and does not count toward `CAPTFJobFailing`. | [Plan Approval](../../user-guide/plan-approval.md) |

## 3. Read status.lastRun for a completed run

When the runner actually started and produced a result — every reason
above except `ImagePullFailed` and a `JobDeadlineExceeded` that hit before
any step ran — `status.lastRun.error.kind` classifies what happened. See
the full field list in [Last run](../../reference/resources/common-fields.md#last-run).

- `step`: a runtime command failed. `error.step` names it — usually
  `init`, `validate`, `plan`, `show-json`, `apply`, `apply-refresh-only` or
  `destroy`; occasionally `force-unlock` (retrying past a stale lock left
  by a previous run; see the [stale state lock runbook](stale-lock.md)) or
  `prepare` (the runner's own environment setup, before any runtime
  command ran) — and `error.summary` gives the runner's curated one-line
  reason, at most 512 bytes — the module's or the cloud provider's own
  error, never raw output. For a failed `apply` or `destroy`,
  `error.resources` lists the failing resources as `<address>: <summary>`
  (at most 10), and the `ApplyJobSucceeded` condition's message names the
  first, so `kubectl get -o jsonpath='{.status.lastRun.error.resources}'`
  often answers which resource failed. Read the rest from the Job's pod
  logs (step 4).
- `image-layout`: the image does not follow the module contract; the same
  cause as `ImageInvalid` above. See
  [Image layout errors](#image-layout-errors).
- `interrupted`: the runner was sent `SIGTERM` before it could finish — a
  node drain, an eviction, the Job being deleted, or the deadline. It is
  retried without counting toward backoff; see [Retry backoff](#retry-backoff).
- `blocked` or `plan-changed`: see
  [Plan Approval](../../user-guide/plan-approval.md).

`status.lastRun.steps` lists every step the runner completed, with its
exit code and duration — useful for finding a slow step even when the run
as a whole succeeded.

## 4. Read the Job's pod logs

```sh
kubectl get job -n <ns> <job-name>
kubectl logs -n <ns> job/<job-name> -c source
```

`<job-name>` is `status.lastRun.job` for a finished run, or
`status.activeJob.name` for one still running. The `source` container
runs the pinned image and the module; a separate init container only
copies the runner binary into it and rarely fails on its own (that
failure surfaces as an image pull failure on the manager's `--runner-image`
instead, a cluster-wide problem rather than one specific to this object).
`status.lastRun.error.summary` is a curated, size-limited copy of the
failing step's output, not the raw log, because the object's status is
readable by anyone who can `get` it — the full log is only in
`kubectl logs`.

By default the newest three failed Jobs of each operation are kept
(`spec.jobs.failedJobsHistoryLimit`; see
[Tuning Jobs](../../user-guide/job-tuning.md)), so the pod and its logs
are usually still there for a fresh alert.
`kubectl events --for <kind>/<name> -n <ns> --types=Warning` also carries a
curated summary of each failure as a `JobFailed` or `StepFailed` event,
even after the Job itself is pruned.

## Image pull failures

`ImagePullFailed` means a container was stuck pulling its image — never that
the module ran and failed. For an apply or plan it is reported at the Job's
deadline; for a destroy, refresh, drift or restore it can appear earlier, once
the last image CAPTF can try is stuck (see [Destroy, refresh, drift and
restore](#destroy-refresh-drift-and-restore-fall-back-to-another-image)). Two images can be
at fault:

- the `source` container's image, `spec.source.image` — check for a typo,
  a missing pull secret, or a tag that was deleted from the registry;
- the runner init container's image, the manager's `--runner-image`
  (defaults to the manager's own image) — a cluster-wide problem, not
  specific to this object.

```sh
kubectl get pods -n <ns> -l batch.kubernetes.io/job-name=<job-name>
kubectl describe pod -n <ns> <pod-name>
```

The `Events` section names the image and the pull error
(`ErrImagePull`/`ImagePullBackOff`). Fix the image reference or the pull
credentials (`spec.jobs.imagePullSecrets`; see
[Tuning Jobs](../../user-guide/job-tuning.md)), then let the next
reconcile retry — no manual retrigger is needed.

### Destroy, refresh, drift and restore fall back to another image

Apply and plan run `spec.source.image`. The other operations run the **pinned
digest** of the record they render, and a registry can garbage collect a
digest that no tag points to. So when a destroy, refresh, drift or restore Job
has had no ready pod for 2 minutes and its `source` container is stuck in
`ErrImagePull`, `ImagePullBackOff` or `InvalidImageName`, CAPTF falls back:

1. It tries the images in order: the pinned `repo@digest`, then the image tag
   the record ran (`captf.io/image`), then `spec.source.image`.
2. It records the image that failed in the `captf.io/unpullable-images`
   annotation on the durable inputs Secret (`captf-inputs-*`, at most 3
   entries), clears `status.activeJob`, deletes the stuck Job and emits the
   Warning `ImagePullFallback`: "Could not pull X (reason): deleted destroy Job
   J; retrying destroy with Y". The next pass starts the operation again with
   the same Job name on the next image. A deleted Job counts as no failure, so
   there is no backoff. The new Job carries `captf.io/image-fallbacks` with
   the images still to try, and its `JobCreated` note says it falls back.
3. A successful apply re-pins the digest and clears the list.

On the **last** image (or with no durable inputs Secret to record on), the Job
is left to run to its deadline and the operation's condition is set to
`False`/`ImagePullFailed` at once: `ApplyJobSucceeded` for a destroy,
`DriftJobSucceeded` for a refresh or drift, `RestoreJobSucceeded` for a
restore. The message names the image and the exits:

- push the image back, or let the Job's pull secrets reach it;
- for a mutable kind, set `spec.source.image` to an image that can be pulled
  (it is honored live, also for the running Job's fallback decision);
- for a destroy, set `spec.deletionPolicy: Retain`.

An init container (the runner image) that cannot pull never falls back. To keep
digests pullable, exclude them from the registry's lifecycle rules.

## Image layout errors

`ImageInvalid` (`status.lastRun.error.kind: image-layout`) means the
runner started but the image itself does not follow the module contract:
it is missing the module directory the contract requires, or its entry
point is not executable. See
[Image Contract](../../module-author/image-contract.md) for the layout an
image must follow. Republish the image and point `spec.source.image` at
the new tag or digest to try again.

!!! warning "No retry fixes an image layout error"

    This is a problem with the image, not with the object's spec or a transient failure.


## Deadline exceeded

`JobDeadlineExceeded` means the Job's pod ran past
`spec.jobs.activeDeadlineSeconds` (one hour unless set) without
finishing. Kubernetes sends the runner `SIGTERM`; it gets most of the
Job's termination grace period to finish an in-flight provider call and
write state before being killed, so infrastructure created before the
deadline is not lost even though the Job is marked failed. Common causes:

- a module that is simply slow relative to its deadline — raise
  `spec.jobs.activeDeadlineSeconds`; see
  [Tuning Jobs](../../user-guide/job-tuning.md);
- a state lock wait: the first step that locks the state (`plan`,
  `apply`, `apply-refresh-only` or `destroy` — `init` never takes the
  lock) waits at most `spec.jobs.lockTimeoutSeconds` (five minutes unless
  set) for it before failing on its own — well inside the default
  deadline, so a lock wait alone should rarely be the cause; see
  [Slow Jobs](slow-jobs.md) and the
  [stale state lock runbook](stale-lock.md) if it is;
- a provider call that never returns — the module's or the cloud API's
  problem; the log up to where it stopped is the only record when the
  runner is killed before it can write a result.

## Retry backoff

A Job that failed for `step`, `image-layout` or a pull failure counts
toward that operation's retry backoff; a `blocked` or `plan-changed` Job
never counts, since it waits for an approval instead of a timer. See
[The Reconcile Lifecycle](../../concepts/lifecycle.md#retry-backoff) for
the delay itself. A deadline kill always counts, even when the runner
caught its `SIGTERM` in time and reported itself `interrupted`
(`status.lastRun.error.kind: interrupted`): a step that always hangs must
reach the retry cap. Only an interruption that is not a deadline kill, such
as a drain or an eviction, retries on the next reconcile with no wait. See
[Retries and backoff](../../concepts/jobs/retries.md#counting-failures).

!!! warning "There is no way to skip a real backoff by hand"

    Retrying immediately against an unresolved cause (a bad image, a still-held lock) only fails again the same way.


## Confirm it worked

!!! success ""

    ```sh
    kubectl get <kind> -n <ns> <name> -o json \
      | jq '.status.conditions[] | select(.type=="ApplyJobSucceeded" or .type=="DriftJobSucceeded")'
    ```

    The condition returns to `status: "True"`, and the next
    `status.lastRun.error` is empty.

!!! related "See also"

    - [Approvals and Gates](../../concepts/approvals/operating.md) for the
      conditions and events of a waiting plan or a blocked apply.
    - [Slow Jobs](slow-jobs.md) — a Job that runs but takes far longer than
      expected.
    - [Stale State Lock](stale-lock.md) — a lock held long enough to fail a
      Job on its own.
    - [Plan Approval](../../user-guide/plan-approval.md) — approving a
      blocked or changed plan.
    - [Tuning Jobs](../../user-guide/job-tuning.md) — deadlines, lock
      timeouts, history limits and pull secrets.
