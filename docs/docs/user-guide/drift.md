---
description: Set how often CAPTF checks for drift, whether it reports or remediates, and read the results.
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "September 29, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-09-29"
authors:
  - "The CAPTF Authors"
icon: lucide/scan-search
subtitle: "Turn on drift checks"
---

# Drift

CAPTF periodically refreshes and plans a `TerraformCluster`,
`TerraformMachine` or `TerraformMachinePool` to check whether the
infrastructure still matches its module's inputs. This page covers how to
set the check interval and action for each kind, disable checks where
that is possible, read the results, and remediate what a check finds. See
[Drift and Health](../concepts/drift-and-health.md) for how the checks
work and how they feed the object's health.

!!! info "Before you begin"

    - A provisioned `TerraformCluster`, `TerraformMachine` or
      `TerraformMachinePool`.
    - `kubectl` access to edit the object and read its status.

## Set the drift interval

Every kind checks for drift on a timer: `spec.drift.intervalSeconds`. Left
unset, it uses the manager's `--drift-default-interval` flag (30 minutes
by default; see [Manager Flags](../reference/manager-flags.md)).

A `TerraformMachine` and a `TerraformMachinePool` inherit an interval from
the owning `TerraformCluster`'s `spec.defaults.drift.intervalSeconds`
when they set none of their own:

=== "TerraformCluster"

    ```yaml
    apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
    kind: TerraformCluster
    spec:
      drift:
        intervalSeconds: 900 # (1)!
    ```

    1. The cluster's own interval.

=== "Default for machines and pools"

    ```yaml
    apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
    kind: TerraformCluster
    spec:
      defaults:
        drift:
          intervalSeconds: 1800 # (1)!
    ```

    1. Inherited by every `TerraformMachine` and `TerraformMachinePool`
       that sets no interval of its own.

=== "TerraformMachine"

    ```yaml
    apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
    kind: TerraformMachine
    spec:
      drift:
        intervalSeconds: 900
    ```

=== "TerraformMachinePool"

    ```yaml
    apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
    kind: TerraformMachinePool
    spec:
      drift:
        intervalSeconds: 900
    ```

A machine's or pool's own `intervalSeconds` always wins over the
inherited default. `spec.drift` is operational policy and stays mutable
for the object's whole life, unlike the fields that define the machine or
pool itself (see [The Kinds](../concepts/kinds.md) for what is mutable
per kind).

## Set the drift action

`spec.drift.action` decides what happens when a check finds changes:
`Report` (the default) only records the finding, `Remediate` applies the
object's current inputs to remove it. Both a `TerraformCluster` and a
`TerraformMachinePool` accept `action`:

```yaml
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformCluster
spec:
  drift:
    action: Remediate
```

!!! note "A `TerraformMachine` only reports"

    A `TerraformMachine`'s drift is always reported, never remediated: the
    underlying instance is immutable infrastructure, replaced by a rollout
    rather than patched in place, so `spec.drift` has no `action` field,
    and a `spec.defaults.drift.action` on the `TerraformCluster` does not
    apply to it. A pool without its own `spec.drift.action` takes the
    cluster's `spec.defaults.drift.action`, else the `TerraformCluster`'s
    own `spec.drift.action`.

## Disable drift checks

Setting `intervalSeconds: 0` disables drift checks on a `TerraformCluster`
or a `TerraformMachine`.

!!! warning "Disabling drift checks also stops health sampling"

    Health is read only from a completed refresh or drift Job, so
    disabling drift stops every health sample taken after provisioning:
    the `InfrastructureHealthy` condition stops updating. A
    `TerraformMachine` still refreshes independently while its
    `spec.remediation.annotateMachine` is true; see [Machine
    Remediation](remediation.md).

A `TerraformMachinePool`'s drift cannot be disabled; see
[Drift and health](../concepts/drift-and-health.md#what-runs-and-when)
for why.

## Read the results

`DriftDetected` reports the last check's outcome:

| Status | Reason | Meaning |
| --- | --- | --- |
| `Unknown` | `DriftNotChecked` | The first check has not completed. |
| `False` | `NoDrift` | The last check found no changes. |
| `True` | `DriftReported` | The last check found changes, and the action is `Report`. |
| `True` | `DriftPending` | It found changes, the action is `Remediate`, and the remediation has not started or failed. |
| `True` | `DriftRemediating` | A remediation apply is running. |

```sh
kubectl get terraformcluster <name> -n <namespace> \
  -o jsonpath='{.status.conditions[?(@.type=="DriftDetected")]}'
```

Its message names the drift Job and, when changes were found, the counts
of resources to create, update, replace and delete. `status.lastRun.drift` carries
the same counts as separate fields plus up to 20 affected resource
addresses, and `status.lastDriftCheck` is when the last successful check
completed. `DriftJobSucceeded` separately reports whether the check (or
refresh) Job itself succeeded, independent of what it found. See
[Conditions](../reference/conditions.md#driftdetected) and [Last
run](../reference/resources/common-fields.md#last-run) for every reason and field.

## Remediate drift

With `action: Remediate` set as above, a `TerraformCluster` or
`TerraformMachinePool` re-applies its current inputs whenever a check
finds changes, retried with the same backoff as any other apply (see
[The reconcile lifecycle](../concepts/lifecycle.md)).

!!! warning "Remediation is capped"

    After `failedJobsHistoryLimit` ([job tuning](job-tuning.md)) failed
    remediation applies since the last successful check, `DriftDetected`
    stays `DriftPending` until the next check succeeds.

A `TerraformCluster` remediation apply also goes through the
destructive-plan guard (or plan approval under `applyPolicy: Manual`);
the guard does not apply to a `TerraformMachinePool` (see [Plan
Approval](plan-approval.md)). See [Drift and
Health](../concepts/drift-and-health.md#report-or-remediate) for exactly
how a remediation runs and what each `DriftDetected` reason during it
means.

A `TerraformMachine`'s drift is never remediated this way: an unhealthy
instance is instead signaled to Cluster API for replacement. See [Machine
Remediation](remediation.md).

## Confirm it worked

!!! success ""

    After a check completes, `status.lastDriftCheck` advances and
    `DriftDetected` reads `False`/`NoDrift` or `True` with a reason above.
    After a `Remediate` apply succeeds, `DriftDetected` returns to
    `False`/`NoDrift` and `status.lastRun.drift` is empty again.

!!! related "See also"

    - [Drift and Health](../concepts/drift-and-health.md) for how checks and
      health sampling work.
    - [Machine Remediation](remediation.md) for handling an unhealthy
      `TerraformMachine`.
    - [Plan Approval](plan-approval.md) for the destructive-plan guard a
      `TerraformCluster` remediation apply goes through.
    - [Machine Pools](machine-pools.md) for the pool's separate membership
      refresh schedule.
    - [Conditions](../reference/conditions.md#driftdetected) and [Manager
      Flags](../reference/manager-flags.md).
