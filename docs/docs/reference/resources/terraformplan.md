---
description: "Reference for the TerraformPlan kind: a plan that waits for an approval, its spec and status, labels, phases, conditions, print columns and admission rules."
icon: lucide/clipboard-check
subtitle: "A plan waiting for an approval"
---

# TerraformPlan

A `TerraformPlan` is one plan that the manager made for a
[`TerraformCluster`](terraformcluster.md) or a
[`TerraformMachinePool`](terraformmachinepool.md) and that waits for an
approval before it is applied. The manager creates it and owns it; you
approve it by setting `spec.approved`. The name is derived from the Job that
made the plan and the plan hash, so it is deterministic per Job: a recurring
identical plan, such as the same drift planned again later, is a new object.
A target names its live plan in `status.pendingPlanRef.name`. Because it is an object of its own, an
approval can be listed, selected, watched, audited and automated like any
other Kubernetes object, and it moves with its target through `clusterctl
move`.

`TerraformPlan` is a public integration API. Its field names, its labels,
its phases and its conditions are frozen for `v1alpha1`: a dashboard, a policy
engine or a pipeline may depend on them. The plan itself never carries a
value, only addresses, actions and counts.

| | |
| --- | --- |
| API version | `infrastructure.cluster.x-k8s.io/v1alpha1` |
| Kind | `TerraformPlan` |
| Scope | Namespaced, in the namespace of its target |
| Created by | The manager, named `<target name>-<10 hex chars>`. You never write the plan fields |
| Owned by | Its target (`spec.targetRef`), through a controller owner reference |
| Finalizer | none |
| Short names | `tfplan` |
| Categories | `cluster-api` |
| Status subresource | yes |

## Example

A plan for a `TerraformCluster` that replaces one resource, as `kubectl get
-o yaml` shows it before anyone approves it:

```yaml title="terraformplan.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformPlan
metadata:
  name: demo-3f9a1c07be
  namespace: default
  labels:
    cluster.x-k8s.io/cluster-name: demo
    captf.io/destructive: "true"
    captf.io/plan-phase: Pending
    captf.io/plan-reason: Destructive
spec:
  targetRef:
    kind: TerraformCluster
    name: demo
  planHash: "p2:9c1e0d4a6b7f2e3d5a8c1b0f4e6d7a9c2b3e5f8a1d4c6b7e0f2a3d5c8b1e4f6a"
  inputsHash: "h2:51ab0c3d7e9f2a4b6c8d0e1f3a5b7c9d1e3f5a7b9c1d3e5f7a9b1c3d5e7f9a1b"
  reason: Destructive
  summary:
    create: 1
    update: 2
    replace: 1
    delete: 0
    resources:
      - aws_instance.control_plane (replace)
      - aws_lb.api (update)
      - aws_route53_record.api (update)
      - aws_security_group_rule.api (create)
status:
  phase: Pending
  observedGeneration: 1
```

To approve it, set `approved` and your own username in `approvedBy`:

```bash
kubectl patch terraformplan demo-3f9a1c07be --type merge \
  -p "{\"spec\":{\"approved\":true,\"approvedBy\":\"$(kubectl auth whoami -o jsonpath='{.status.userInfo.username}')\"}}"
```

## Spec

The manager writes every field except `approved` and `approvedBy` when it
creates the object, and none of them ever changes afterwards.

