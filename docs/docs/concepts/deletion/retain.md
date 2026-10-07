---
description: "Delete a TerraformCluster, machine or pool without a destroy, keep its state for later, and adopt the running infrastructure with a new object."
git_creation_date_localized: "October 6, 2026"
git_revision_date_localized: "October 6, 2026"
git_creation_date_iso: "2026-10-06"
git_revision_date_iso: "2026-10-06"
authors:
  - "The CAPTF Authors"
icon: lucide/archive
subtitle: "Delete, keep, adopt later"
---

# Retain and Adopt

Deleting a `TerraformCluster`, `TerraformMachine` or `TerraformMachinePool`
normally destroys what its module created. `spec.deletionPolicy: Retain`
deletes the object without a destroy and keeps what CAPTF knows about the
infrastructure, so a later object can manage it again. This page covers
what Retain keeps, what it releases, and how a new object adopts the
retained state, or refuses to until you say so.

## Setting the policy

`spec.deletionPolicy` is `Destroy` or `Retain`. It is mutable at any time,
also after the deletion has started:

```sh
kubectl patch terraformmachine <name> -n <namespace> --type merge \
  -p '{"spec":{"deletionPolicy":"Retain"}}'
```

An unset policy inherits, like other operational policy ([the inheritance
rule](../kinds.md#the-inheritance-rule)): a machine or pool takes its
cluster's `spec.defaults.deletionPolicy`, else the `TerraformCluster`'s own
`spec.deletionPolicy`, else `Destroy`. A `TerraformCluster` uses only its
own value. Machine templates are immutable, so set the policy for a
cluster's machines on the `TerraformCluster` rather than in the template:
that needs no rollout.

```yaml title="Keep everything a cluster created when it is deleted"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformCluster
spec:
  deletionPolicy: Retain
```

The fields are documented in [Common
Fields](../../reference/resources/common-fields.md#deletion-policy).

## What Retain keeps

On deletion with `Retain`, no destroy Job runs. Once no Job of the object
is running, the controller:

| What | Retain does |
| --- | --- |
| The state Secrets, every chunk | Kept |
| The state backups | Kept |
| The durable and applied inputs Secrets | Kept |
| The state lock Lease | Deleted |
| The plan key, the run and write leases | Deleted |
| The object's place among the credential mirror's owners | Dropped, as on every deletion |
| The finalizer | Removed |

Each kept Secret loses its owner reference to the object, so Kubernetes
does not garbage-collect it with the object, and gets the label
`captf.io/retained-from-uid` with the object's `metadata.uid`. The
backend's labels stay, so Terraform and OpenTofu still read the state, and
the `clusterctl.cluster.x-k8s.io/move` label stays, so a later `clusterctl
move` carries the Secrets along. A `Normal` event `InfrastructureRetained`
counts what was kept.

The cloud infrastructure keeps running and is managed by nothing until an
object adopts it. Every step is idempotent: a pass cut short is finished by
the next.

```sh
kubectl get secrets -n <namespace> -l captf.io/retained-from-uid=<uid>
```

## What Retain releases

Retain is decided before any restore or destroy, as soon as no Job runs.
Setting it on a deletion that is stuck releases it, whatever holds it:

- the state is lost or unreadable (a [held deletion](held.md));
- the last destroy failed;
- the destroy cannot start: the inputs Secrets (durable and applied) are gone, the identity no
  longer allows the namespace or no longer exists, or the runner
  credentials cannot be prepared.

The messages of those conditions name `spec.deletionPolicy: Retain` as the
way out. Unlike stripping the finalizer by hand, nothing is lost: the state
that exists, its backups and the inputs stay, ready to be adopted or
restored.

!!! warning "Retain never destroys, even when the destroy would succeed"

    With `Retain` set, a deletion runs no destroy at all. Remove the
    infrastructure through the cloud provider, or adopt it and delete the
    adopting object with `Destroy`, if you want it gone.

A paused object never retains, as it never destroys, and a
`TerraformCluster` still waits for its machines and pools to go first.

## A recreated object holds

A state Secret's name and a backup's selector come from the object's
namespace, kind and name, not its UID. So a new object of the same kind,
namespace and name finds the Secrets an earlier one retained. It never
adopts them silently: they describe infrastructure that may still be
running, and the new object may be meant to build something else.

Instead the object holds: `StateReadable` is `False` with reason
`RetainedStateFound`, a `RetainedStateFound` `Warning` event fires, and the
message names the retaining UID. While it holds, no Job runs, no state is
adopted, backed up or read into status, and none of the retained Secrets
gets an owner reference. The hold has two exits: adopt, or discard.

## Adopting retained state

Set `spec.adoptRetainedState: true` on the new object:

```yaml
spec:
  adoptRetainedState: true
```

The controller removes the `captf.io/retained-from-uid` label from every
retained Secret it found and emits `RetainedStateAdopted`. On the next
reconcile it owns them, reads the state as the object's own and carries on
from there: a machine whose state reads becomes provisioned without a new
apply, a cluster or pool applies only if its inputs differ from the
state's. The field is never inherited, and it stays set; leave it or clear
it as you like.

!!! note "Adopt with the same inputs"

    The adopted state was written by the earlier object's inputs. A
    `TerraformCluster` or `TerraformMachinePool` whose spec differs applies
    the difference, guarded as any change is. A `TerraformMachine` is
    immutable and keeps the adopted inputs records, image and identity.

## Discarding retained state

To start afresh instead, delete the retained Secrets before or after you
create the new object:

```sh
kubectl delete secret -n <namespace> -l captf.io/retained-from-uid=<uid>
```

The infrastructure they described keeps running, unmanaged. Delete it
through the cloud provider.

## Deleting while held

Deleting an object that holds on another object's retained state removes
its finalizer at once, without a Job, whatever its own `deletionPolicy`.
The object never created anything, and the retained Secrets are left
exactly as they were: never deleted, owned or relabeled. The
`FinalizerRemoved` event names the retaining UID.

!!! related "See also"

    - [Held Deletions](held.md#retain)
    - [Cleanup and Garbage Collection](cleanup.md)
    - [Stuck Destroy](../../operator-guide/runbooks/stuck-destroy.md#retain-instead)
    - [Annotations, Labels and Finalizers](../../reference/annotations-labels.md)
    - [Conditions](../../reference/conditions.md#statereadable) and
      [Events](../../reference/events.md)
