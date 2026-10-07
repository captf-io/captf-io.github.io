---
title: "Operating Plan Approval Gates"
description: "Run the plan-approval gates day to day: the TerraformPlan lifecycle, conditions and events, retries, who can approve and a tiered auto-approval policy."
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

This page is the reference for running the gates day to day: the
`TerraformPlan` lifecycle, what the conditions and events mean, how retries
behave, and who can approve. The commands are in [Plan
Approval](../../user-guide/plan-approval.md).

## The TerraformPlan lifecycle

Every approval is a [`TerraformPlan`](../../reference/resources/terraformplan.md).
Only the manager creates plans. A plan lives in its target's namespace and is
owned by the target, so it is garbage-collected with it and moves with it
through `clusterctl move`.

- **Name.** `<target name>-<10 hex chars>`, derived from the Job that made the
  plan and the plan hash. It is deterministic per Job, so a recurring
  identical plan, such as the same drift planned again later, is a new
  object.
- **Reasons.** `Manual` (a `TerraformCluster` under `applyPolicy: Manual`),
  `Destructive` (a guarded cluster apply that deletes or replaces) and
  `ExportsChange` (a `TerraformMachinePool` apply of a change of the
  cluster's exports). See [Manual plan approval](manual-approval.md) and [The
  destructive-plan guard](destructive-guard.md).
- **One live plan per target.** A plan is live in the phases `Pending` and
  `Approved`. Creating a plan supersedes the previous live one.

### Phases

| Transition | When | Event |
| --- | --- | --- |
| `Pending` to `Approved` | `spec.approved` becomes `true` | `PlanApproved` on the target, naming `approvedBy`, when bookkeeping first sees the approval |
| `Approved` to `Applied` | The apply Job annotated with the plan succeeded | `PlanApplied` |
| `Approved` to `Failed` | The approved apply planned other changes and stopped | `PlanChanged` (Warning) |
| `Pending` or `Approved` to `Superseded` | A newer plan of the target exists, or the plan became moot | `PlanSuperseded` |

`Failed` happens only when the approved apply planned other changes. A failed
step or a deadline keeps the plan `Approved`: the apply is retried with the
same expected plan after the usual backoff.

A plan becomes moot when:

- the target's inputs no longer hash to the plan's `spec.inputsHash`, because
  they changed or reverted to what is applied;
- no apply is due any more, because the drift it remediated is gone or the
  drift action changed;
- the `applyPolicy` changed, so a `Manual` plan under `Automatic` or the
  reverse;
- for a pool, the change of the cluster's exports was withdrawn (the exports
  are back to the applied ones) or replaced by another change.

Superseding never happens while a Job of the target runs, while the target is
paused or deleting, or while its dependencies gate it (its inputs cannot be
built). `PlanSuperseded` is `Normal`, and `Warning` when the plan had been
approved: its approval is ignored, and the message names the current plan if
there is one.

The phase is mirrored to the label `captf.io/plan-phase`. For the terminal
phases the label is the source of truth, because it survives `clusterctl
move`; the live phases come from `spec.approved`. The webhook refuses to
approve a plan whose label is already terminal. If an approval lands just
before the plan is superseded, it is ignored: the plan's `Approved` condition
is `False` with the reason `ApprovalIgnored`, and the `PlanSuperseded`
warning names the current plan.

### Pruning

The manager keeps the 10 newest finished plans (`Applied`, `Superseded` and
`Failed`) of each target and deletes older ones. It never prunes a live plan,
and prunes nothing while the target is paused or deleting.

### Find a plan

The target's `status.pendingPlanRef.name` names its live plan; the field is
omitted when none is live. To list plans by label:

```sh
kubectl get terraformplans -n <namespace> -l captf.io/plan-phase=Pending
```

### Plan conditions

A plan has two conditions, `Ready` and `Approved`:

| Condition | Status | Reason | When |
| --- | --- | --- | --- |
| `Ready` | `True` | `Pending` | Live, waiting for approval |
| `Ready` | `True` | `Approved` | Approved, apply not finished |
| `Ready` | `True` | `Applied` | Applied |
| `Ready` | `False` | `Superseded` | Superseded |
| `Ready` | `False` | `Failed` | The approved apply planned other changes |
| `Approved` | `True` | `Approved` | `spec.approved` is `true` (`Approved`, `Applied` or `Failed`) |
| `Approved` | `False` | `Pending` | Live and not approved |
| `Approved` | `False` | `NotApproved` | Terminal and never approved |
| `Approved` | `False` | `ApprovalIgnored` | Approved, then superseded before it was applied |

