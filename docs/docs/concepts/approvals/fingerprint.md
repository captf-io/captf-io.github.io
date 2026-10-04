---
description: "What goes into the p2: plan hash an approval names, what it binds and what it leaves out, so you know what an approval covers."
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-02"
authors:
  - "Steven Crothers"
icon: lucide/fingerprint
subtitle: "What an approval is tied to"
---

# What the Plan Hash Binds

The value you approve under `applyPolicy: Manual` is `status.plan.planHash`,
a string that starts with `p2:`. It is a fingerprint of what the plan will
do. This page defines what goes into it and why, so you can tell what an
approval covers.

## Construction

The runner builds the hash from one line per change:

```text
<name>|<actions>|<hex HMAC-SHA256 of the canonical effect>
```

- `<name>` is the resource address, or `output.<name>` for an output.
- `<actions>` are the plan's actions, comma-joined, in plan order (so the
  two orders of a replacement differ).
- The last field is a keyed HMAC of the change's *effect*, described below.

The lines are sorted and joined with newlines, and the hash is `p2:` and the
hex SHA-256 of that text. A resource appears when its action is not a
no-op, or when it carries an import, or a moved-from address, since an
import and a move are changes even where nothing else is. An output appears
when its change is not a no-op.

The HMAC key is the per-object plan key (see [Run inputs and the plan
key](../secret-management/run-inputs.md#the-plan-key)). Because the hash is
keyed, reading `status.plan.planHash` reveals nothing about any value, and
the same plan hashes differently for two objects. A plan or approved-apply
Job whose key is missing or shorter than 32 bytes fails before any step
runs, so it cannot produce an unkeyed hash.

## The effect, by kind of change

What each line's HMAC covers depends on the action. The effect is serialized
as canonical JSON: keys sorted, empty fields omitted, and numbers kept as
the literals Terraform wrote.

| Change | What the effect contains |
| --- | --- |
| **Update or replace** | Only the attributes the change touches, as leaf paths with their old and new values; the paths whose value is unknown until apply; changes in sensitivity; whether a value is absent or null; and whether a path step is a list index or a map key |
| **Create or read** | The planned object, with its unknown and sensitive markers |
| **Delete or forget** | Nothing about the resource: the address and the action are all that identify it |
| **Import** | What the import imports (the identifier or identity) |
| **Move** | The address the resource moves from |
| **Output** | The same rules as a resource, under `output.<name>` |

A delete, forget or no-op line still carries any import or move on it.

## What this means for approval

**An approval binds values, not only addresses.** A plan that changes the
same resources to different values hashes differently and needs its own
approval. A new image tag, a different CIDR or a changed count each changes
the hash.

!!! warning "Untouched attributes are not part of the hash"

    For an update, only leaf paths that differ between the old and new
    object count. Attributes the change leaves alone, such as an
    autoscaler's desired capacity under `ignore_changes` or a Kubernetes
    `resourceVersion`, can move between your review and the apply without
    invalidating the approval. Without this rule, any busy object would
    force a re-approval at every apply.

**Unknown values are bound as unknown.** A value the provider will compute
at apply time appears in the effect as "unknown after apply", not as a
value. The approval covers that the attribute will be computed, not what it
will become.

**Sensitive values are bound but hidden.** A change from sensitive to not
sensitive changes the hash, and the value itself stays inside the HMAC.

**Imports and moves always need approval.** They are changes even with no
other difference, so a plan whose only change is an `import` or a `moved`
block waits for approval.

**Output changes need approval.** An output that changes appears in the
hash, and `status.plan.outputChanges` counts them. Cluster outputs feed
machines and pools; see [Limits](limits.md#cluster-outputs-reach-pools-and-machines).

## What the hash does not bind

It does not bind how the provider carries the change out. A reviewed
update to a security group is bound to its old and new attributes, not to
the API calls the provider makes, their order, or what the cloud does with
them. It does not bind anything the module does outside the plan, such as
provisioners that reach elsewhere. See [Limits](limits.md).

## The empty plan and old hashes

A plan with no change at all has a fixed hash (`p2:` followed by the SHA-256
of the empty string), and an apply for it needs no approval.

A hash that does not start with `p2:` is a plan recorded by an older
release (`p1:`). The controller re-plans it automatically and the approval
is then given again, against the new hash. An approval annotation written for
a `p1:` hash does not match.

## Drift is classified separately

Drift detection does not use this hash. It counts resources by action only,
so an import or a move alone is not drift, and neither is an output change.
That is why a drift check can report no drift while a `Manual` plan still
has something to approve.

!!! related "See also"

    - [Manual plan approval](manual-approval.md).
    - [Drift](../../user-guide/drift.md) and [Drift and
      Health](../drift-and-health.md).
    - [Limits](limits.md).
