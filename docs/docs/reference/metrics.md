---
title: "Prometheus Metrics Exposed by CAPTF"
description: "Look up every Prometheus metric the CAPTF manager exposes: type, labels and their values, unit and meaning, grouped by topic with example queries."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/chart-column
subtitle: "Every Prometheus metric"
hide:
  - toc
---

# Metrics

The manager exposes `captf_*` series that describe Jobs, reconcile
decisions, state, drift and health. The [shipped alerts](alerts.md) are
written on them, and the examples below build on the same series. Jump to:
[Jobs](#jobs), [reconcile decisions](#reconcile-decisions),
[state and inputs](#state-and-inputs), [drift and health](#drift-and-health),
[locks, leases and approvals](#locks-leases-and-approvals),
[identity and images](#identity-and-images), [build info](#build-info),
[controller-runtime series](#controller-runtime-and-other-series).

## Where they are served

The metrics are on the manager's diagnostics endpoint, HTTPS on `:8443`
(`--diagnostics-address`), at `/metrics`. Requests are authenticated with a
`TokenReview` and authorized with a `SubjectAccessReview` for `get` on the
non-resource URL `/metrics`; a request without a token gets `401`.
`--insecure-diagnostics` serves plain HTTP with no checks and is for local
development only. See
[Observability](../operator-guide/observability.md#the-diagnostics-endpoint)
and [Manager flags](manager-flags.md#diagnostics-and-tls-capi).

The opt-in `config/prometheus` component ships a `Service`
(`captf-controller-manager-metrics`, port `8443`, named `metrics`), a
`ServiceMonitor` that scrapes it over HTTPS with the Prometheus
ServiceAccount's token, and the RBAC that token needs. It is not part of the
release manifest; see
[Enabling the Prometheus component](../operator-guide/observability.md#enabling-the-prometheus-component).

## Conventions

- Metrics are declared with `k8s.io/component-base/metrics` at stability
  level `ALPHA`, so names and labels can change between releases. On the
  wire, each `HELP` string starts with `[ALPHA]`.
- Durations are in seconds, sizes in bytes and timestamps in Unix seconds.
- Labels are bounded enums: `kind`, `op`, `result`, `reason`, `step`,
  `action` and `error_kind`. Only the eight per-object gauges carry
  `namespace` and `name`, and CAPTF removes a gauge's series when its object
  is deleted, so they do not accumulate.
- `kind` is the CAPTF kind: `TerraformCluster`, `TerraformMachine` or
  `TerraformMachinePool`. `op` is the operation: `apply`, `destroy`,
  `refresh`, `drift`, `plan` or `restore`.
- Failure counters count transitions, not reconciles. They go up once when
  an object or Job newly enters a bad state, so use `increase()` to ask
  whether something newly broke.

## Jobs

Every runner Job is observed when it completes. A Job is one `op` for one
object; see [Jobs](../concepts/jobs/README.md).

| Metric | Type | Labels | Unit | Measures |
| --- | --- | --- | --- | --- |
| `captf_jobs_total` | counter | `kind`, `op`, `result` | Jobs | Jobs completed, by result. |
| `captf_job_duration_seconds` | histogram | `kind`, `op`, `result` | seconds | Wall time of a completed Job, start to finish. |
| `captf_job_step_duration_seconds` | histogram | `kind`, `op`, `step` | seconds | Wall time of each runner step of a completed Job. |
| `captf_job_queue_seconds` | histogram | `kind`, `op` | seconds | Time from a Job's creation to its source container's start. |
| `captf_job_errors_total` | counter | `kind`, `op`, `error_kind`, `step` | Jobs | Jobs that did not succeed, by error kind and failing step. |
| `captf_jobs_active` | gauge | `kind`, `op` | Jobs | Jobs running now, counted from the Job cache at scrape time. |
| `captf_job_attempts` | histogram | `kind`, `op` | attempts | Retry number of a Job that succeeded. |
| `captf_resources_changed_total` | counter | `kind`, `op`, `action` | resources | Resources an apply or destroy Job changed. |

Label values:

| Label | Values |
| --- | --- |
| `result` | `succeeded`, `failed`, `deadline`, `interrupted` (stopped from outside: a drain, eviction or deletion), `blocked` (a guarded apply stopped before a plan that deletes or replaces resources, awaiting approval), `plan_changed` (an approved apply planned other changes and stopped). |
| `step` | `init`, `force-unlock`, `validate`, `plan`, `show-json`, `apply`, `apply-refresh-only`, `destroy`, `state-push`, `state-list`, `prepare`; anything else is `other`. On `captf_job_errors_total`, `none` when no step failed. |
| `error_kind` | `step`, `image-layout`, `interrupted`, `blocked`, `plan-changed`; `deadline` or `unknown` when the Job left no result. |
| `action` | `add`, `change`, `destroy`, `import`. |

Notes on how each series is built:

- `op="plan"` is a plan Job under `applyPolicy: Manual`; it applies
  nothing.
- `blocked` and `plan_changed` are not failures. Each is reported by its own
  condition and event, and `CAPTFJobFailing` does not count them.
- `captf_job_duration_seconds` buckets run from 15 seconds to 2 hours, and
  `captf_job_step_duration_seconds` from 1 second to 2 hours.
- `captf_job_queue_seconds` has buckets from 5 seconds to 30 minutes, with
  300 seconds, the `CAPTFJobQueueSlow` threshold, as a boundary. CAPTF does
  not record it when the pod reports no start.
- `captf_job_attempts` is 1 plus the failed Jobs of the op since it last
  succeeded. Interrupted Jobs do not count.
- `captf_resources_changed_total` comes from the runtime's final summary
  line.

```promql
# p95 apply duration by kind over the last day, for Jobs that ran their course
histogram_quantile(0.95, sum by (le, kind) (
  rate(captf_job_duration_seconds_bucket{op="apply",result=~"succeeded|failed"}[1d])))

# Failures by error kind and failing step, last hour
sum by (kind, op, error_kind, step) (increase(captf_job_errors_total[1h])) > 0
```

```promql
# Slowest runner steps (p90)
topk(5, histogram_quantile(0.9, sum by (le, kind, op, step) (
  rate(captf_job_step_duration_seconds_bucket[6h]))))

# Resources destroyed by applies in the last 24 hours
sum by (kind) (increase(captf_resources_changed_total{op="apply",action="destroy"}[24h]))
```

## Reconcile decisions

| Metric | Type | Labels | Unit | Measures |
| --- | --- | --- | --- | --- |
| `captf_reconcile_op_decisions_total` | counter | `kind`, `op`, `reason` | decisions | What a reconcile decided to run, and why. |

`op` is `none` when the reconcile decided to run nothing. `reason` says why:
for example `NoState`, `InputsChanged`, `DriftDue`, `DriftRemediation` or
`Deleting` start a Job, while `UpToDate`, `JobActive`,
`LastApplyFailedBackoff` or `DeletingBackoff` start nothing.

```promql
# Why applies started in the last day
sum by (kind, reason) (increase(captf_reconcile_op_decisions_total{op="apply"}[1d]))
```

## State and inputs

The per-object gauges hold the last value the manager read. See [State](../concepts/state.md).

| Metric | Type | Labels | Unit | Measures |
| --- | --- | --- | --- | --- |
| `captf_state_read_errors_total` | counter | `kind`, `reason` | reads | State reads that turned unreadable. |
| `captf_state_resources` | gauge | `kind`, `namespace`, `name` | resources | Managed resources, not data sources, in the object's state. |
| `captf_state_bytes` | gauge | `kind`, `namespace`, `name` | bytes | Compressed state size summed over its Secrets. |
| `captf_inputs_bytes` | gauge | `kind`, `namespace`, `name` | bytes | Size of the rendered `main.tf.json` and `terraform.tfvars.json`. |
| `captf_state_backups_total` | counter | `kind`, `result` | backups | State backups, by result. |
| `captf_state_restores_total` | counter | `kind`, `result` | restores | State restores requested with `captf.io/restore-state`. |
| `captf_outputs_invalid_total` | counter | `kind`, `reason` | outputs | Outputs that turned invalid against the module contract. |
| `captf_inputs_hash_changes_total` | counter | `kind` | applies | Applies started because the inputs of a mutable kind changed. |

Label values:

| Label | Values |
| --- | --- |
| `state_read_errors_total{reason}` | `inconsistent`, `encrypted`, `corrupt` (an unsupported state version counts as corrupt), `lost` (a provisioned object's state is gone), `locked` (held by something other than this object's runner). |
| `state_backups_total{result}` | `taken` (a new serial copied into `captf-state-backup-*` Secrets), `pruned` (a backup beyond `--state-backups` deleted), `skipped` (a new serial not backed up: encrypted, unreadable or oversized state, or a failed copy). |
| `state_restores_total{result}` | `succeeded`, `failed` (a restore Job finished), `not_found` (the annotation names no backup). |

The Kubernetes backend holds at most 1 MiB per Secret, and no Job starts
when the inputs exceed 1000000 bytes. [`CAPTFStateNearSecretLimit`](alerts.md#captfstatenearsecretlimit)
and [`CAPTFInputsNearLimit`](alerts.md#captfinputsnearlimit) warn at 900 KiB
and 900000 bytes.

```promql
# The ten largest states, as a share of one Secret's 1 MiB
topk(10, captf_state_bytes / (1024 * 1024))

# Objects with unreadable state in the last 15 minutes, by reason
sum by (kind, reason) (increase(captf_state_read_errors_total[15m])) > 0
```

## Drift and health

See [Drift and health](../concepts/drift-and-health.md). The gauges use the
condition value: `1` for True, `0` for False and `-1` for Unknown.

| Metric | Type | Labels | Unit | Measures |
| --- | --- | --- | --- | --- |
| `captf_ready` | gauge | `kind`, `namespace`, `name` | 1, 0 or -1 | The `Ready` condition. |
| `captf_infrastructure_healthy` | gauge | `kind`, `namespace`, `name` | 1, 0 or -1 | The `InfrastructureHealthy` condition. |
| `captf_drift_detected` | gauge | `kind`, `namespace`, `name` | 1 or 0 | 1 while `DriftDetected` is True, else 0. |
| `captf_drift_resources_total` | counter | `kind`, `action` | resources | Resources a drift Job that found drift would `add`, `change` or `destroy`. |
| `captf_last_success_timestamp_seconds` | gauge | `kind`, `namespace`, `name`, `op` | Unix seconds | When the newest successful Job of an op finished. |
| `captf_unhealthy_samples` | gauge | `namespace`, `name` | samples | A `TerraformMachine`'s consecutive unhealthy health samples (`status.unhealthySamples`). |
| `captf_remediation_requests_total` | counter | `action` | requests | `cluster.x-k8s.io/remediate-machine` annotations set on (`requested`) or removed from (`withdrawn`) a `Machine`. |

`captf_last_success_timestamp_seconds` exports `drift` and `refresh` only
while that op is scheduled: not while the object is deleting or paused, and
only with a drift interval or health checks set. A series that goes missing
is therefore not a failure by itself.

```promql
# Objects that are not Ready
captf_ready == 0

# Objects whose drift check or health refresh is overdue, in hours
(time() - captf_last_success_timestamp_seconds{op=~"drift|refresh"}) / 3600 > 6
```

## Locks, leases and approvals

| Metric | Type | Labels | Unit | Measures |
| --- | --- | --- | --- | --- |
| `captf_lock_force_unlocks_total` | counter | `kind` | unlocks | Stale state locks force-unlocked. |
| `captf_lease_waits_total` | counter | `kind`, `reason` | waits | Operations that started waiting for a run lease, once per wait. |
| `captf_plan_approvals_total` | counter | `kind`, `result` | approvals | Plans approved with `captf.io/approve-plan` under `applyPolicy: Manual`. |
| `captf_destructive_plan_approvals_consumed_total` | counter | `kind` | approvals | Destructive-plan approvals removed after the approved apply succeeded. |

Label values:

| Label | Values |
| --- | --- |
| `lease_waits_total{reason}` | `run_lease` (another live Job of the object holds it), `cluster_operation` (a machine's apply or destroy waits for its `TerraformCluster`'s), `machine_operations` (a cluster's apply or destroy waits for its machines'). |
| `plan_approvals_total{result}` | `approved` (the apply of the approved plan succeeded and the annotation was removed), `changed` (the approved apply planned other changes and stopped; the new plan waits for approval). |

See [Leases](../concepts/jobs/leases.md) and
[Approvals](../concepts/approvals/README.md).

```promql
# Where operations wait, by reason
sum by (kind, reason) (increase(captf_lease_waits_total[1h]))
```

## Identity and images

| Metric | Type | Labels | Unit | Measures |
| --- | --- | --- | --- | --- |
| `captf_identity_denied_total` | counter | `reason` | refusals | Identity refusals: `notfound` or `namespace`. |
| `captf_image_inspect_errors_total` | counter | `reason` | errors | Registry or image-label failures while resolving template capacity. |

```promql
# Identity refusals in the last day
sum by (reason) (increase(captf_identity_denied_total[1d]))
```

## Build info

| Metric | Type | Labels | Unit | Measures |
| --- | --- | --- | --- | --- |
| `captf_build_info` | gauge | `version`, `commit`, `contract` | constant 1 | The manager's version, commit and module contract. |

```promql
captf_build_info
```

## Controller-runtime and other series

The same endpoint serves series that CAPTF does not define:

| Family | What it covers |
| --- | --- |
| `controller_runtime_*` | Reconcile counts, errors, time and active workers per controller. `controller_runtime_reconcile_errors_total` backs [`CAPTFReconcileErrors`](alerts.md#captfreconcileerrors). |
| `workqueue_*` | Queue depth, latency and retries per controller. |
| `rest_client_*` | Client requests to the API server, by code and verb. |
| `go_*`, `process_*` | Go runtime and process statistics. |
| `kubernetes_feature_enabled` | Feature gates, from component-base. |

CAPTF merges its registry with the controller-runtime defaults and the
component-base registry, and drops component-base's own `go_*` and
`process_*` families because controller-runtime already serves them.

```promql
# Reconcile errors per second by controller
sum by (controller) (rate(controller_runtime_reconcile_errors_total{controller=~"terraform.*"}[10m]))
```
