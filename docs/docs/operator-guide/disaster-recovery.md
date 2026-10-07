---
title: "Disaster Recovery for CAPTF"
description: "Recover from lost Terraform state, a lost namespace or a lost management cluster: what to back up outside the cluster, how to rebuild and how to rehearse."
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/hard-drive
subtitle: "Plan for lost state or clusters"
---

# Disaster Recovery

This page covers recovering from the loss of Terraform state, of a
namespace, or of the whole management cluster. It starts with what CAPTF
does and does not give you, then lists what to back up outside the cluster,
how to rebuild, and a drill to rehearse it.

!!! warning "Most of this page is untested guidance"

    Most of this page is **guidance derived from how the controller behaves**,
    not a tested procedure. CAPTF is pre-alpha, and no recovery has been run
    against a live management cluster. Where a step depends on a tool outside
    CAPTF (Velero, `kubectl`, `jq`) it is marked as guidance: check it in a
    scratch cluster before you rely on it. The drill at the end is how.

## What the in-cluster backups are not

CAPTF keeps up to `--state-backups` (default 5) copies of each object's
state as Secrets named `captf-state-backup-<suffix>-<serial>`. They are
useful for a state Secret that was deleted or damaged. They are **not**
disaster recovery:

- They are **in the same namespace**, so deleting or losing the namespace
  loses them with the state.
- They are **owned by the object**, so Kubernetes garbage-collects them when
  it goes, including after a finalizer is removed by hand.
- They are **taken after each write** by the controller, when it sees a new
  state serial. There is no copy taken before an apply, and a run of bad
  applies pushes the last good copy out of the window.
- **Anyone who can delete Secrets in the namespace can delete them**, and
  so can a module running in a Job.

