---
description: Understand what CAPTF's handling of Secrets does and does not protect, and where the trust boundaries lie.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/shield
subtitle: "Risks and how to reduce them"
---

# Security Considerations

This page states what the way CAPTF keeps Secrets does and does not
protect, so you can decide where to run which module. The wider threat
model, including images, RBAC for the Terraform objects and Pod Security
Admission, is in the [Security Model](../security-model.md); this page is
about the Secrets in this chapter.

## The runner can reach every Secret in its namespace

The Job runs as `captf-runner`, whose ClusterRole grants `get`, `list`,
`create`, `update` and `delete` on Secrets in the namespace (see [Inside the
Job](job.md#serviceaccount-and-rbac)). The state backend needs those verbs,
and Kubernetes RBAC cannot narrow them to the state Secrets, because the
chunk names are dynamic. So the runner, and with it the module image and
any provider or program the module runs, can read, overwrite and delete
every Secret in that namespace: the state, the backups, the inputs and the
plan keys of other objects, and the credential mirrors.

!!! danger "The trust boundary is the namespace and the module image publisher"

    The trust boundary is therefore the **namespace** and the **publisher of
    the module image**. A module in a namespace is trusted with everything
    in it. Put modules you do not fully trust in their own namespaces, with
    their own identity that allows only that namespace, and do not share a
    namespace between tenants.

## The plan key does not protect against a hostile module

(See also [Limits](../approvals/limits.md) for the approval gates.)

The plan key is readable by the module (it is mounted into the Job that
plans). The `p2:` plan hash is a keyed fingerprint: it detects that the
plan changed between the review and the apply, and it hides the planned
values from anyone who can read `status.plan`.

!!! warning "Review the module you approve, not only its plan"

    The plan key does not defend against a module image that wants to lie
    about its plan, because that image can read the key and compute the
    hash it likes.

## Backups are not disaster recovery

State backups are copies taken after each write, in the same namespace,
owned by the object. They help with a state Secret that was lost or
damaged. They do not help when:

- **The object goes away.** Deleting the object, or removing its finalizer
  by hand, garbage-collects every backup with it.
- **The namespace or cluster goes away.** They are Secrets in that
  namespace.
- **Bad applies pile up.** Each new serial adds a backup and the oldest
  complete set beyond `--state-backups` (default 5) is pruned, so a run of
  bad applies can push the last good state out.
- **Someone with Secret access acts.** The runner can delete them, as above,
  and so can anyone with the right in the namespace.

Back the namespace up outside the cluster; see [What to back up outside
the cluster](operator-files.md#what-to-back-up-outside-the-cluster).

## No encryption at rest of its own

CAPTF does not encrypt the Secrets it keeps. The state, the inputs with
their bootstrap data and variable values, and the credential mirrors are
stored as the API server stores any Secret. Enable encryption at rest for
Secrets on the management cluster (see [Encrypting Secrets at
rest](operator-files.md#encrypting-secrets-at-rest)) and limit who can read
Secrets. OpenTofu's client-side state encryption is not supported: an
encrypted state reports `StateReadable=False`/`StateEncrypted`.

## Credentials arrive twice and in full

The Job mounts every key of the credentials mirror as a file and also
injects it as an environment variable, so the Terraform process, its
providers and anything the module runs see all of it, whether or not the
module uses each key. Put only what the module needs in an identity's
source Secret, and prefer short-lived credentials where the cloud supports
them. The runner removes `TF_*` and `KUBE_*` keys from the environment so a
credential Secret cannot steer Terraform itself (see
[Credentials](credentials.md#delivery-to-the-runtime)); that is a guard
against a mistake, not a boundary against the module.

## Rotation is not instant

A change to the source Secret reaches the mirror on the next reconcile of an
object that uses it, which takes up to the manager's `--sync-period` (ten
minutes by default). A Job already running keeps its old credentials. After
revoking a credential in the cloud, expect Jobs started in that window to
fail with the old one, and to pick up the new one on the next run. Narrowing
`allowedNamespaces` takes effect the same way, at the next reconcile.

## What CAPTF keeps out of logs

The runner replaces known secrets with `(sensitive)` in failure summaries,
events and logs, and CAPTF never logs state or inputs. This is best effort:
it cannot recognize a secret it was not told about, so do not treat it as a
reason to put sensitive data in places Secrets would not go. See [What CAPTF
keeps out of status, events and
logs](../security-model.md#what-captf-keeps-out-of-status-events-and-logs).

!!! related "See also"

    - [Security Model](../security-model.md).
    - [RBAC](../../operator-guide/rbac.md).
    - [Secrets](../../operator-guide/secrets.md).