| Field | Type | Description |
| --- | --- | --- |
| `spec.targetRef` | object | The object the plan is for, in the plan's namespace. **Required.** **Immutable.** |
| `spec.targetRef.kind` | string | The kind of the target. **Required.** **Allowed values:** `TerraformCluster`, `TerraformMachinePool`. |
| `spec.targetRef.name` | string | The name of the target. **Required.** **Range:** 1 to 253 characters. |
| `spec.planHash` | string | The fingerprint of the plan's changes. An approval covers exactly the plan with this hash: the apply plans again and runs only if the hash is the same. **Required.** **Immutable.** **Range:** 1 to 128 characters. |
| `spec.inputsHash` | string | The hash of the inputs the plan was made for. **Required.** **Immutable.** **Range:** 1 to 128 characters. |
| `spec.reason` | string | Why the plan waits for an approval. **Required.** **Immutable.** **Allowed values:** see [Reasons](#reasons). |
| `spec.summary` | object | The summary of the plan: counts and the changed resources, never a value. **Required.** **Immutable.** Must set at least one property. |
| `spec.summary.create` | integer | Resources the plan creates. **Range:** 0 or more. |
| `spec.summary.update` | integer | Resources the plan updates in place. **Range:** 0 or more. |
| `spec.summary.replace` | integer | Resources the plan replaces: deletes and creates again. A replacement counts here only. **Range:** 0 or more. |
| `spec.summary.delete` | integer | Resources the plan deletes, not counting replacements. **Range:** 0 or more. |
| `spec.summary.import` | integer | Resources the plan imports into the state. **Range:** 0 or more. |
| `spec.summary.move` | integer | Resources a `moved` block moves to a new address. **Range:** 0 or more. |
| `spec.summary.forget` | integer | Resources the plan removes from the state without destroying them. **Range:** 0 or more. |
| `spec.summary.outputChanges` | integer | Root module outputs the plan changes. An output change alone needs approval, because cluster exports feed every machine and pool module. **Range:** 0 or more. |
| `spec.summary.resources` | array of strings | `<address> (<labels>)` of each changed resource, sorted by address. **Range:** at most 50 items, each 1 to 600 characters. The labels are the action (`create`, `update`, `delete`, `replace`, `read` or `forget`), or `import` or `move` for an otherwise unchanged resource, comma-separated: `aws_instance.a (import)`, `aws_instance.b (update, move)`. |
| `spec.summary.truncated` | boolean | `true` when `spec.summary.resources` lists fewer resources than the plan changes. |
| `spec.approved` | boolean | Approves the plan. **Optional.** It can only change from unset or `false` to `true`, never back, and only while the plan is live ([Phases](#phases)). |
| `spec.approvedBy` | string | The user that approved. **Optional**, and required when `approved` is `true`. It must equal the username of the request that sets `approved` ([Who can approve](#who-can-approve)). **Range:** 1 to 512 characters. |

### Reasons

| `spec.reason` | The plan waits because |
| --- | --- |
| `Manual` | The `TerraformCluster` has `spec.applyPolicy: Manual`, so every change waits. |
| `Destructive` | The plan deletes or replaces resources, and the target applies automatically otherwise. |
| `ExportsChange` | A `TerraformMachinePool` applies a change of its cluster's exports. |

## Status

The manager sets `status`; you do not write it. `status` has at least one
property when present.

| Field | Type | Description |
| --- | --- | --- |
| `status.conditions` | array of Condition | The plan's conditions: `Ready` and `Approved`. **Range:** up to 32 items. Keyed by `type`. |
| `status.conditions[].type` | string | The condition type: `Ready` or `Approved`. |
| `status.conditions[].status` | string | `True`, `False` or `Unknown`. |
| `status.conditions[].reason` | string | A machine-readable reason in CamelCase. |
| `status.conditions[].message` | string | A human-readable detail. |
| `status.conditions[].lastTransitionTime` | time | When `status` last changed. |
| `status.conditions[].observedGeneration` | integer | The `metadata.generation` the condition was computed from. |
| `status.phase` | string | Where the plan is in its life. **Allowed values:** see [Phases](#phases). |
| `status.observedGeneration` | integer | The `metadata.generation` the status was computed for. **Range:** 1 or more. |

### Phases

| `status.phase` | Meaning | Live |
| --- | --- | --- |
| `Pending` | The plan waits for an approval. | yes |
| `Approved` | The plan was approved and its apply has not finished. | yes |
| `Applied` | The plan was approved and its apply succeeded. | no |
| `Superseded` | A newer plan of the target replaced it, or it became moot, before it was applied. | no |
| `Failed` | The plan was approved, but its apply planned other changes and stopped. | no |

A target has at most one live plan: creating a plan supersedes the previous
live one. A plan becomes moot when the target's inputs no longer hash to
`spec.inputsHash`, when no apply is due any more, when the `applyPolicy`
changed, or, for a pool, when the change of the cluster's exports was
withdrawn or replaced. A failed step of the apply, or a deadline, keeps the
plan `Approved`: the apply is retried with the same expected plan.

`Applied`, `Superseded` and `Failed` are terminal: a terminal plan can no
longer be approved. The manager keeps the 10 newest finished plans of each
target and deletes older ones. It never prunes a live plan, and prunes
nothing while the target is paused or deleting.

### Conditions

| Type | Status | Reason | When |
| --- | --- | --- | --- |
| `Ready` | `True` | `Pending` | The plan is live and waits for an approval. |
| `Ready` | `True` | `Approved` | The plan is approved and its apply has not finished. |
| `Ready` | `True` | `Applied` | The apply succeeded. |
| `Ready` | `False` | `Superseded` | The plan was superseded. |
| `Ready` | `False` | `Failed` | The approved apply planned other changes. |
| `Approved` | `True` | `Approved` | `spec.approved` is `true` (`Approved`, `Applied` or `Failed`). |
| `Approved` | `False` | `Pending` | The plan is live and not approved. |
| `Approved` | `False` | `NotApproved` | The plan is finished and was never approved. |
| `Approved` | `False` | `ApprovalIgnored` | The plan was approved, then superseded before it was applied. |

An approval can land just before the plan is superseded. The webhook refuses
an approval only when the plan's label is already terminal, so such an
approval is ignored: `Approved` is `False` with the reason `ApprovalIgnored`,
and the `PlanSuperseded` warning on the target names the current plan.

`observedGeneration` on the object and on each condition tells an
integration whether the status already reflects the latest spec.

## Labels

The manager puts these labels on every plan, so you can select plans without
reading their specs. Their keys and values are frozen for `v1alpha1`. Every
key is also on [Annotations, Labels and
Finalizers](../annotations-labels.md#on-your-objects-and-their-machines).

| Label | Value |
| --- | --- |
| `cluster.x-k8s.io/cluster-name` | The name of the `Cluster` the target belongs to. |
| `captf.io/destructive` | `true` when the plan replaces or deletes a resource (`spec.summary.replace` plus `spec.summary.delete` is above 0), otherwise `false`. |
| `captf.io/plan-phase` | The same value as `status.phase`. It lives on the metadata because `clusterctl move` drops status: a moved plan keeps its phase, and a finished plan cannot be approved again. Only the manager may change it. |
| `captf.io/plan-reason` | The same value as `spec.reason`. |

```bash
# Every plan waiting for an approval that deletes or replaces something
kubectl get terraformplans -A \
  -l captf.io/plan-phase=Pending,captf.io/destructive=true
```

## Printer columns

`kubectl get terraformplans` (or `kubectl get tfplan`) shows:

| Column | Source |
| --- | --- |
| `Target` | `.spec.targetRef.name` |
| `Reason` | `.spec.reason` |
| `Phase` | `.status.phase` |
| `Create` | `.spec.summary.create` |
| `Update` | `.spec.summary.update` |
| `Replace` | `.spec.summary.replace` |
| `Delete` | `.spec.summary.delete` |
| `Approved` | `.spec.approved` |
| `Age` | `.metadata.creationTimestamp` |

## Who can approve

An approval is a write to a `TerraformPlan`, so it is Kubernetes RBAC on
`terraformplans`:

- **Approvers** need `get`, `list` and `watch` to find the plan, and `patch`
  (or `update`) to approve it. They need nothing on the target.
- **`create` equals approve.** The admission webhook accepts a plan created
  with `approved: true` and `approvedBy` set to the creator, because
  `clusterctl move` creates plans again on the target cluster as the mover.
  Whoever may create `terraformplans` can therefore create an approved plan. Grant `create` only to the manager's
  ServiceAccount and to the identity that runs `clusterctl move`.
- **`approvedBy` is verified.** The webhook requires `spec.approvedBy` to
  equal the username of the request that sets `spec.approved` to `true`, so
  the field names who approved and not who claims to have. CAPTF has no
  mutating webhooks, so you write the field yourself: the command above fills
  it from `kubectl auth whoami`.

See [Who can approve](../../concepts/approvals/operating.md#who-can-approve)
for example Roles and a ValidatingAdmissionPolicy for tiered auto-approval.

## Validation

The CRD schema, CEL rules in the CRD and the validating admission webhook
enforce these rules. The webhook runs on create and update, and a request
fails if the webhook is unreachable. The CEL rules hold even then: `spec.targetRef`,
`spec.planHash`, `spec.inputsHash`, `spec.reason` and `spec.summary` are
immutable, `approvedBy` is required exactly when `approved` is `true`, and an
approval can be neither withdrawn nor changed; a violation is refused with
`422 Invalid`.

Schema rules:

- `spec.targetRef`, `spec.planHash`, `spec.inputsHash`, `spec.reason` and
  `spec.summary` are required, with the allowed values and ranges above.
- `spec.summary` and `status` must set at least one property when present,
  and `status.conditions` has at most 32 items.

Webhook rules, on create:

- `spec.approvedBy` is required when `spec.approved` is `true`, and refused
  when it is not.
- Unless the manager creates the plan, `spec.approvedBy` must equal the
  creating user when `spec.approved` is `true`. A plan whose
  `captf.io/plan-phase` label is terminal (`Applied`, `Superseded` or
  `Failed`) is accepted with any `approvedBy`, so `clusterctl move` still works
  for finished plans.
- A creator other than the manager may set the `captf.io/plan-phase` label
  only to `Pending`, or to `Approved` on an approved plan.

Webhook rules, on update:

- Every `spec` field except `approved` and `approvedBy` is immutable.
- `spec.approved` can change only from unset or `false` to `true`, and once
  `true` it and `spec.approvedBy` never change.
- An approval is refused when the stored object's `captf.io/plan-phase` label
  is `Applied`, `Superseded` or `Failed`.
- `spec.approvedBy` must equal the username of the requester.
- Only the manager's ServiceAccount may change or remove the
  `captf.io/plan-phase` label.

## Lifecycle

- **Create.** When a change needs an approval, the manager runs a plan Job
  and creates one `TerraformPlan` for the result, with the plan's counts and
  resources. A plan with no change creates no object.
- **Approve.** Setting `spec.approved` moves the plan to `Approved`. The
  target's apply runs with `--expect-plan=<spec.planHash>` and applies only if
  it plans exactly those changes. A pool's `ExportsChange` plan binds the
  approval hash in `spec.inputsHash` instead (`--allow-deletes-hash`).
- **Finish.** A successful apply makes the plan `Applied`. An apply that found
  other changes makes it `Failed`; a failed step keeps it `Approved`. A newer
  plan, or a change that makes the plan moot, makes it `Superseded`.
- **Delete.** The plan is owned by its target and is garbage-collected with
  it.
- **Move.** `clusterctl move` carries the plan with its target through the
  owner reference, and `captf.io/plan-phase` keeps its phase. Status is
  rebuilt on the target cluster.
