---
description: "Design modules that behave well under CAPTF: where resources belong, stable exports, health, autoscaling, import, destroy safety, secrets and testing."
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-02"
authors:
  - "Steven Crothers"
icon: lucide/ruler
subtitle: "Patterns that keep modules safe"
---

# Module Design Patterns

The [module contract](contract/README.md) says what a module must do. This
page says how to design modules that behave well under CAPTF: where each kind
of infrastructure belongs, how to shape exports, what the health and
`provider_id` outputs must do, how pools autoscale, what to expect from
`import` and `moved` blocks, how to keep destroys safe, how to handle
secrets, and how to test. It links to the contract pages instead of
restating them. Read those for the rules; read this for the reasons.

## Put shared and destructive infrastructure in the cluster module

A `TerraformCluster` is the **only** kind whose applies can wait for a
person. `applyPolicy: Manual` gates every change after the first, and the
destructive-plan guard stops any apply, under `Automatic`, whose plan deletes
or replaces a resource. A machine's apply never waits, and a pool's apply
waits only when it renders a changed set of cluster exports and its plan
deletes or replaces something. See [Approvals and
Gates](../concepts/approvals/README.md) and [What is
guarded](../concepts/approvals/limits.md#what-is-guarded).

So decide where a resource lives by what it costs to get wrong:

| Resource | Put it in | Why |
| --- | --- | --- |
| Networks, subnets, security groups, load balancers, DNS, the control-plane endpoint | The **cluster** module | Shared by every machine, and losing one is expensive: changes are gated |
| One node, its disk and its address | The **machine** module | One instance per machine, and replaced rather than changed |
| A scaling group and its launch template | The **pool** module | Reconciled to a count; its own changes are ungated, except a destructive plan after an exports change |
| Anything an operator should review before it changes | The **cluster** module | It is the only place a review can happen |

If a resource is shared **and** a machine or pool module would need to
change it, you have the design wrong: change it in the cluster module and
publish what machines need as an export.

## Design exports for stability

The cluster's `exports` output reaches every machine and pool as the input
`captf_cluster_outputs`, verbatim. See [`exports`](contract/v1alpha1/cluster.md#exports-output).
What happens when it changes depends on the kind:

| Kind | An export change |
| --- | --- |
| `TerraformMachine` | Nothing. The first apply's inputs are stored and re-fed on drift and destroy; a later change is ignored |
| `TerraformMachinePool` | The inputs hash changes and every pool re-applies. The apply is **guarded**: if its plan deletes or replaces anything, the change is held until approved, and the pool keeps applying the last exports meanwhile |

The consequence is the rule: **treat exports as a stable interface.**

- **Publish identifiers, not state of the world.** Export a load balancer's
  target group id or a subnet id, which change only when you replace the
  thing. Do not export a timestamp, a count of machines or an address that
  changes on its own.
- **Change an export only when you mean to roll every pool.** Under `Manual`
  the cluster apply that changes it waits for approval (an output-only change
  needs one), so the person approving sees the change. Each pool then applies
  it. A pool apply that only creates or updates in place follows without a
  prompt; one that deletes or replaces is held until its own approval.
- **Export integers, strings, booleans, lists and objects, but not
  fractions or exponents.** The controller hashes exports, and a number with
  a fractional part or an exponent is rejected with `exports contains a
  fractional or exponent number; export numbers as integers or strings`.
- **No secrets.** The generated root marks `exports` sensitive, so a secret
  there does not fail the plan, but secrets belong in the identity. See [Sensitive
  values](#sensitive-values).
- **Know what a pool replaces.** A pool module that reads an export and
  replaces a resource when it changes is held for approval, but rotations
  that replace resources (an instance configuration, say) matter after a
  failed or partly applied change, when every apply of the pool is guarded.
  Put `lifecycle { prevent_destroy = true }` on the resources a bad export
  could destroy; the apply then fails even if approved. See [Cluster outputs
  reach pools and
  machines](../concepts/approvals/limits.md#cluster-outputs-reach-pools-and-machines)
  and [Machine pools](../concepts/approvals/destructive-guard.md#machine-pools).

## Health and `provider_id`

A machine reports itself through two outputs, and the controller is
deliberately slow to believe the worst.

- **`health`** is an object with `state` (`pending`, `running`, `degraded`,
  `stopped`, `terminated` or `unknown`), `healthy`, an optional `message` and
  `reasons`. `running` with `healthy: false` is `InstanceUnhealthy`;
  `pending` is `InstancePending`; the others map one to one. The message
  and reasons reach the condition's message, so write them for an operator.
  The mapping is in [`InfrastructureHealthy`](../operator-guide/troubleshooting/conditions.md#infrastructurehealthy).
- **`provider_id`** is written once and then immutable. Return it as soon as
  the instance exists, and return **the same value every time**: a later
  change makes `OutputsValid=False`/`ProviderIDChanged`. It must equal the
  Node's `spec.providerID` exactly.
- **The two-sample rule.** If `provider_id` becomes `null` after the machine
  was provisioned, the first reading sets `InfrastructureHealthy=Unknown`
  with `ProviderIDMissing`. It is reported terminated only if a **later**
  refresh is also `null`. Reconciling the same output again is not a second
  sample. The rule exists so that a transient read, such as an eventually
  consistent cloud API, does not trigger remediation of a healthy machine.
  Design for it: when an instance is gone, return `null`, and keep returning
  `null` rather than a placeholder.

!!! tip "Do not invent a healthy state"

    A module that cannot tell should report `unknown`.

The health timeline and the provisioned rule are in
[Machine role](contract/v1alpha1/machine.md), and the remediation that acts on
unhealthy machines is in [Machine Remediation](../user-guide/remediation.md).

## Pool autoscaling

A pool autoscales through two annotations on the `MachinePool`:
`cluster.x-k8s.io/cluster-api-autoscaler-node-group-min-size` and
`-max-size`. Both must be present, parse as non-negative integers and
satisfy `min <= max`. If neither is set, autoscaling is off and
`spec.replicas` is the capacity. If one is missing, unparsable or `min >
max`, autoscaling is off and `AutoscalingActive=False`/`AutoscalingAnnotationsInvalid`
names the problem.

When it is on:

- The module receives `autoscaling = {enabled, min, max}`, and its
  `replicas` input is the **observed** capacity, clamped into the range, not
  `spec.replicas`.
- The module must scale **in the cloud**, within `[min, max]`, and
  **ignore changes** to the desired capacity, or each reconcile fights the
  cloud autoscaler. `tfcapi-lint` warns about a module that uses
  `var.autoscaling` without an `ignore_changes` on the desired capacity
  (`pool/autoscaling-ignore-changes`).
- The controller writes the observed `replicas` output back to
  `MachinePool.spec.replicas` and sets the annotation
  `cluster.x-k8s.io/replicas-managed-by: captf`. If another controller
  already owns that annotation with a truthy value, CAPTF leaves
  `spec.replicas` alone and reports `ReplicasManagedExternally`. Choose one
  owner.
- The Kubernetes Cluster Autoscaler is **not** supported on pools.

See [Machine Pools](../user-guide/machine-pools.md#choose-fixed-replicas-or-autoscaling)
and the [`autoscaling` input](contract/v1alpha1/machinepool.md#autoscaling-input).

## `import` and `moved` blocks

CAPTF does not block `import` and `moved` blocks. The runner reads a plan's
imports and moves, counts them separately from adds, changes and destroys,
shows them as `address (import)` or `address (update, move)`, and folds them
into the plan fingerprint. What that means in practice:

- **On the cluster under `Manual`, they need approval, except on the first
  apply.** A plan that only imports or moves is not empty, so it waits for
  approval like any change. The first apply of an object with no state is not
  gated, so a wrong id on a first-apply import adopts the wrong resource
  unattended. A plan with no changes, imports, moves or output changes needs
  none.
- **Under `Automatic`, they are not blocked.** The destructive-plan guard
  looks only for deletes and replaces, and an import or move is neither.
- **On machines and pools they apply unattended**, like everything else there.
- **They are not drift.** A drift check ignores imports and moves.

!!! warning "An `import` block with a wrong id adopts the wrong thing"

    Under `Manual`, read the plan before you approve. Also, no CAPTF
    documentation or test yet covers `import` blocks inside a module, so
    treat the pattern as untested.

Drive the ids
from a variable that defaults to empty, so the block can stay in the module.
An object that applied before and lost its state cannot run a module apply at
all, so adoption after a state loss needs a recreated object or a rebuilt state:
see [Total State Loss and Import](../operator-guide/runbooks/total-state-loss.md).

## Destroy safety and replaceable machines

- **A machine is replaced, never changed.** A `TerraformMachine`'s source,
  identity and variables are immutable; Cluster API rolls machines by
  creating a new one and deleting the old. Write a machine module so that
  creating it needs nothing from a sibling, and deleting it harms nothing
  shared. Keep per-machine state per machine.
- **Destroy runs from stored inputs.** A destroy renders from the durable
  inputs Secret, pinned to the image of the last apply, so it does not depend
  on the current Cluster or bootstrap Secret. Do not write a module whose
  destroy needs a value only the live Cluster has. See [The destroy
  Job](../concepts/deletion/destroy-job.md).
- **A destroy that fails retries forever.** A resource that cannot be
  deleted (a disk still attached, a security group still in use) stalls the
  deletion. Order dependencies so Terraform deletes in the right order, and
  see [Stuck Destroy](../operator-guide/runbooks/stuck-destroy.md) for the
  way out.
- **`prevent_destroy` is plain Terraform.** On the load balancer behind the
  control-plane endpoint it turns an approved replacement into a failed Job
  instead of a lost cluster. The same setting makes the cluster's own destroy
  fail, so deleting a cluster means lifting it first. Use it where the loss
  would be worse than the stalled delete, and write down how to lift it.
- **Do not depend on the controller's order.** The cluster destroys last,
  after its machines and pools are gone, but do not rely on timing: a module
  should tolerate a destroy that finds a resource already gone.

## Sensitive values

- **Mark secrets `sensitive = true` in the module.** A variable that arrived
  from a Secret is declared sensitive in the generated root, but a
  declaration in your module makes the value sensitive whatever its source.
  An output that refers to a sensitive value must itself be `sensitive =
  true`, or `plan` fails. See [Common
  inputs](contract/v1alpha1/common.md).
- **Never put credentials in the module.** They come from the identity, as
  environment variables and files. `tfcapi-lint` warns on a provider block that
  sets a credential-named argument to a literal (`module/provider-config`).
- **What the controller keeps out.** Status and events carry counts and
  addresses, never values. The runner redacts the values it knows about
  (credentials, sensitive variables, bootstrap data, sensitive plan values)
  from the Job's result and events. It cannot redact a secret a module
  derives and prints. See [What CAPTF keeps out of status, events and
  logs](../concepts/security-model.md#what-captf-keeps-out-of-status-events-and-logs).
- **Bootstrap data is sensitive.** `bootstrap_data` carries join tokens.
  Declare it `sensitive = true`; `tfcapi-lint` warns when you do not
  (`input/sensitive`).

## Test the module

1. **Start from the noop module.** It creates nothing in a cloud, and shows
   the contract end to end: [Your First Module](../getting-started/first-module.md)
   builds one. The published images and source are in
   [`captf-io/noop-modules`](https://github.com/captf-io/noop-modules).
2. **Lint the module** with `tfcapi-lint`, in strict mode, in CI. It needs
   neither `terraform` nor `tofu`:

    ```sh
    tfcapi-lint module --role cluster --strict ./cluster
    tfcapi-lint image <image-ref> --role cluster --strict
    ```

    The checks that most often catch design mistakes: `input/required`,
    `input/type`, `output/required` and `output/health` (the contract shape);
    `output/provider-id-list-shape` and `pool/autoscaling-ignore-changes`
    (pools); `output/endpoint-never-set` (a cluster that never sets an
    endpoint); `module/backend` and `module/cloud` (the controller owns the
    backend); `module/source-escape` and `module/tofu-shadow` (code the linter
    would not see); and `module/provider-config` (literal credentials). The full
    list is in [tfcapi-lint CLI](../reference/tfcapi-lint-cli.md#checks).
3. **Run it with both runtimes.** A module that validates under Terraform can
   fail under OpenTofu, or the reverse; `module/tofu-shadow` catches one cause.
   Initialize and validate under each.
4. **Try the lifecycle**, in a scratch management cluster: the first apply, an
   input change, a drift check, a machine delete and a destroy, and a state
   restore. Check each one leaves the object `Ready` and that the destroy
   leaves nothing behind. See [Disaster
   Recovery](../operator-guide/disaster-recovery.md#a-recovery-drill) for a
   drill.

!!! related "See also"

    - [Module Contract](contract/README.md) and its role pages: [cluster](contract/v1alpha1/cluster.md),
      [machine](contract/v1alpha1/machine.md) and
      [machine pool](contract/v1alpha1/machinepool.md).
    - [Image Contract](image-contract.md), [Runtime Environment](runtime-environment.md)
      and [tfcapi-lint](tfcapi-lint.md).
    - [Approvals and Gates](../concepts/approvals/README.md).
