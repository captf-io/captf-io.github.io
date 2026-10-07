---
description: "What a plan approval does and does not promise: apply-time behavior, the plan key, ungated kinds, cluster outputs and state surgery."
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/octagon-alert
subtitle: "What an approval cannot promise"
---

# Limits

The gates are a review step, not a sandbox. This page says what an approval
promises and what it does not, so you set your expectations and your module
design to match.

## An approval binds a plan, not the apply

The approval binds what the plan says will change, as far as the [plan hash
binds it](fingerprint.md). It cannot bind how the provider then carries that
change out at apply time: the API calls it makes, their order, retries, or
what the cloud does in response. A reviewed change can still fail halfway,
and a partial apply leaves the world different from the plan you read, which
is why the next attempt re-plans and may ask for a new approval.

## The plan key is readable by the module

The plan key is mounted into the Job that plans, and the runner's
ServiceAccount can read every Secret in its namespace (see [Security
considerations](../secret-management/security.md#the-runner-can-reach-every-secret-in-its-namespace)).
So a module image can read the key and compute any hash it likes. The
fingerprint protects against the world changing between your review and the
apply, and against a person approving something other than the plan they
read. 

!!! danger "A hostile module image can forge any hash"

    The fingerprint does not protect against it. Review the module you
    run, and keep modules you do not trust out of the namespace.

## What is guarded

The cluster has both gates. `TerraformMachine` applies are never gated. A
`TerraformMachinePool` apply is guarded in one case only: when it renders
cluster exports that differ from its last successful apply (see [Machine
pools](destructive-guard.md#machine-pools)). Destroy, restore, refresh and
drift Jobs are never gated on any kind. The reasons are structural: a machine
is immutable and Cluster API replaces it rather than changing it, and scaling
would otherwise wait on a person for every machine (see
[scaling](README.md#scaling-is-not-gated)). The consequence is that a machine
or pool module can do anything its credentials allow with no approval step,
apart from that one pool case. Keep shared and destructive
infrastructure, such as networks, load balancers and databases, in the
cluster module, where the gates apply, and keep machine and pool modules to
what is meant to come and go.

## Cluster outputs reach pools and machines

A cluster's exports feed the inputs of every machine and pool. An output
change in a cluster plan needs approval under `Manual`. After that apply
succeeds, the new exports change the inputs of each `TerraformMachinePool`,
which is mutable, and the pool applies them. That apply is **guarded**: if its
plan deletes or replaces anything, it stops and the change is **held**. The
pool applies bootstrap rotations with the exports of its last successful apply
until someone approves the change's plan. Any other input change guards the
change again and makes a new plan. See [Machine
pools](destructive-guard.md#machine-pools).

What the guard does not cover:

- **A pool that applied before the guard existed** has no record of its last
  exports until its next successful apply, and is unguarded until then.
- **Plans that only update in place** are not blocked, as for a cluster.
- **A `TerraformMachine` is immutable** and is not re-applied; its inputs are
  fixed once it is provisioned. Nothing guards a machine.
- **The pool apply waits for the cluster's Job** (the cluster operation gate),
  but that is a scheduling lock, not an approval.

!!! tip "Make a pool module defensive with prevent_destroy"

    Still make a pool module defensive with `lifecycle { prevent_destroy = true }`
    on what must never go: it fails even an approved plan.

## Approving is a patch on the plan

Approval authority is Kubernetes RBAC on `terraformplans`, by design (see [Who
can approve](operating.md#who-can-approve)). Approving needs no right on the
target, so the right to edit a spec and the right to approve can be held by
different people, and should be. Two things to keep in mind. `create` on
`terraformplans` equals approve, so grant it only to the manager and the
identity that runs `clusterctl move`. And RBAC alone cannot tell a harmless
plan from a destructive one; for that, add an admission policy (see
[Tiered auto-approval](operating.md#tiered-auto-approval)).

## Approvals do not cover state surgery

Restoring a state, abandoning an object and unlocking a state lock are not
approvals and are not gated: they act on whoever can annotate or patch the
object. 

!!! danger "A restore can make the controller forget resources it created"

    A restore rewrites the state, so a person with that right can do
    this. Treat these annotations as equal in weight to the right to edit
    the object.

A rebuild of a lost state, including imports, is a runbook, not an approval: see
[Total State Loss and Import](../../operator-guide/runbooks/total-state-loss.md).

!!! related "See also"

    - [Security Model](../security-model.md).
    - [Security considerations](../secret-management/security.md) for the
      Secrets behind these limits.
    - [Manual plan approval](manual-approval.md) and [The destructive-plan
      guard](destructive-guard.md).
