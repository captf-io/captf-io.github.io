---
title: "Operating Plan Approval Gates"
description: "Run the plan-approval gates day to day: what the conditions and events mean, how retries and upgrades behave, and who can approve."
tags:
  - Operators
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/toggle-right
subtitle: "Run the approval gates"
---

# Operating the Gates

This page is the reference for running the gates day to day: what the
conditions and events mean, how retries and upgrades behave, and who can
approve. The commands are in [Plan
Approval](../../user-guide/plan-approval.md).

## What you see

Everything below is on the `TerraformCluster`. Read it with:

```sh
kubectl get terraformcluster <name> -n <namespace> \
  -o jsonpath='{range .status.conditions[?(@.type=="ApplyJobSucceeded")]}{.status}/{.reason}: {.message}{"\n"}{end}'
```

### `ApplyJobSucceeded` reasons

| Status / reason | Meaning | What to do |
| --- | --- | --- |
| `Unknown`/`PlanAwaitingApproval` | `Manual`: a plan is ready and nothing applies until it is approved. The message has the counts and the exact approve command | Review `status.plan` and the plan Job's log, then approve |
| `Unknown`/`PlanChanged` | The approved apply re-planned, the plan no longer matched, and nothing was applied. The message has the new plan | Review the new plan, then approve the new hash |
| `False`/`DestructivePlanBlocked` | `Automatic`: the plan deletes or replaces something and the inputs hash is not approved. The message names the resources and the inputs hash | Review the plan, then approve the inputs hash |
| `True`/`ApplySucceeded` | The last apply succeeded | None |
| `False`/`ApplyFailed` | The apply failed; the message names the failing step | See [Failing Jobs](../../operator-guide/runbooks/job-failures.md) |
| `False`/`JobPolicyInvalid` | The merged Job policy is inconsistent (`lockTimeoutSeconds` is not below `activeDeadlineSeconds`), so no Job starts | Fix the timeouts; see [Tuning Jobs](../../user-guide/job-tuning.md#deadlines-and-lock-waits) |
| `Unknown`/`WaitingForRunLease` | Another Job of this object holds the run lease | Wait; it retries every 30 seconds |
| `Unknown`/`WaitingForMachineOperations` | The cluster's apply or destroy waits for machine and pool Jobs to finish | Wait |
| `Unknown`/`WaitingForClusterOperation` | A machine's or pool's apply or destroy waits for the cluster's Job (seen on those kinds) | Wait |
| `False`/`IdentityNotAllowed` | A destroy cannot start because the identity no longer allows the namespace | See [Credentials](../secret-management/credentials.md#revocation) |

`PlanAwaitingApproval` and `PlanChanged` are `Unknown` on purpose: a plan
waiting for you is not a failure and does not make `Ready` false. The full
list of reasons is in [Conditions](../../reference/conditions.md#applyjobsucceeded).

### Events

| Event | Type | When |
| --- | --- | --- |
| `PlanReady` | Normal | A plan Job planned a change; once per plan Job. For an empty plan its message says the apply runs without an approval |
| `PlanApproved` | Normal | The apply of an approved plan started (not for an empty plan) |
| `PlanApplied` | Normal | The approved apply succeeded and `status.plan` was cleared |
| `PlanChanged` | Warning | The plan changed since it was approved |
| `DestructivePlanBlocked` | Warning | A guarded apply stopped on a delete or replace; once per blocked Job |
| `DestructivePlanApprovalConsumed` | Normal | The controller removed a destructive-plan approval after an apply |

An `InputsChanged` event also marks the start of a plan. The condition
transitions for `PlanAwaitingApproval` and `PlanChanged` emit no event of
their own. See [Events](../../reference/events.md) for the full list.

`captf_plan_approvals_total{kind,result}` counts applied approvals
(`approved`) and changed plans (`changed`), and
`captf_destructive_plan_approvals_consumed_total{kind}` counts consumed
destructive-plan approvals; see [Metrics](../../reference/metrics.md).

## Timing

A waiting plan, and a blocked apply, are re-checked at least every ten
minutes, and a changed annotation or new inputs re-trigger the reconcile at
once. The controller does not validate an approval's format: it compares the
string with the plan hash or the inputs hash, and ignores any other value.

## Upgrades

A `status.plan` recorded by an older release has a hash that does not start
with `p2:`. After the upgrade the controller plans again by itself, and the
new hash needs a fresh approval. An old approval annotation does not match.
See [Upgrades](../../operator-guide/upgrades.md).

## Who can approve

**Approval authority is Kubernetes RBAC, by design.** An approval is an
annotation on the object, and whoever may `patch` the `TerraformCluster` may
set `captf.io/approve-plan`; for the destructive-plan guard, whoever may patch
the object may set `captf.io/approve-destructive-plan`. CAPTF's admission
webhook does not restrict these annotations, and will not: the Kubernetes
authorization you already run is the single place that decides who approves.
There is no second list of approvers to keep in step.

!!! warning "Whoever holds patch can both change the module and approve the change"

    The consequence to plan for: RBAC cannot look inside a patch, so it cannot
    separate "sets the annotation" from "edits the spec" on the same object.
    Whoever holds `patch` can both change what the module does and approve the
    change. The way to separate the two is to separate **who holds `patch`**, not
    to restrict an annotation.

The recommended pattern:

- **Approvers** are the principals with `patch` on `terraformclusters` in the
  namespace, with read access to Jobs, pods and logs so they can read the plan.
- **Spec changes** from everyone else come through a reviewed path, such as a
  GitOps pipeline whose ServiceAccount holds the write Role. People propose a
  change in review; an approver reads `status.plan` and the plan log, and
  annotates.
- **Do not give approvers' rights to automation that edits specs**, and do not
  sync the approval annotations from Git: a controller that does would re-add a
  consumed approval.

Example Roles, one for the approvers and one for the pipeline:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: captf-plan-approver
  namespace: <namespace>
rules:
- apiGroups: ["infrastructure.cluster.x-k8s.io"]
  resources: ["terraformclusters"]
  verbs: ["get", "list", "watch", "patch"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["pods/log"]
  verbs: ["get"]
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: captf-spec-pipeline
  namespace: <namespace>
rules:
- apiGroups: ["infrastructure.cluster.x-k8s.io"]
  resources: ["terraformclusters", "terraformmachines", "terraformmachinepools"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

Bind `captf-plan-approver` to the approvers' group and `captf-spec-pipeline` to
the pipeline's ServiceAccount, and give everyone else read-only access. An
approver can still change the spec, so give the Role only to people you would
trust to do so.

Machines and pools are not gated at all, so this split protects the cluster
module only; see [Limits](limits.md).

If you also want an admission policy that rejects the annotations unless the
requester is in a group, that is **optional and outside CAPTF**: a Kubernetes
`ValidatingAdmissionPolicy`, Kyverno or Gatekeeper rule can do it, and must
still let the manager's own ServiceAccount remove a consumed approval. CAPTF
ships none and does not need one.

!!! related "See also"

    - [Plan Approval](../../user-guide/plan-approval.md).
    - [Manual plan approval](manual-approval.md) and [The destructive-plan
      guard](destructive-guard.md).
    - [RBAC](../../operator-guide/rbac.md).
