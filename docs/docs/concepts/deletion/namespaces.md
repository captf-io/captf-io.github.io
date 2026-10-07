---
title: "Deletion in a Terminating Namespace"
description: What a deletion can still finish in a terminating namespace, why a destroy waits there, and what the namespace takes with it.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/folder-x
subtitle: "Deleting inside a dying namespace"
---

# Terminating Namespaces

Deleting a namespace deletes everything in it, including the `Terraform*`
objects and every Secret CAPTF keeps for them. The cloud resources are not
touched. This page explains what a deletion can still do while its
namespace is terminating, and what the namespace takes with it.

## What can still finish

Kubernetes refuses to create new objects in a terminating namespace. A
destroy needs new objects: a Job, its per-run Secret, and often the runner
ServiceAccount, its RoleBinding and the credential mirror. So the controller
sorts a deleting object by whether it needs a Job at all.

| Situation | Needs a Job | Result |
| --- | --- | --- |
| The object never applied and has no state | No | The finalizer comes off at once |
| Held on lost or unreadable state | No | Held; [abandon](held.md#abandon) releases it |
| Abandoned | No | The finalizer comes off at once |
| A destroy of readable state | Yes | Waits, as below |
| A restore of a held state | Yes | Waits, as below |

The credentials a deleting object needs are prepared only for a Job that is
about to start, so the first three never wait on them. The reconcile does
not treat a credential failure as an error for a deleting object: the
namespace lifecycle would reject the creation again on every retry. The
object records the failure in its credential conditions instead.

## A destroy that waits

When the credentials cannot be prepared, the pass does not start the Job.
It sets the `Deleting` condition's message to `The destroy Job waits for its
credentials: <condition> is <status> (<reason>)` and requeues every 30
seconds. The named condition is the first of `IdentityAllowed`,
`CredentialsMirrored` and `RunnerRBACReady` that is not `True`. A restore
says `restore` where the message says `destroy`.

If the credentials already exist, the Job create itself is a create in a
terminating namespace, which the API server rejects. The reconcile reports
the error and controller-runtime retries it with backoff. A rejected create
gives the run and cluster leases back, so nothing else waits on a Job that
does not exist.

Either wait is a case the abandon annotation releases, with the cause `it
waits for its credentials`. Where the namespace deletion has already removed
the state Secrets, the object is held, not released:
`status.initialization.provisioned` still marks it as applied, so the
missing state reads as `StateLost`, not as nothing to destroy.

## What goes with the namespace

Every Secret CAPTF keeps is namespaced, so a deleted namespace removes:

- the state Secrets and their backups,
- the durable inputs Secret (and with it the `captf.io/applied` marker),
- the plan key and the credential mirror,
- the Jobs, their pods and their per-run Secrets,
- the run and cluster Leases and the state lock Lease,
- the runner ServiceAccount and RoleBinding.

The credential **source** Secret named by a `TerraformClusterIdentity` lives
in whichever namespace the operator put it, and the identity itself is
cluster-scoped; neither goes unless that namespace is the one deleted.

### The known limit

The applied marker is the only thing that tells a moved object that
applied from one that never did, because status is not moved (see
[`clusterctl move`](move.md#what-does-not-move)).

!!! danger "Deleting a moved object's namespace can orphan its cloud resources"

    When the namespace of a **moved** object is deleted, the marker goes
    with the Secret, the state and the backups. The object, now without
    any of the four [ever applied](held.md#ever-applied) signals, looks
    like one that never applied, and its finalizer comes off with nothing
    destroyed.

An object that was not moved keeps `provisioned` in its status and is held
instead.

Move first, and delete the source namespace only when the target has taken
over.

!!! related "See also"

    - [Lifecycle walkthroughs: namespace
      deletion](../secret-management/lifecycle.md#namespace-deletion).
    - [Stuck Destroy: terminating
      namespaces](../../operator-guide/runbooks/stuck-destroy.md#terminating-namespaces).
    - [Cleanup and garbage collection](cleanup.md).