## What you see on the target

Read the target's condition with:

```sh
kubectl get terraformcluster <name> -n <namespace> \
  -o jsonpath='{range .status.conditions[?(@.type=="ApplyJobSucceeded")]}{.status}/{.reason}: {.message}{"\n"}{end}'
```

### `ApplyJobSucceeded` reasons

| Status / reason | Meaning | What to do |
| --- | --- | --- |
| `Unknown`/`PlanAwaitingApproval` | `Manual`: a plan is ready and nothing applies until it is approved. The message starts `TerraformPlan <name> plans inputs hash <hash>: <counts>. Nothing is applied until it is approved:` and ends with the approve command | Review the plan and the plan Job's log, then approve |
| `Unknown`/`PlanChanged` | The approved apply planned other changes and applied nothing. The message reads `Job <apply>: the plan changed since TerraformPlan <old> was approved, so nothing was applied. TerraformPlan <new> plans ...` and gives the approve command. For a `Destructive` plan no new plan exists and the next apply plans again | Review the new plan, then approve it |
| `False`/`DestructivePlanBlocked` | A guarded apply stopped before a plan that deletes or replaces something. The message says what, and names the `TerraformPlan` to approve. On a pool, the plan is for a change of the cluster's exports | Review the plan, then approve the `TerraformPlan` |
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
| `PlanReady` | Normal | A `Manual` plan was created, from a plan Job or as a new plan after `PlanChanged`. It names the plan, its counts and the approve command. Also when a `Manual` plan Job's plan changes nothing: the note says the apply runs without an approval, and no plan is created |
| `DestructivePlanBlocked` | Warning | A guarded apply stopped on a delete or replace; once per blocked Job. It names the plan and the approve command |
| `PlanApproved` | Normal | Bookkeeping first saw `spec.approved` on a plan of the target (not when the apply starts); names it and `approvedBy` |
| `PlanApplied` | Normal | The apply of an approved plan succeeded |
| `PlanChanged` | Warning | An approved apply planned other changes; the plan is `Failed`. Once per such apply, for `Manual` and `Destructive` plans alike |
| `PlanSuperseded` | Normal, Warning when the plan was approved | A plan was superseded; names why and the current plan. The Warning also covers an approval that lost a race with the supersession |

An `InputsChanged` event also marks the start of a plan. See
[Events](../../reference/events.md) for the full list.

`captf_plan_approvals_total{kind,result}` counts plan transitions, with the
results `created`, `approved`, `applied`, `superseded` and `failed`; see
[Metrics](../../reference/metrics.md).

## Timing

A waiting plan, and a blocked apply, are re-checked at least every ten
minutes, and an approval or new inputs re-trigger the reconcile at once.

## Upgrades

Plans are created by the manager from what the runner reports. A plan waiting
from an older release is planned again by itself, and the new plan needs a
fresh approval. See [Upgrades](../../operator-guide/upgrades.md).

## Who can approve

**Approval authority is Kubernetes RBAC, by design.** An approval is an
update of a `TerraformPlan`: whoever may `patch` it sets `spec.approved`.
CAPTF has no second list of approvers to keep in step; the Kubernetes
authorization you already run decides.

- **Approvers** need `get`, `list`, `watch` and `patch` on `terraformplans`.
  They need no access to the target.
- **`create` equals approve.** The admission webhook accepts a plan created
  with `approved: true`, because `clusterctl move` creates plans again on the
  target cluster as the mover. Grant `create` on `terraformplans` only to the
  manager and to the identity that runs `clusterctl move`.
- **`approvedBy` is verified.** The webhook requires `spec.approvedBy` to
  equal the username of the request that sets `approved`. You write the field
  yourself, because CAPTF has no mutating webhooks, and the webhook checks it
  against the admission request.

Because an approval is a write to a separate kind, the right to approve is no
longer the right to edit the target. Approvers do not need `patch` on
`terraformclusters`, and whoever edits specs needs no right on
`terraformplans`. Separate the two roles:

- **Approvers** are the principals with `patch` on `terraformplans` in the
  namespace, with read access to Jobs, pods and logs so they can read the plan.
