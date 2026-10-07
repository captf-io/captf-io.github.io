---
title: "Prometheus Alerts Shipped with CAPTF"
description: "Look up the eleven Prometheus alerts CAPTF ships: severity, PromQL expression, what each means, likely causes and where to look first."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/siren
subtitle: "Shipped alert rules"
---

# Alerts

CAPTF ships eleven alerts as one `PrometheusRule`, `captf-alerts`, in the
`captf` rule group. They fire on the series in [Metrics](metrics.md), and
each links to a section of [Observability](../operator-guide/observability.md)
that says where to look first.

| Alert | Severity | Means |
| --- | --- | --- |
| [`CAPTFJobFailing`](#captfjobfailing) | warning | More than two Jobs of a kind and op failed in 30 minutes. |
| [`CAPTFDestroyStuck`](#captfdestroystuck) | critical | Destroy Jobs for a kind have not succeeded for 30 minutes. |
| [`CAPTFClusterDrift`](#captfclusterdrift) | warning | A `TerraformCluster` has stayed drifted for an hour. |
| [`CAPTFStateUnreadable`](#captfstateunreadable) | critical | A state Secret turned unreadable; nothing applies. |
| [`CAPTFForceUnlocks`](#captfforceunlocks) | warning | A Job force-unlocked a state lock. |
| [`CAPTFReconcileErrors`](#captfreconcileerrors) | warning | A controller keeps returning reconcile errors. |
| [`CAPTFJobSlow`](#captfjobslow) | info | The p90 Job duration is above 30 minutes. |
| [`CAPTFJobQueueSlow`](#captfjobqueueslow) | warning | The p90 wait before a Job starts is above 5 minutes. |
| [`CAPTFStateNearSecretLimit`](#captfstatenearsecretlimit) | warning | An object's state is above 900 KiB of the 1 MiB limit. |
| [`CAPTFInputsNearLimit`](#captfinputsnearlimit) | warning | An object's rendered inputs are near the size limit. |
| [`CAPTFNoRecentSuccess`](#captfnorecentsuccess) | warning | No drift check or health refresh succeeded in six hours. |

## Install the rules

`config/prometheus` in the provider repository is an opt-in kustomize
component: a metrics `Service`, a `ServiceMonitor`, the `PrometheusRule`
and the RBAC Prometheus needs to read the endpoint. It is not part of
`infrastructure-components.yaml`, so `clusterctl init` does not install it
and `clusterctl upgrade` does not update it. Build it from a checkout of the
tag you run and apply it again after each upgrade to pick up rule changes.
[Enabling the Prometheus component](../operator-guide/observability.md#enabling-the-prometheus-component)
has the steps.

The Prometheus Operator must select the rule. If your `Prometheus` object
filters `PrometheusRule` objects by label, add that label to `captf-alerts`
in an overlay. Promtool unit tests for the rules are in
`config/prometheus/tests/rules_test.yaml`; `make promtool-check` and `make
promtool-test` run them.

## Read the alerts

Two properties apply to all eleven alerts:

- The failure counters count transitions, not reconciles. They go up once
  when an object or Job newly enters the bad state, so `increase(...) > 0`
  means something newly broke, not that it is still broken. A counter alert
  resolves after its window even if the cause remains.
- Only `CAPTFClusterDrift`, `CAPTFStateNearSecretLimit`,
  `CAPTFInputsNearLimit` and `CAPTFNoRecentSuccess` carry `namespace` and
  `name` labels. The others aggregate by `kind` with `op` or `reason`
  (`CAPTFReconcileErrors` by `controller`), so you find the object through
  its [conditions](conditions.md), as each runbook says.

Blocked and plan-changed Jobs, which wait for an approval, are not failures
and no alert counts them. See [Approvals](../concepts/approvals/README.md).

## Tune thresholds

Change a rule in an overlay instead of editing the shipped file, so an
upgrade does not discard the change. A kustomize patch on `captf-alerts`
replaces a rule's `expr` or `for`. Rules are a list, so the patch targets
the rule by index; confirm the index against the built output first:

```yaml title="kustomization.yaml"
patches:
  - target:
      kind: PrometheusRule
      name: captf-alerts
    patch: |-
      - op: replace
        path: /spec/groups/0/rules/6/expr   # (1)!
        value: histogram_quantile(0.9, sum by (le, kind, op) (rate(captf_job_duration_seconds_bucket{result=~"succeeded|failed"}[1h]))) > 3600
```

1. Rule 6 is `CAPTFJobSlow`: rules are numbered from 0 in the order of the
   table above. This example raises its threshold from 30 to 60 minutes.

Two thresholds mirror real limits, so raise them with care.
`CAPTFStateNearSecretLimit` warns at 900 KiB because one Secret holds at
most 1 MiB, and `CAPTFInputsNearLimit` warns at 900000 bytes because no Job
starts above 1000000. To silence an alert for one object, use an
Alertmanager silence on its labels instead of loosening the rule for all.

## CAPTFJobFailing

**Severity:** warning. **For:** none, so it fires on the first evaluation
that matches.

```promql
sum by (kind, op) (increase(captf_jobs_total{result=~"failed|deadline"}[30m])) > 2
```

More than two Jobs of one kind and op failed or hit their deadline within 30
minutes. Blocked, plan-changed and interrupted Jobs do not count.

Likely causes:

- A module error that every object of the kind hits, such as a bad input, an
  API quota or an expired credential.
- A cloud outage or throttling.
- A deadline set too short for the module.

Find the objects with `ApplyJobSucceeded=False` or `DriftJobSucceeded=False`
and read `status.lastRun` and the Job logs. Runbook:
[`CAPTFJobFailing`](../operator-guide/observability.md#captfjobfailing),
then [Failing Jobs](../operator-guide/runbooks/job-failures.md).

## CAPTFDestroyStuck

**Severity:** critical. **For:** 30m.

```promql
sum by (kind) (increase(captf_jobs_total{op="destroy",result!="succeeded"}[30m])) > 0
```

Destroy Jobs for a kind have failed, hit their deadline or been interrupted,
with none succeeding, for 30 minutes. The objects keep their finalizer and
their state, so nothing is orphaned yet, but the deletion does not finish.

Likely causes:

- Cloud resources that cannot be deleted because something still depends
  on them, such as a load balancer or a network interface.
- Credentials that expired or were removed before the destroy ran.
- An identity that no longer allows the namespace.

Runbook:
[`CAPTFDestroyStuck`](../operator-guide/observability.md#captfdestroystuck),
then [Stuck Destroy](../operator-guide/runbooks/stuck-destroy.md).

## CAPTFClusterDrift

**Severity:** warning. **For:** 1h.

```promql
captf_drift_detected{kind="TerraformCluster"} == 1
```

A `TerraformCluster`'s last drift check found changes, and it has stayed
that way for an hour. The alert carries the cluster's `namespace` and `name`.

Likely causes:

- `drift.action: Report`: CAPTF reports and waits for you to decide.
- `drift.action: Remediate`: the remediation apply keeps failing. Read
  `ApplyJobSucceeded`.
- Someone changed the infrastructure outside CAPTF.

Runbook:
[`CAPTFClusterDrift`](../operator-guide/observability.md#captfclusterdrift),
then [Drift](../user-guide/drift.md). Machines and pools can drift too, but
no shipped alert covers them; query `captf_drift_detected` for those kinds.

## CAPTFStateUnreadable

**Severity:** critical. **For:** none.

```promql
sum by (kind, reason) (increase(captf_state_read_errors_total[15m])) > 0
```

A state Secret turned unreadable in the last 15 minutes. The `reason` label
says how: `inconsistent`, `encrypted`, `corrupt`, `lost` or `locked`.
Nothing applies to the object until its state reads again.

Likely causes:

- `lost`: the state Secret was deleted, or a management-cluster restore
  left an object without its state.
- `corrupt` or `inconsistent`: a partial write or an edit by hand.
- `encrypted`: the state is encrypted and CAPTF has no key for it.
- `locked`: a holder other than this object's runner holds the lock.

Find the object with `StateReadable=False` and read its reason and message.
Runbook:
[`CAPTFStateUnreadable`](../operator-guide/observability.md#captfstateunreadable),
then [Unreadable State](../operator-guide/runbooks/state-unreadable.md).

## CAPTFForceUnlocks

**Severity:** warning. **For:** none.

```promql
sum by (kind) (increase(captf_lock_force_unlocks_total[1h])) > 0
```

A Job force-unlocked a state lock whose holder pod no longer existed. The
unlock is safe by design, since the holder is gone, but the previous Job died
without releasing the lock.

Likely causes:

- The runner pod was evicted, OOM-killed or lost with its node.
- A node drain or spot preemption stopped a Job mid-apply.

Look for `ForceUnlocked` and `JobInterrupted` events on the object, and find
why the previous Job died. Runbook:
[`CAPTFForceUnlocks`](../operator-guide/observability.md#captfforceunlocks),
then [Stale State Lock](../operator-guide/runbooks/stale-lock.md).

## CAPTFReconcileErrors

**Severity:** warning. **For:** 10m.

```promql
sum by (controller) (rate(controller_runtime_reconcile_errors_total{controller=~"terraform.*"}[10m])) > 0.1
```

One of the CAPTF controllers returned more than 0.1 reconcile errors per
second, sustained for 10 minutes. This is a controller-runtime metric, not a
`captf_*` series; the `controller` label is the controller's name, such as
`terraformcluster`.

Likely causes:

- The API server is unavailable or throttling the manager.
- A webhook or a CRD the controller depends on is missing.
- A bug that fails every reconcile of one kind.

Read the manager logs for the failing kind. Runbook:
[`CAPTFReconcileErrors`](../operator-guide/observability.md#captfreconcileerrors),
then [Reconcile Errors](../operator-guide/runbooks/reconcile-errors.md).

## CAPTFJobSlow

**Severity:** info. **For:** 30m.

```promql
histogram_quantile(0.9, sum by (le, kind, op) (rate(captf_job_duration_seconds_bucket{result=~"succeeded|failed"}[1h]))) > 1800
```

The 90th percentile of Job duration for a kind and op has been above 30
minutes, measured over the last hour, for 30 minutes. Compare it with the
Jobs' `activeDeadlineSeconds`: a Job near its deadline is about to fail.

Likely causes:

- A module that creates slow resources, such as a managed Kubernetes control
  plane or a database.
- A slow step: find it with `captf_job_step_duration_seconds`.
- Cloud API throttling.

Runbook:
[`CAPTFJobSlow`](../operator-guide/observability.md#captfjobslow), then
[Slow Jobs](../operator-guide/runbooks/slow-jobs.md).

## CAPTFJobQueueSlow

**Severity:** warning. **For:** 10m.

```promql
histogram_quantile(0.9, sum by (le, kind, op) (rate(captf_job_queue_seconds_bucket[10m]))) > 300
```

The 90th percentile of the time from a Job's creation to its source
container starting has been above five minutes, for 10 minutes. That time is
scheduling, image pulls and the runner's init copy; the module has not
started yet.

Likely causes:

- No node capacity or a namespace quota blocks the runner pods.
- A slow or failing pull of the module image.
- Node autoscaling that is slow to add nodes.

Look for `Pending` runner pods and their events. Runbook:
[`CAPTFJobQueueSlow`](../operator-guide/observability.md#captfjobqueueslow),
then [Slow Jobs](../operator-guide/runbooks/slow-jobs.md).

## CAPTFStateNearSecretLimit

**Severity:** warning. **For:** 15m.

```promql
captf_state_bytes > 900 * 1024
```

An object's compressed state is above 900 KiB for 15 minutes. The
Kubernetes state backend keeps one Secret per state, and a Secret holds at
most 1 MiB, so the next apply that crosses the limit fails to save its
state. The alert carries the object's `namespace` and `name`.

Likely causes:

- A module that manages too many resources in one state. Check the count with
  `captf_state_resources`.
- Large attributes stored in state.

Split the module across kinds or reduce what it stores. Runbook:
[`CAPTFStateNearSecretLimit`](../operator-guide/observability.md#captfstatenearsecretlimit),
then [Size Limits](../operator-guide/runbooks/size-limits.md).

## CAPTFInputsNearLimit

**Severity:** warning. **For:** 15m.

```promql
captf_inputs_bytes > 900000
```

The rendered `main.tf.json` and `terraform.tfvars.json` for an object are
above 900000 bytes for 15 minutes. Above 1000000 bytes no Job starts, and
`ApplyJobSucceeded` reports `InputsTooLarge`. The alert carries the object's
`namespace` and `name`.

Likely causes:

- A very large `spec` field, such as an inline list or a long user-data
  string.
- Many machines or node groups in one object.

Runbook:
[`CAPTFInputsNearLimit`](../operator-guide/observability.md#captfinputsnearlimit),
then [Size Limits](../operator-guide/runbooks/size-limits.md). See also
[Inputs](../concepts/inputs.md).

## CAPTFNoRecentSuccess

**Severity:** warning. **For:** 30m.

```promql
time() - captf_last_success_timestamp_seconds{op=~"drift|refresh"} > 6 * 3600
```

An object's scheduled drift check or health refresh has not succeeded in six
hours, so drift and health go unobserved. The `op` label says which. The
series exists only while the op is scheduled: not while the object is
deleting or paused, has drift checks off, or (for `refresh`) samples no
health.

The rule assumes intervals well under six hours. If you set a drift or
refresh interval near or above six hours, raise the threshold.

Likely causes:

- The scheduled Jobs fail. Read `DriftJobSucceeded` and `status.lastRun`.
- The Jobs never start: see `CAPTFJobQueueSlow` and the run lease events.

Runbook:
[`CAPTFNoRecentSuccess`](../operator-guide/observability.md#captfnorecentsuccess),
then [Failing Jobs](../operator-guide/runbooks/job-failures.md).
