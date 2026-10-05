---
description: Review and approve a destructive plan or, under applyPolicy Manual, every plan, with the exact kubectl commands and caveats.
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
`spec.applyPolicy: Manual` every plan waits for one. This page is the
how-to: the commands to review and approve. How the gates work, what the
plan hash binds and what they do not cover are in the chapter
[Approvals and Gates](../concepts/approvals/README.md).

!!! info "Before you begin"

    - A `TerraformCluster` whose apply you want to guard or preview.
    - `kubectl` access to annotate it and to read the logs of its Jobs. Anyone
      who can patch the object can approve; see [who can
      approve](../concepts/approvals/operating.md#who-can-approve).

## The destructive-plan guard

Under the default `applyPolicy: Automatic`, every `TerraformCluster` apply,
including a drift remediation, plans first and stops before applying if the
plan deletes or replaces a resource. Nothing changes. `ApplyJobSucceeded`
turns `False`/`DestructivePlanBlocked` and its message names the affected
resources and the inputs hash. See [The destructive-plan
guard](../concepts/approvals/destructive-guard.md) for the full behavior.

To approve:

1. Read the plan: `kubectl logs job/<job> -n <namespace> -c source`. The
   condition message lists what it deletes or replaces.
2. Approve the **inputs hash** named in the condition:

    ```sh
    kubectl annotate terraformcluster <name> -n <namespace> \
      captf.io/approve-destructive-plan=<inputs-hash> --overwrite
    ```

    `<name>` and `<namespace>` are the `TerraformCluster`'s; `<inputs-hash>`
    is the hash from the condition message.

!!! note "The approval covers exactly those inputs"

    The next change produces a new hash and is guarded again. The
    controller removes the annotation after the approved apply succeeds.
    `lifecycle { prevent_destroy = true }` in the module remains the
    stronger control for a resource that must never be replaced.

## Plan preview: applyPolicy Manual

Set `spec.applyPolicy: Manual` on the `TerraformCluster` or its
`TerraformClusterTemplate` to review every change except the first apply.
Switching back to `Automatic` applies whatever was waiting.

1. A change plans first. `ApplyJobSucceeded` becomes
   `Unknown`/`PlanAwaitingApproval` and `status.plan` fills in. Nothing
   applies.
2. Review `status.plan` (counts, and up to 50 resources with their actions)
   and the plan Job's log, which has the human-readable plan:

    ```sh
    kubectl get terraformcluster <name> -n <namespace> -o jsonpath='{.status.plan}'
    kubectl logs job/<plan-job> -n <namespace> -c source
    ```

3. Approve by naming the plan hash, `status.plan.planHash`:

    ```sh
    kubectl annotate terraformcluster <name> -n <namespace> \
      captf.io/approve-plan=<plan-hash> --overwrite
    ```

4. The apply plans again and applies only if the new plan has the same
   hash. If anything changed, it stops with `PlanChanged` and a new plan to
   approve. See [Manual plan
   approval](../concepts/approvals/manual-approval.md#when-the-plan-changes).
5. After the approved apply succeeds, the controller removes the
   annotation, clears `status.plan` and emits `PlanApplied`.

!!! warning "Approving a plan also approves its deletes and replacements"

    `captf.io/approve-destructive-plan` is not needed under `Manual`. A
    plan with no changes needs no approval. A plan that only changes
    outputs, or only imports or moves, does.

### Caveats

- The plan hash binds what each change does, including old and new values,
  so a plan with different values needs its own approval. It reveals no
  value; read values in the plan Job's log. See [What the plan hash
  binds](../concepts/approvals/fingerprint.md).
- An approval is consumed only when the approved apply succeeds. A stale one
  can approve a later plan with the same hash. Remove it with
  `kubectl annotate terraformcluster <name> -n <namespace>
  captf.io/approve-plan-`.
- Hashes start with `p2:`. After an upgrade from a release with `p1:`
  hashes, a waiting plan is planned again and needs a new approval.
- `status.plan` is status, not durable state: after `clusterctl move` the
  controller plans again, and an approval still on the annotation applies if
  the new plan hashes the same.
- In a GitOps setup, the annotation is set by a person, or by a pipeline
  after its own review of `status.plan` and the plan Job's log. Do not keep
  it in Git: a controller that syncs annotations from Git would re-add a
  consumed approval.

## What is not guarded

Neither gate applies to a `TerraformMachine`, and a `TerraformMachinePool` is
guarded only when its apply renders a changed set of cluster exports (see
[Machine pools](../concepts/approvals/destructive-guard.md#machine-pools)).
Destroy, restore, refresh and drift Jobs are never gated. See
[Approvals and Gates](../concepts/approvals/README.md#scaling-is-not-gated)
and [Limits](../concepts/approvals/limits.md).

## Confirm it worked

!!! success ""

    - After approving a destructive plan, `kubectl describe terraformcluster
      <name> -n <namespace>` shows `ApplyJobSucceeded` back to `True` and the
      `captf.io/approve-destructive-plan` annotation gone.
    - After approving a plan under `Manual`, `status.plan` is empty and
      `ApplyJobSucceeded` is `True`/`ApplySucceeded`.

!!! related "See also"

    - [Approvals and Gates](../concepts/approvals/README.md), the chapter
      behind this page.
    - [Operating the gates](../concepts/approvals/operating.md) for conditions,
      events and RBAC.
    - [Drift](drift.md) for `drift.action: Remediate`, which the
      destructive-plan guard also covers.
    - [Reconcile Lifecycle](../concepts/lifecycle.md).
    - [Annotations, Labels and Finalizers](../reference/annotations-labels.md),
      [Conditions](../reference/conditions.md#applyjobsucceeded) and
      [Events](../reference/events.md).