- **Spec changes** from everyone else come through a reviewed path, such as a
  GitOps pipeline whose ServiceAccount holds the write Role. People propose a
  change in review; an approver reads the plan and its Job's log, and
  approves.
- **Do not give automation that edits specs the right to approve**, and do
  not create plans from Git: a `TerraformPlan` is the manager's object.

Example Roles, one for the approvers and one for the pipeline:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: captf-plan-approver
  namespace: <namespace>
rules:
- apiGroups: ["infrastructure.cluster.x-k8s.io"]
  resources: ["terraformplans"]
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
the pipeline's ServiceAccount, and give everyone else read-only access.

Machines and pools are mostly not gated, so this split protects the cluster
module and a pool's exports changes; see [Limits](limits.md).

### Tiered auto-approval

RBAC cannot look inside a patch, so it cannot allow a bot to approve a
harmless plan and refuse a plan that deletes something. A Kubernetes
`ValidatingAdmissionPolicy` can, because it sees the plan. It is **optional
and outside CAPTF**: CAPTF ships none.

The example below lets a bot ServiceAccount approve plans that delete and
replace nothing. Approving a plan with `spec.summary.delete +
spec.summary.replace` above 0 requires membership in the group
`captf-approvers`. Grant the bot's ServiceAccount `patch` on `terraformplans`
as above; the policy then narrows what it may approve. Replace the bot's
name and the group with your own.

The policy checks `UPDATE` only. An approval is an update of `spec.approved`
from unset or `false` to `true`; a plan created already approved is the
`clusterctl move` path, and RBAC on `create terraformplans` governs it, since
`create` equals approve.

```yaml title="captf-plan-approval-policy.yaml"
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata:
  name: captf-plan-approval-tiers
spec:
  failurePolicy: Fail
  matchConstraints:
    resourceRules:
    - apiGroups: ["infrastructure.cluster.x-k8s.io"]
      apiVersions: ["v1alpha1"]
      operations: ["UPDATE"]
      resources: ["terraformplans"]
  matchConditions:
  - name: approval-transition # (1)!
    expression: >-
      has(object.spec.approved) && object.spec.approved == true &&
      (!has(oldObject.spec.approved) || oldObject.spec.approved != true)
  variables:
  - name: destructive # (2)!
    expression: >-
      (has(object.spec.summary.delete) ? object.spec.summary.delete : 0) +
      (has(object.spec.summary.replace) ? object.spec.summary.replace : 0) > 0
  - name: isHuman
    expression: >-
      has(request.userInfo.groups) &&
      'captf-approvers' in request.userInfo.groups
  validations:
  - expression: "!variables.destructive || variables.isHuman" # (3)!
    reason: Forbidden
    messageExpression: >-
      'plan ' + object.metadata.name + ' deletes or replaces resources: ' +
      'only members of captf-approvers may approve it, not ' +
      request.userInfo.username
---
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicyBinding
metadata:
  name: captf-plan-approval-tiers
spec:
  policyName: captf-plan-approval-tiers
  validationActions: ["Deny"]
```

1. The policy runs only on the transition to approved, on an `UPDATE`, where
   `oldObject` is always set. Every other update of a plan passes it by.
2. The counts are optional integers and can be absent, so each is read behind
   `has()`.
3. A non-destructive plan passes for anyone who already has `patch`, so the
   bot can approve it. A destructive plan passes only for a member of
   `captf-approvers`. A request without groups counts as no member, not as
   an evaluation error.

Notes:

- The manager and the `clusterctl move` identity create plans, some of them
  approved, and the policy never sees a `CREATE`. Keep `create` on
  `terraformplans` to those two: whoever may create a plan may approve one.
- The webhook's own checks still apply: `approvedBy` must equal the
  requester, so the bot writes its own username.
- `failurePolicy: Fail` denies approvals while the policy cannot be
  evaluated. Use `Ignore` only if you accept that.
- To try it first, set `validationActions: ["Audit", "Warn"]` on the binding.
  Violations then show up in the audit log and as a warning to the client
  instead of a denial.

!!! related "See also"

    - [Plan Approval](../../user-guide/plan-approval.md), including [automating
      approvals](../../user-guide/plan-approval.md#automate-approvals).
    - [Manual plan approval](manual-approval.md) and [The destructive-plan
      guard](destructive-guard.md).
    - [RBAC](../../operator-guide/rbac.md).
