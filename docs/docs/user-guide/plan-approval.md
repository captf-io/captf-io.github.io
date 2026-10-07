---
title: "Approve a Terraform Plan Before Apply"
description: Find, review and approve a TerraformPlan for a destructive plan or, under applyPolicy Manual, every plan, with the kubectl commands and caveats.
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/circle-check
subtitle: "Gate destructive or manual applies"
---

# Plan Approval

`TerraformCluster` guards two things before it changes infrastructure: a
plan that deletes or replaces a resource waits for an approval, and with
`spec.applyPolicy: Manual` every plan waits for one. Each wait is a
[`TerraformPlan`](../reference/resources/terraformplan.md) object that you
approve by setting `spec.approved`. This page is the how-to: the commands to
find, review and approve it. How the gates work, what the plan hash binds and
what they do not cover are in the chapter [Approvals and
Gates](../concepts/approvals/README.md).

!!! info "Before you begin"

    - A `TerraformCluster` whose apply you want to guard or preview.
    - `kubectl` access to read `terraformplans` and to patch them, and to read
      the logs of the target's Jobs. Approving needs no access to the target;
      see [who can
      approve](../concepts/approvals/operating.md#who-can-approve).

## Find the plan

A waiting plan is named by `status.pendingPlanRef.name` on its target (a
`TerraformCluster` or a `TerraformMachinePool`), and the field is omitted when
no plan is live:

```sh
kubectl get terraformcluster <name> -n <namespace> \
  -o jsonpath='{.status.pendingPlanRef.name}'
```

To list plans by label instead:

```sh
kubectl get terraformplans -n <namespace> -l captf.io/plan-phase=Pending
```

`kubectl get terraformplans` shows each plan's target, reason, phase and
counts. A target has at most one live plan, in the phase `Pending` or
`Approved`. A newer plan, or a change that makes the plan moot, supersedes
it.

## Approve a plan

1. Read the plan: its counts and resources are in `spec.summary`, and the
   human-readable plan is in the log of the Job the condition message names:

    ```sh
    kubectl get terraformplan <plan> -n <namespace> -o jsonpath='{.spec.summary}'
    kubectl logs job/<job> -n <namespace> -c source
    ```

2. Approve it, with your own username in `approvedBy`:

    ```sh
    kubectl patch terraformplan <plan> -n <namespace> --type merge \
      -p '{"spec":{"approved":true,"approvedBy":"'"$(kubectl auth whoami -o jsonpath='{.status.userInfo.username}')"'"}}'
    ```

    The admission webhook requires `approvedBy` to equal the username of the
    request, so the field says who approved. The plan moves to `Approved`, and
    the controller emits `PlanApproved` on the target when it first sees the approval.

3. The apply runs with `--expect-plan=<spec.planHash>`. It plans again and
   applies only if the new plan has the same hash. After it succeeds, the
   plan is `Applied`.

An approval cannot be undone, and a plan that is `Applied`, `Superseded` or
`Failed` can no longer be approved.

## The destructive-plan guard

Under the default `applyPolicy: Automatic`, every `TerraformCluster` apply,
including a drift remediation, plans first and stops before applying if the
plan deletes or replaces a resource. Nothing changes. The manager creates a
`TerraformPlan` with the reason `Destructive`, and `ApplyJobSucceeded` turns
`False`/`DestructivePlanBlocked`. Its message names the affected resources and
the plan to approve, with the command. See [The destructive-plan
guard](../concepts/approvals/destructive-guard.md) for the full behavior.

Approve the plan as above. The approval binds the exact plan, not only the
inputs: if the approved apply plans something else, it applies nothing, the
plan becomes `Failed`, and a new plan blocks again if it is still
destructive.

!!! note "Each destructive plan needs its own approval"

    A finished plan cannot be approved again, so the next destructive plan
    is blocked and needs a new plan and a new approval.
    `lifecycle { prevent_destroy = true }` in the module remains the stronger
    control for a resource that must never be replaced.

## Plan preview: applyPolicy Manual

Set `spec.applyPolicy: Manual` on the `TerraformCluster` or its
`TerraformClusterTemplate` to review every change except the first apply.
Switching back to `Automatic` makes a waiting plan moot, and the apply runs.

1. A change plans first. The manager creates a `TerraformPlan` with the
   reason `Manual`, and `ApplyJobSucceeded` becomes
   `Unknown`/`PlanAwaitingApproval`. Nothing applies. A plan with no change
   creates no object and applies at once.
2. Find, review and approve the plan as above.
3. If anything changed, the apply stops with `PlanChanged`: the approved plan
   becomes `Failed`, and a new `Manual` plan waits for approval. See [Manual
   plan
   approval](../concepts/approvals/manual-approval.md#when-the-plan-changes).

!!! warning "Approving a plan also approves its deletes and replacements"

    A `Manual` plan needs no separate destructive approval. A plan with no
    changes needs no approval. A plan that only changes outputs, or only
    imports or moves, does.

### Caveats

- The plan hash binds what each change does, including old and new values,
  so a plan with different values needs its own approval. It reveals no
  value; read values in the plan Job's log. See [What the plan hash
  binds](../concepts/approvals/fingerprint.md).
- A failed step of the approved apply keeps the plan `Approved`: the apply is
  retried with the same expected plan.
- Hashes start with `p2:`.
- Plans are objects of their own: they move with their target through
  `clusterctl move`, and the moved plan still gates the apply, even though
  Jobs and status do not move.
- Finished plans are kept for history. The manager keeps the 10 newest
  finished plans of each target.
- In a GitOps setup, do not keep `TerraformPlan` objects in Git: the manager
  creates them. A person approves one, or a pipeline does after its own
  review of the plan and the plan Job's log.

## Automate approvals

Because a plan is an object, a pipeline or a bot can list, watch and approve
plans like any Kubernetes object, using the same patch. Limit what it may
approve with RBAC on `terraformplans`, and with a
`ValidatingAdmissionPolicy` that lets a bot approve non-destructive plans
while a destructive plan needs a human group. See [Tiered
auto-approval](../concepts/approvals/operating.md#tiered-auto-approval) for
the policy and its binding.

## What is not guarded

Neither gate applies to a `TerraformMachine`, and a `TerraformMachinePool` is
guarded only when its apply renders a changed set of cluster exports (see
[Machine pools](../concepts/approvals/destructive-guard.md#machine-pools)).
A pool's plan has the reason `ExportsChange`, and you approve it the same
way. Destroy, restore, refresh and drift Jobs are never gated. See
[Approvals and Gates](../concepts/approvals/README.md#scaling-is-not-gated)
and [Limits](../concepts/approvals/limits.md).

## Confirm it worked

!!! success ""

    - After approving a plan, `kubectl get terraformplan <plan> -n
      <namespace>` shows the phase `Approved`, then `Applied` once the apply
      succeeds.
    - `kubectl describe terraformcluster <name> -n <namespace>` shows
      `ApplyJobSucceeded` back to `True`/`ApplySucceeded`, and
      `status.pendingPlanRef` is gone.

!!! related "See also"

    - [Approvals and Gates](../concepts/approvals/README.md), the chapter
      behind this page.
    - [Operating the gates](../concepts/approvals/operating.md) for the plan
      lifecycle, conditions, events and RBAC.
    - [TerraformPlan](../reference/resources/terraformplan.md).
    - [Drift](drift.md) for `drift.action: Remediate`, which the
      destructive-plan guard also covers.
    - [Reconcile Lifecycle](../concepts/lifecycle.md).
    - [Annotations, Labels and Finalizers](../reference/annotations-labels.md),
      [Conditions](../reference/conditions.md#applyjobsucceeded) and
      [Events](../reference/events.md).
