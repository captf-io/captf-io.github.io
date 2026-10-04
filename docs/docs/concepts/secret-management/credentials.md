---
description: Follow a credential from the source Secret through the per-namespace mirror to the Job, including rotation and revocation.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "Steven Crothers"
icon: lucide/key
subtitle: "How credentials reach a Job"
---

# Credentials

A Job never reads the operator's credentials Secret. The manager copies it
into the object's namespace, and the Job gets that copy. This page covers
the pieces and how a credential change propagates. For creating an
identity and choosing its namespaces, see [Identities and
Credentials](../../user-guide/identities.md).

## The pieces

- **The source Secret.** Any name, in any namespace, created and owned by
  the operator. CAPTF never writes it. It carries no move label, so
  `clusterctl move` does not carry it (see [`clusterctl
  move`](../../operator-guide/runbooks/move.md)).
- **The `TerraformClusterIdentity`.** A cluster-scoped object that names the
  source Secret in `spec.secretRef` and the namespaces that may use it in
  `spec.allowedNamespaces`. It carries no credential data.
- **The mirror**, `captf-creds-<identity>`, in each allowed namespace where
  an object uses the identity. It is an `Opaque` Secret with a copy of the
  source's data and:
    - labels `captf.io/mirrored=true` and `captf.io/managed=true`;
    - annotations `captf.io/source-hash` (a SHA-256 over the source's data)
      and `captf.io/identity` (the identity's name);
    - one non-controller owner reference per `Terraform*` object that uses it,
      with `blockOwnerDeletion` unset. A reference to an earlier UID of an
      object is replaced on its next reconcile.

A name over 253 characters is shortened to `captf-creds-` and 16 hex
characters of a hash.

## Who may point an identity at a Secret

Creating an identity, changing `spec.secretRef`, or widening
`spec.allowedNamespaces` makes the admission webhook run a
`SubjectAccessReview`: the requesting user must be able to `get` the named
Secret. An unset `allowedNamespaces` allows no namespace, and `{}` is
rejected as ambiguous; `selector: {}` allows every namespace. Without the
check, a role that may manage identities but not read Secrets could use an
identity to have the manager mirror a Secret into a namespace it can read.
See [Identities and Credentials](../../user-guide/identities.md#create-the-identity).

## When the mirror is written

The manager makes sure the mirror is current:

- on every reconcile of every non-deleting object that uses the identity;
- just before it creates a deletion Job, so a destroy has credentials.

Each time, it reads the source Secret uncached, hashes its data and
compares the hash with the mirror's `captf.io/source-hash`. If they differ
it rewrites the mirror's data. That is the only way a rotation reaches the
mirror.

## Rotation

Nothing watches the source Secret. A rotated credential reaches the mirror
on the next reconcile of any object that uses it, which is bounded by the
manager's `--sync-period` (default ten minutes). A Job that is already
running keeps the credentials it started with; the next Job gets the new
ones. The identity's own controller only reports status: it re-reads the
source every five minutes to set the identity's `Ready` condition and
`status.namespaces`, and does not copy anything.

## Revocation

If the identity stops allowing a namespace, because you narrowed
`allowedNamespaces` or relabeled the namespace, the manager deletes that
namespace's mirror on the next reconcile and the objects there report
`IdentityAllowed=False`/`NamespaceNotAllowed`. A destroy that needs the
identity then waits with `ApplyJobSucceeded=False`/`IdentityNotAllowed` and
requeues; the way out is to allow the namespace again or to [abandon the
infrastructure](../../operator-guide/runbooks/stuck-destroy.md#abandon-instead).

When the last object using the mirror is removed, cleanup removes its own
owner reference and deletes the mirror. You cannot delete an identity while
any object uses it: the delete webhook refuses until `status.namespaces` is
empty.

## Conflicts

If a Secret named `captf-creds-<identity>` already exists and is not a
mirror, the manager never overwrites it. It reports
`CredentialsMirrored=False` with `MirrorFailed`. Rename or remove the
Secret that is in the way.

## Delivery to the runtime

The Job gets the mirror two ways at once:

- `envFrom`, so every key becomes an environment variable;
- a read-only mount at `/var/run/captf/credentials`, mode `0440`, one file
  per key.

!!! warning "Every key in the source Secret reaches the Terraform process"

    Anything in the source Secret reaches the Terraform process as an
    environment variable, whether or not the module uses it.

The runner removes
keys starting with `TF_` or `KUBE_` from the environment, except the three the
Job sets itself (`TF_IN_AUTOMATION`, `TF_INPUT` and `KUBE_NAMESPACE`).
Otherwise a key such as `TF_WORKSPACE` or `TF_VAR_x` could move the state or
override the rendered inputs. A dropped key is still present as a file. More
on the environment is in [Inside the Job](job.md#environment) and the [runtime
environment](../../module-author/runtime-environment.md).

!!! related "See also"

    - [Identities and Credentials](../../user-guide/identities.md).
    - [Identities and credentials runbook](../../operator-guide/runbooks/identity-and-credentials.md).
    - [Security considerations](security.md).
