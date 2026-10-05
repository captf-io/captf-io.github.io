---
description: The two approval gates on a TerraformCluster, what each stops and binds, what is not gated, and where to go next.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/clipboard-check
subtitle: "Gate changes behind a review"
---

# Approvals and Gates

CAPTF can stop a `TerraformCluster` before it changes infrastructure and
wait for a person to say yes. It has two such gates, and they apply to the
cluster kind only. This chapter explains what each gate does, what it
binds, what is deliberately not gated, and what an operator needs to run
them safely. The task-oriented commands are in [Plan
Approval](../../user-guide/plan-approval.md).

The pages:

1. This page: the gates, a decision table and the scaling questions.
2. [Manual plan approval](manual-approval.md): `applyPolicy: Manual`, the
   plan Job, `status.plan` and the approved apply.
3. [What the plan hash binds](fingerprint.md): the `p2:` fingerprint.
4. [The destructive-plan guard](destructive-guard.md): the check on every
   cluster apply under `Automatic`.
5. [Operating the gates](operating.md): commands, conditions, events,
   retries, upgrades and who can approve.
6. [Other manual actions](other-manual-actions.md): restores, abandoning
   an object, and the fixes that are not approvals.
7. [Limits](limits.md): what an approval does and does not promise.

## The two gates

| Gate | Set by | What it stops | Annotation that releases it | Binds |
| --- | --- | --- | --- | --- |
| **Manual plan approval** | `spec.applyPolicy: Manual` on a `TerraformCluster` or its template | Every apply except the first one | `captf.io/approve-plan=<plan hash>` | The plan: what each change does, and the output changes |
| **Destructive-plan guard** | Always on, for every `TerraformCluster` apply | An apply whose plan deletes or replaces a resource | `captf.io/approve-destructive-plan=<inputs hash>` | The inputs, not the plan |

Under `Manual` the first gate subsumes the second: approving a plan also
approves the deletes and replacements that plan lists, so the second
annotation is never needed there.

Both gates are specific to `TerraformCluster`, with one narrow extension.
`applyPolicy` exists on no other kind, and the Job builder adds the guard to a
`TerraformCluster`'s apply, and to a `TerraformMachinePool`'s apply **only when
it renders cluster exports that differ from its last successful apply** (see
[Machine pools](destructive-guard.md#machine-pools)). A `TerraformMachine`'s
apply is never gated: its instance is immutable, and Cluster API replaces it
rather than its apply changing it. Destroy, restore, refresh and drift Jobs are
never gated on any kind.

## What is gated

An apply decision has one reason; the reason decides whether a gate sees it.

| Situation | Kind | `Automatic` | `Manual` |
| --- | --- | --- | --- |
| First apply of a new object (no state) | `TerraformCluster` | Guard runs, nothing to delete | Not gated, applies at once |
| Changed inputs (image, spec, variables) | `TerraformCluster` | Guard: blocked if the plan deletes or replaces | Plan, then wait for `approve-plan` |
| Retry after a failed apply | `TerraformCluster` | Guard | Plan, then wait (an earlier approval is reused if the re-plan matches) |
| Drift remediation (`drift.action: Remediate`) | `TerraformCluster` | Guard | Plan, then wait |
| State with no inputs hash | `TerraformCluster` | Guard | Plan, then wait |
| Apply that renders a changed set of cluster exports | `TerraformMachinePool` | Guard: held if the plan deletes or replaces; the pool keeps applying the last exports | Not applicable: no `applyPolicy` |
| Any other apply | `TerraformMachinePool` | Not gated | Not applicable: no `applyPolicy` |
| Any apply | `TerraformMachine` | Not gated | Not applicable: no `applyPolicy` |
| Destroy, restore, refresh, drift check | Any | Not gated | Not gated |

## Scaling is not gated

Scaling does not go through an approval, so a large change to machine
counts does not wait for one:

- **Scaling a `MachineDeployment` up** creates `TerraformMachine` objects.
  Each one's first apply creates its machine; there is nothing for a gate to
  check.
- **Scaling it down** deletes `Machine` objects. After Cluster API drains
  them, each `TerraformMachine` runs a destroy Job, which is never gated.
- **A fixed-replica `MachinePool`** re-applies its pool module when
  `spec.replicas` changes. Such an apply is not gated, unless it also renders
  changed cluster exports.
- **An autoscaled `MachinePool`** scales in the cloud, with no Terraform
  run at all (see [Machine Pools](../../user-guide/machine-pools.md)).

A 100-machine `MachineDeployment` therefore scales without an approval.
If a change to shared infrastructure must wait for a person, that
infrastructure belongs in the cluster module. See [Limits](limits.md) for
how cluster outputs reach machines and pools.

## In this section

<div class="grid cards" markdown>

-   :material-check-decagram-outline:{ .lg .middle } __Approve a Plan__

    ---

    The commands to review and approve a destructive plan or a manual plan.

    [:octicons-arrow-right-24: Approve a Plan](../../user-guide/plan-approval.md)

-   :material-clipboard-check-outline:{ .lg .middle } __Manual Plan Approval__

    ---

    applyPolicy: Manual, the plan Job, status.plan and the approved apply.

    [:octicons-arrow-right-24: Manual Plan Approval](manual-approval.md)

-   :material-fingerprint:{ .lg .middle } __What the Plan Hash Binds__

    ---

    The p2: fingerprint an approval names, and what it covers.

    [:octicons-arrow-right-24: What the Plan Hash Binds](fingerprint.md)

-   :material-shield-alert-outline:{ .lg .middle } __The Destructive-Plan Guard__

    ---

    The check on every cluster apply under Automatic.

    [:octicons-arrow-right-24: The Destructive-Plan Guard](destructive-guard.md)

-   :material-alert-circle-outline:{ .lg .middle } __What Approval Does Not Guarantee__

    ---

    What an approval does and does not promise.

    [:octicons-arrow-right-24: What Approval Does Not Guarantee](limits.md)

</div>

## Where the state lives

An approval rests on three things that other chapters describe:

- the plan key, a Secret that makes the plan hash a keyed value (see [Run
  inputs and the plan key](../secret-management/run-inputs.md#the-plan-key));
- `status.plan`, written by the controller from what the runner reports;
- annotations on the object, which are the approval itself.

!!! related "See also"

    - [Plan Approval](../../user-guide/plan-approval.md) for the commands.
    - [Conditions](../../reference/conditions.md#applyjobsucceeded) and
      [Events](../../reference/events.md) for the exact reasons.
    - [Annotations, Labels and Finalizers](../../reference/annotations-labels.md).
    - [Security Model](../security-model.md).
