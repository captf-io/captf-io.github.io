---
description: See how state Secrets are named, labeled, chunked, read, checked and attached to the object by the manager.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/file-lock
subtitle: "How state Secrets are stored"
---

# Terraform State Secrets

The state of every `TerraformCluster`, `TerraformMachine` and
`TerraformMachinePool` lives in Secrets in the object's own namespace,
written by Terraform's or OpenTofu's `kubernetes` backend from inside the
Job. This page covers how those Secrets are named, found, read and
checked, and how the manager attaches them to the object. The higher-level
description is in [Terraform State](../state.md); this page adds the
mechanics.

## The backend

The rendered root module declares an empty `terraform.backend.kubernetes`
block. Everything the backend needs arrives on the command line of
`init`:

```text
init -backend-config=secret_suffix=<suffix> \
     -backend-config=namespace=<ns> \
     -backend-config=in_cluster_config=true \
     -backend-config=labels=<HCL map>
```

The backend therefore authenticates with the Job's own ServiceAccount (see
[Inside the Job](job.md#serviceaccount-and-rbac)), and the workspace is
always `default`: the runner drops `TF_WORKSPACE` from the environment.

## Names and the suffix

The suffix is the first 16 hex characters of
`sha256(<namespace>/<kind>/<name>)`, a hyphen and `c`, `m` or `mp`. It
depends on names, never on the UID, so it survives `clusterctl move`, and
it never ends in `-<digits>`, because the backend parses a chunk index from
a trailing number.

| Secret or Lease | Name |
| --- | --- |
| Base state Secret | `tfstate-default-<suffix>` |
| Further chunks | `tfstate-default-<suffix>-part-N` |
| Lock Lease | `lock-tfstate-default-<suffix>` |

`status.stateSecretSuffix` records the suffix for you to read; the
controller derives it again every time and never reads it back.

## Labels

The `labels` backend setting makes the backend stamp a fixed set of labels
on every chunk and on the lock Lease, next to its own `tfstate=true`,
`tfstateSecretSuffix` and `tfstateWorkspace=default`:

| Label | Value |
| --- | --- |
| `captf.infrastructure.cluster.x-k8s.io/owner-kind` | The object's kind |
| `captf.infrastructure.cluster.x-k8s.io/owner-name` | The object's name; a 16-hex-character hash of it if it is over 63 characters |
| `cluster.x-k8s.io/cluster-name` | The owning Cluster's name, with the same hashing |
| `captf.io/managed` | `true` |
| `clusterctl.cluster.x-k8s.io/move` | Empty: the move marker |

!!! warning "The label map must never change for an existing object"

    The backend lists its chunks with a selector made of the whole map, so
    a changed map would stop matching the Secrets already there and the
    state would appear to vanish.

## Chunking and compression

Each Secret holds the state gzip-compressed under the data key `tfstate`.
Terraform splits a state that compresses past about 1 MiB into further
Secrets; OpenTofu 1.12 writes a single Secret and does not chunk. The reader
accepts either shape. See [State Storage: Terraform and
OpenTofu](runtimes.md) for the two backends side by side, what happens
when an OpenTofu state outgrows its Secret, and switching runtimes.

## How the manager reads state

The reader (the manager's own, not Terraform's) works in this order, and
each failure maps to a `StateReadable` reason:

1. It lists Secrets by the backend selector: `tfstate=true`, the suffix and
   the `default` workspace. State Secrets are read uncached, straight from
   the API server.
2. It orders the base Secret and the `-part-N` chunks. A gap, a duplicate,
   an unexpected name or a base Secret without the `tfstate` key is
   `StateInconsistent`.
3. It refuses more than 32 Secrets, or more than 64 MiB once decompressed:
   `StateCorrupt`. The decompression stops at the first gzip member, so a
   trailing chunk left behind when the state shrank is ignored rather than
   misread.
4. If the document carries an `encryption_version`, it is OpenTofu's client
   state encryption, which CAPTF cannot read: `StateEncrypted`. This check
   comes first.
5. The state `version` must be 4. Any other value, or none, is reported as
   `StateCorrupt`.
6. It reads the serial, the lineage, the Terraform or OpenTofu version, the
   root outputs and the number of managed resources. Resource attributes
   are not parsed.

No Secret at all is either "no state yet" (`StateNotFound`, Unknown) or
`StateLost`, depending on whether the object ever applied; see [lost
state](lifecycle.md#lost-state). Outputs come from the state, never from a
Job's result, and `status.observedStateSerial` records the serial they were
read from. For what each reason means and how to recover, see the
[unreadable state runbook](../../operator-guide/runbooks/state-unreadable.md).

## The inputs hash

The base Secret carries the annotation `captf.io/inputs-hash`, a value of
the form `h2:<sha256>` over the canonical rendered inputs of the apply that
wrote the state. The controller compares it with the hash of the inputs it
would render now:

- A mutable object whose current hash differs is re-applied
  (`InputsChanged`).
- A state with no hash at all is `StateWithoutInputsHash`: the controller
  cannot tell what produced it.

Terraform's own writes carry only the backend labels, so the annotation is
added by the manager, in the step below.

## Adoption

After a successful apply or restore, the manager adopts the state:

- It adds an owner reference to the `Terraform*` object on every chunk. The
  reference is not a controller reference and leaves `blockOwnerDeletion`
  unset, so it never blocks the object's deletion; it makes Kubernetes
  garbage-collect the chunks with the object, and makes `clusterctl move`
  follow the object to the target.
- It sets `captf.io/inputs-hash` on the base Secret, with an optimistic
  lock so a concurrent write is not overwritten.

Adoption runs only when the Job's hash is set and differs from the state's.
A `-part-N` chunk that Terraform creates later, during a refresh, a drift
check or a retry with the same hash, therefore has no owner reference when
it is written. The next reconcile that finds no Job running owns it again,
as it does a chunk restored without references or naming an earlier UID of
the object, and emits `OwnerReferencesRepaired`. It does not do so while the
object is paused, or while a Job holds the run lease. The cleanup after a
destroy finds every chunk by the label selector, not by ownership.

!!! related "See also"

    - [Terraform State](../state.md) for caps, locks and what is read.
    - [State Storage: Terraform and OpenTofu](runtimes.md).
    - [Backups and restore](backups.md).
    - [Size limits runbook](../../operator-guide/runbooks/size-limits.md).
    - [Stale state lock runbook](../../operator-guide/runbooks/stale-lock.md).