See [Backups are not disaster
recovery](../concepts/secret-management/security.md#backups-are-not-disaster-recovery)
and [Backups and restore](../concepts/secret-management/backups.md). For
what the controller does with them when the state is lost, see [State
Restore](runbooks/state-restore.md).

## What to back up outside the cluster

Back up the things that cannot be recreated from the rest. The table says
what each CAPTF object is, how to select it, and what happens if it is lost.

| Object | Select by | If lost |
| --- | --- | --- |
| **State Secrets** `tfstate-default-<suffix>` and `-part-N` | Label `tfstate=true` | The state is gone: `StateReadable=False`/`StateLost` for an object that applied, no Job runs, a deletion is held |
| **State backups** `captf-state-backup-*` | Label `captf.io/state-backup=true` | No in-cluster restore source |
| **Durable and applied inputs** `captf-inputs-<kindshort>-<name>`, `captf-applied-<kindshort>-<name>` | Name prefixes `captf-inputs-` and `captf-applied-` (label `captf.io/managed=true` with the owner-kind label) | The `captf.io/applied` marker, the pinned digest and the pinned identity go; a `TerraformMachine` can no longer render a destroy (`DestroyFailed`) |
| **`Terraform*` objects** | The kinds | The spec is the module's inputs; without it nothing can be rebuilt |
| **`TerraformClusterIdentity`** (cluster-scoped) | The kind | Objects report `IdentityNotFound`; no Job, not even a destroy |
| **Identity source Secrets** | The Secret named by each identity's `spec.secretRef` | `SecretNotFound` on the identity and every object using it |
| **`variablesFrom` ConfigMaps and Secrets** | The labeled sources | `VariablesSourceNotFound`; mutable kinds stop |
| **Cluster API objects** (`Cluster`, `Machine`, `MachineDeployment`, `MachinePool`, control plane and bootstrap objects) | The kinds | The owners of the `Terraform*` objects |
| **Module images**, by digest | Your registry | A destroy needs the pinned image to exist |

Not worth backing up, because the controller re-creates them: the credential
mirror `captf-creds-*`, the plan key `captf-plankey-*`, the run and cluster
Leases, the per-run Secrets, the Jobs, and the runner ServiceAccount and
RoleBinding. Losing the plan key invalidates the hash of every plan that
waits for approval; the next reconcile makes a new plan to approve.

Notes on the selectors:

- `captf.io/managed=true` matches all of these Secrets and also Leases, the
  runner ServiceAccount and RoleBinding and the per-run Secrets. If you use
  it, exclude Leases and the `captf-run-*` Secrets. The per-run Secrets hold
  rendered variables and are transient.
- The state Secrets and the backups are plain Kubernetes Secrets: protect the
  backup as you protect the Secrets. See [No encryption at rest of its
  own](../concepts/secret-management/security.md#no-encryption-at-rest-of-its-own).
- The suffix in a Secret's name is derived from the namespace, the kind and
  the object's name, not from its UID, so it is the same after a restore.

### Two ways to take the copy

=== "etcd snapshot"

    **An etcd snapshot** captures everything, including owner-reference UIDs, so
    a restore returns the cluster to a point in time with nothing to repair. The
    cost is that it is the whole cluster at that moment.

=== "Per-namespace backup"

    **A per-namespace backup** (Velero or `kubectl`) is finer but has one trap:
    owner references. Every CAPTF Secret above, except the identity's, is owned
    by its `Terraform*` object, by UID. A restored Secret that still names the
    **old** UID has an owner that does not exist, and Kubernetes garbage
    collection deletes it. Restore the Secrets without their `ownerReferences`:
    CAPTF re-owns them. Each object's first unpaused reconcile with no active Job
    gives its state Secrets, backups, durable inputs and plan key one owner
    reference to the object's new UID, and replaces its old entry in the
    credential mirror, emitting an `OwnerReferencesRepaired` event. A Secret that
    still names the old UID would be repaired too if it lasted that long, but
    garbage collection normally deletes it first, and nothing is re-owned while
    the object is paused. Take the copy so that you can do this. For example,
    with `kubectl` and `jq` (guidance, not a tested procedure):

    ```sh
    ns=<ns>
    for sel in tfstate=true captf.io/state-backup=true; do
      kubectl get secret -n "$ns" -l "$sel" -o json \
        | jq 'del(.items[].metadata.ownerReferences,
                  .items[].metadata.uid,
                  .items[].metadata.resourceVersion,
                  .items[].metadata.creationTimestamp,
                  .items[].metadata.managedFields)' > "backup-$sel.json"
    done
    ```

    Do the same for each `captf-inputs-*` and `captf-applied-*` Secret. If you use Velero, check how
    your version restores `ownerReferences` before you rely on it, and test with
    one namespace.

How often to take the copy decides how much you lose. The state changes on
every apply, so a copy older than the last apply restores an out-of-date
state: see [After a restore](#after-a-restore).

## Rebuild a lost management cluster

Infrastructure that Terraform created keeps running when the management
cluster is lost; only the record of it is gone. The order below matters
because of how the controller treats a **new** object whose state it cannot
see.

!!! danger "A new object with no visible state creates a second set of resources"

    A new `Terraform*` object whose state Secret is missing and
    that shows no sign of an earlier apply reads as "never applied", and its
    first apply creates a **second** set of resources next to the live ones. The
    signs of an earlier apply are the `captf.io/applied` marker on the durable inputs
    Secret, an applied Secret (`captf-applied-*`), or any state backup. With any of them
    the missing state reads as lost and nothing runs. So restore the Secrets
    **before** the objects can reconcile, or restore the objects paused.

1. **Install the platform.** Create a management cluster, install cert-manager
    and Cluster API, and install CAPTF at the same version, so the CRDs match
    the backed-up objects. See [Installation](installation.md).
2. **Restore the identities and credentials.** The
    `TerraformClusterIdentity` objects and their source Secrets.
    `variablesFrom` sources go back too.
3. **Restore the Cluster API objects.** The `Cluster` and the machine owners
    come first: a `Terraform*` object whose owner is missing waits at
    `DependenciesReady`, and one whose owner reference names a UID that no
    longer matches reports `OwnerMismatch` and runs nothing. Restore them
    with the Cluster paused (`spec.paused: true`), so nothing starts yet.
4. **Restore the Secrets**: the state, the backups and the durable inputs,
    **without their `ownerReferences`**. CAPTF adds the owner references back
    on each object's first unpaused reconcile.
5. **Restore the `Terraform*` objects, paused.** Add the
    `cluster.x-k8s.io/paused` annotation to each, or keep the Cluster paused.
    A paused object runs bookkeeping only.
6. **Check before you unpause.** For each object: `kubectl get` shows the
    state Secret and the durable inputs; the suffix in
    `status.stateSecretSuffix` matches the Secret names.
7. **Unpause one object, then the rest.** Start with a machine or a small
    cluster. Afterwards look for an `OwnerReferencesRepaired` event, or for
    owner references to the new UID on its Secrets. On the first reconcile the
    controller reads the state and compares the inputs hash the state recorded
    with the hash of the current inputs:
    - They match when the spec, the module image and CAPTF's rendering are
      unchanged since the last apply. **No apply runs.** Drift checks follow
      on their schedule.
    - They differ when anything changed. A mutable kind (a cluster or pool)
      applies; under `applyPolicy: Manual` it plans and waits for you.

The repair skips an object while it is paused, and skips its state Secrets
while a Job holds the run lease, because the backend's own write would
conflict; it retries on the next reconcile. A repair that fails is logged and
tried again, and never fails the reconcile. A normal destroy removes the
state, the durable inputs and the plan key by label, whoever owns them.

### After a restore

- **A state older than the infrastructure.** If the state predates changes
  Terraform made after it, the live resources it does not list are untracked.
  Run a drift check (`drift.action: Report`) before you let anything apply,
  and compare the report with the cloud's own inventory.
- **`spec.deletionPolicy`** is part of the spec, so a restored object has the
  value its manifest carries. Check it before you delete a restored object:
  `Retain` leaves the infrastructure running.

## Move instead of rebuild

If the old management cluster is still running, `clusterctl move` is the
supported way to bring objects to a new one. It carries the state Secrets,
the backups and the durable and applied inputs, and it rewrites owner references for
you. A file-level restore leaves that to CAPTF's own repair, above. You
must copy the identity source
Secrets yourself. See [clusterctl move](runbooks/move.md) and [clusterctl
move](../concepts/deletion/move.md) for what moves and what does not.

## Recover from total state loss

State is gone, with no external copy and no usable in-cluster backup. Choose
by what you have:

| You have | Do |
| --- | --- |
| An in-cluster backup | Annotate `captf.io/restore-state=<serial>`. See [State Restore](runbooks/state-restore.md) |
| An external copy of the state Secrets | Restore them without `ownerReferences`, as above; the next reconcile reads them |
| A state file from elsewhere | `terraform state push` it to the object's backend, then reconcile; see [Manual recovery](runbooks/state-restore.md#manual-recovery-with-no-backup) |
| Nothing | Re-import, or retain and recreate: see [Total State Loss and Import](runbooks/total-state-loss.md) |

**Re-import** and the other routes, with commands and the module side, are in
the [Total State Loss and Import runbook](runbooks/total-state-loss.md).
In short: for an object that applied before, every Job is held while its state
is gone, so a module's `import` blocks cannot run; rebuild the state from a
workstation (route 1), or retain the object, clear the retained state and recreate it with
`import` blocks (route 2). An object that never applied can import on its first apply.
That flow has not been exercised end to end, and whichever route you use, run a
drift check before anything applies.

!!! danger "Retain leaves the infrastructure running"

    **Retain** applies to a deleting object. If the object must go and its state
    is lost or unreadable, `spec.deletionPolicy: Retain` releases the finalizer
    without a destroy and leaves the infrastructure running, with nothing
    managing it. Adopt the retained state later or clean the infrastructure up
    through the cloud. See [Held deletions](../concepts/deletion/held.md#retain)
    and [Retain and Adopt](../concepts/deletion/retain.md).

## What a deleted namespace loses

Every Secret CAPTF keeps is in the object's namespace, so a deleted namespace
removes the state, **the backups**, the durable inputs, the plan key, the
mirror, the Leases, the Jobs and the runner ServiceAccount, while the cloud
resources stay. An object whose status marks it provisioned and whose state
is gone is held (`StateLost`) and can be retained. A *moved* object looks
never-applied once its Secrets are gone; see [Terminating
namespaces](../concepts/deletion/namespaces.md#the-known-limit). Only the
cluster-scoped identity and a source Secret in another namespace survive.

## A recovery drill

Rehearse on a scratch management cluster with the `noop` module, which
creates nothing in a cloud, so the drill costs nothing and cannot damage
anything. Repeat it after each CAPTF upgrade and when you change the backup
method.

1. **Set up.** Install CAPTF in a scratch cluster. Create an identity, a
    `TerraformCluster` and a `TerraformMachine` on the `noop` module and wait
    for `Ready=True`.
2. **Back up** with the method you will use in production: the etcd snapshot,
    or the per-namespace export.
3. **Destroy the cluster**, or delete the namespace with the objects in it.
4. **Restore** following [Rebuild a lost management
    cluster](#rebuild-a-lost-management-cluster) on a fresh scratch cluster.
5. **Verify.** Each object reaches `StateReadable=True` and `Ready=True`;
    **no `apply` Job started** (`kubectl get jobs`, and the `JobCreated`
    events); a drift check reports `NoDrift`.
6. **Break it on purpose.** Restore once with the Secrets' original
    `ownerReferences` and watch them get collected; restore once with objects
    unpaused and no state, and watch what happens when the durable inputs are
    present and when they are not. You learn the failure modes in a place
    where they are harmless.
7. **Record** the time it took and what you changed in this page's steps for
    your environment.

!!! related "See also"

    - [Production Readiness](production-readiness.md).
    - [Secrets](secrets.md) and [Operator files and
      settings](../concepts/secret-management/operator-files.md#what-to-back-up-outside-the-cluster).
    - [Stuck Destroy](runbooks/stuck-destroy.md) and
      [Unreadable State](runbooks/state-unreadable.md).
    - [Deletion and Teardown](../concepts/deletion/README.md).
