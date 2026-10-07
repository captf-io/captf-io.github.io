---
description: How the always-on destructive-plan guard blocks a TerraformCluster apply that deletes or replaces a resource until you approve its TerraformPlan.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/shield-alert
subtitle: "Extra check for plans that delete"
---

# The Destructive-Plan Guard

A `TerraformCluster` is mutable: a new image tag, an edited field or a drift
remediation re-applies its module. A module release that renames a
resource, or a different module pointed at the same state, can plan to
destroy infrastructure nobody meant to destroy. The guard stops that. It is
on for every `TerraformCluster` apply under `applyPolicy: Automatic`, and it
cannot be turned off. A `TerraformMachinePool` has a narrower form of the same
guard, for applies that render a change of the cluster's exports (see [Machine
pools](#machine-pools)). The command to approve is in [Plan
Approval](../../user-guide/plan-approval.md#the-destructive-plan-guard).

## The flow

```mermaid
flowchart TD
    A["Apply Job starts<br/>(guard on)"] --> B["init, validate,<br/>plan, show"]
    B -->|no changes| S["Skip the apply step,<br/>Job succeeds"]
    B -->|changes| D{"Does any change<br/>delete or replace?"}
    D -->|no| AP["Apply the saved plan"]
    D -->|yes| H{"Is a TerraformPlan of<br/>exactly this plan approved?"}
    H -->|yes| AP
    H -->|no| BL["Stop: nothing applied<br/>TerraformPlan Pending<br/>DestructivePlanBlocked"]
    BL -->|"approve the TerraformPlan"| A
```

The guarded apply runs `init`, `validate`, `plan -detailed-exitcode -out`,
`show -json` and then applies the saved plan, instead of applying directly.

- A change counts as destructive when its planned actions include a delete:
  a removal, or a replacement in either order. A `forget`, an `import` or a
  `move` is not destructive.
- If the plan has no changes, the apply step is skipped and the Job
  succeeds, adopting the inputs hash and pinning the image digest as a full
  apply would.
- If the plan only creates or updates in place, it applies without any
  approval.
- If it deletes or replaces anything and no approved `TerraformPlan` names
  exactly this plan, the Job stops before the apply step. Nothing changes and
  the state is untouched. The runner reports the plan, and the manager
  creates a `TerraformPlan` with the reason `Destructive`, in the phase
  `Pending`, with `spec.inputsHash` set to the inputs hash of that apply.

The guard applies to every reason for an apply on a `TerraformCluster`: the
first apply, changed inputs, a retry, a drift remediation and a state with
no inputs hash. Under `Manual` it is replaced by the plan approval: a plan
you approved is run as it is, and the plan has the reason `Manual`.

## What a block looks like

- `status.lastRun.error.kind` is `blocked`.
- `ApplyJobSucceeded` is `False`/`DestructivePlanBlocked`. The message names
  the affected addresses and actions (`<address> (delete)` or `(replace)`),
  says nothing was applied, and names the `TerraformPlan` to approve with
  the command to do it. `status.pendingPlanRef.name` names the same plan.
- A `DestructivePlanBlocked` warning event is emitted once per blocked Job,
  in place of the generic failure event, and names the plan and the command.
- The Job is annotated `captf.io/destructive-plan-blocked`, and, once it is
  bookkept, `captf.io/plan-hash` with the hash of the plan it made.
- A blocked Job counts toward neither the retry backoff nor the
  remediation failure cap, and does not mark the last apply as failed.

While the newest apply of the current inputs hash is blocked, no apply of
that hash starts, and the controller re-checks at least every ten minutes.
The apply waits for the plan's approval even when no Job exists any more:
after `clusterctl move`, which moves plans but not Jobs, the moved plan
still gates the apply. A blocked apply whose result has no plan creates no
`TerraformPlan` and is retried after `RetryMax` (ten minutes).
What else pauses depends on why the apply was due:

- A blocked **input change** pauses drift and health checks too, since they
  would render the unapplied inputs.
- A blocked **drift remediation** leaves drift and health checks running.

A new inputs hash starts a new guarded apply at once, and so does approving
the blocked one. The old plan is superseded as soon as the inputs no longer
hash to its `spec.inputsHash`.

## Approving

Read the plan first: `kubectl logs job/<name> -c source` has its
human-readable output, and the condition message lists what it deletes or
replaces. Then approve the `TerraformPlan` the message names:

```sh
kubectl patch terraformplan <plan> -n <namespace> --type merge \
  -p '{"spec":{"approved":true,"approvedBy":"<your username>"}}'
```

The approval binds **the exact plan**, not only the inputs. The apply runs
with `--expect-plan=<spec.planHash>`: it plans again and applies only if the
new plan hashes the same. Two
things follow:

- If something changed in the meantime and the approved apply finds a
  different plan, nothing is applied. The plan becomes `Failed`, and the
  next guarded apply plans again. If that plan is still destructive, it
  blocks again and creates a new `TerraformPlan` to approve.
- An approval is consumed with its plan: once the plan is `Applied`,
  `Superseded` or `Failed` it cannot be approved again, so a later
  destructive plan of the same inputs always needs its own approval. A
  drift remediation, which re-applies inputs the state already records, is
  no exception.

## Machine pools

A `TerraformMachinePool` has no `applyPolicy`, but its apply is guarded in one
case: when it renders cluster exports (`captf_cluster_outputs`) that **differ
from those of the pool's last successful apply**. The guard is the same: the
apply stops before a plan that deletes or replaces anything. Nothing else
about a pool is guarded on its own: the first apply, bootstrap rotations,
version rolls, replica changes and spec edits all apply as before while the
exports are unchanged. Machines are never guarded. See [Limits](limits.md#cluster-outputs-reach-pools-and-machines).

The controller keeps a record of the exports of each successful apply in the
pool's durable inputs Secret, and compares the current exports with it. A pool
with no record is covered in [Pools that applied before the record
existed](#pools-that-applied-before-the-record-existed).

### The approval hash

A pool's plan has the reason `ExportsChange`, and its `spec.inputsHash` is
the pool's **approval hash**: the inputs hash without `bootstrap_data`. It
survives bootstrap rotations, which change `bootstrap_data` roughly every few
minutes, and changes on any other input change. Unlike a cluster's, a pool's
approval binds the approval hash, not the exact plan: once approved, the
apply runs with `--allow-deletes-hash=<approval hash>`, so a rotation in the
meantime does not invalidate it. `ApplyJobSucceeded` names the plan and the
command, and `status.pendingPlanRef.name` of the pool names it too:

```sh
kubectl patch terraformplan <plan> -n <namespace> --type merge \
  -p '{"spec":{"approved":true,"approvedBy":"<your username>"}}'
```

Approval is RBAC on `terraformplans`; see [Who can
approve](operating.md#who-can-approve). The approval ends with the plan,
after the successful apply it approved.

### When it is blocked: the change is held

A blocked apply of a change of the exports is **held**, not retried:

- The pool **keeps applying everything else** (rotations, upgrades, edits)
  with the exports of its last successful apply, so it keeps working.
- **Refresh and drift render the held exports**, so the waiting change does
  not read as drift.
- `ApplyJobSucceeded` stays `False`/`DestructivePlanBlocked`, with what the
  plan would delete or replace and the approval hash, so the pool's `Ready` is
  `False` while a change is held.
- One `Warning` event, `DestructivePlanBlocked`, is emitted per blocked Job.
- The change is recorded in the durable Secret
  (`captf.io/pending-cluster-outputs`).
- The pool holds only as long as the plan's approval hash is the current
  one.

### Withdrawn and superseded

- **Withdrawn.** If the exports return to the applied ones, nothing waits. The
  condition reports the last apply's real outcome and names the withdrawn Job,
  and the plan is `Superseded`, so an approval of that change is ignored. If
  the change comes back, it is held again and needs a new plan and a fresh
  approval.
- **Superseded.** If the exports move to a different change, or the pool's
  spec changes the approval hash, the old plan is `Superseded`. An approval is
  for one change.

!!! warning "A spec edit of a held pool makes it re-guard"

    The tradeoff of binding the approval hash: an edit of the pool's spec
    while a change is held changes the hash. The pool then re-guards: a new
    guarded apply blocks again and creates a new `TerraformPlan`, which
    supersedes the old one, instead of keeping the old approval.

### Partly applied

If a guarded apply fails after it started, or its Job vanishes mid-run, the
state may hold part of the change. The controller records it
(`captf.io/partial-cluster-outputs`).

!!! warning "Until an apply succeeds, a partly applied pool holds nothing"

    **Until an apply succeeds, the pool holds nothing**: it cannot fall back to
    the last successful apply's exports, and every apply is guarded by its own
    approval hash, rotations included. A destructive one waits for approval.
    This matters most for modules whose rotations replace resources, such as an
    instance configuration.

### Unrecorded

The record of the applied exports shares the durable Secret's budget (about
1,000,000 bytes) with the rendered inputs. If it did not fit while a change is
pending, the pool cannot hold the change and waits, like a cluster, until it
is approved or an input other than `bootstrap_data` changes. A hash annotation
(`captf.io/applied-cluster-outputs-hash`) survives the record being dropped, so
a later change is still guarded.

### Pools that applied before the record existed

A pool that applied before CAPTF recorded applied exports has no baseline. On
its first reconcile after the upgrade, CAPTF records the exports it can **prove**
the pool applied:

- its newest successful apply's exports, when the durable inputs still hash to
  the state's inputs hash; or
- its current exports, when no apply Job is retained and the current inputs
  hash to the state's.

Without that proof (an apply Job was recorded as gone, or the Secret does not
match the state), **every apply of the pool is guarded until one succeeds**. A
plan that deletes or replaces nothing applies and records the baseline. A
destructive plan waits for approval like a cluster's, and `ApplyJobSucceeded`
says the exports of the last successful apply are unknown and gives the approve
command. See [Upgrades](../../operator-guide/upgrades.md).

### An apply Job deleted while it ran

This applies to `TerraformCluster` and `TerraformMachinePool`, not to
`TerraformMachine`. If an apply Job is deleted while it runs (for example
`kubectl delete job`), the Job may have applied part of its change. CAPTF
confirms with live reads that the Job is gone and that the object's live
status still names it, then records it in the durable inputs Secret
(`captf.io/interrupted-apply=<job>`). Then:

- **An apply of the current inputs stays due**, even if the inputs equal the
  state's.
- **That apply is guarded** wherever the destructive guard applies: every
  cluster apply, and pool applies that change exports. A plan that would undo
  the lost Job's work waits for approval. Under `applyPolicy: Manual` the due
  apply plans first and waits for plan approval as usual.
- `ApplyJobSucceeded` is `False`/`ApplyFailed` with the message `Job <name>:
  disappeared while it ran and may have applied part of its change; an apply
  of the current inputs is due`, followed by whether that apply is guarded.
  This condition takes precedence over an older blocked or plan-changed apply:
  it names the vanished Job until an apply started after it (one carrying
  `captf.io/after-interrupted-apply`) reports its own outcome, so an earlier
  "approve hash …" message no longer hides it.
- It clears when an apply started afterwards succeeds (those Jobs carry
  `captf.io/after-interrupted-apply`).

Nothing is recorded for a stuck Job that CAPTF deleted itself, and a
`TerraformMachine` records nothing. For a pool whose lost Job rendered a change
of the cluster's exports, the change is also recorded as partly applied (see
above).

### Limits

- A deleting pool applies nothing: its condition says no apply runs.
- `clusterctl move` does not carry Jobs or status, but it carries the
  `TerraformPlan`, so a plan that waits for approval still gates the apply on
  the target cluster.

## Blocked after a failed apply

For clusters and pools, an apply that was blocked after an earlier apply
**failed** now waits for its approval, and the approval applies it. Before, such
a blocked apply sat idle and the earlier failure was forgotten.

## Prevent destroy

!!! tip "Use prevent_destroy for a resource that must never be replaced"

    `lifecycle { prevent_destroy = true }` in the module is the stronger
    control: it fails even an approved plan, under either policy.

!!! related "See also"

    - [Manual plan approval](manual-approval.md), which binds a plan instead of
      the inputs.
    - [Operating the gates](operating.md).
    - [Drift](../../user-guide/drift.md), whose `Remediate` action the guard
      also covers.
    - [Conditions](../../reference/conditions.md#applyjobsucceeded).
