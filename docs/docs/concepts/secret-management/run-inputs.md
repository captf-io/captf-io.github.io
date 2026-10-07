---
description: Learn where rendered inputs are kept, how long, and what the plan key is for.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/file-key
subtitle: "Where inputs live and for how long"
---

# Run Inputs and the Plan Key

Four more Secrets belong to each object's runs: a durable copy of the newest
attempt's inputs, an applied copy of the newest successful apply's inputs, a
per-run copy handed to one Job, and the key behind the plan hash. What goes into the inputs, and how the hash over them is
computed, is in [Job Inputs](../inputs.md); this page covers where the
rendered files are kept and for how long.

## Durable inputs

`captf-inputs-<kindshort>-<name>` is the **attempt record**. It holds the
inputs of the newest apply Job that was created (or a running one the
controller adopted), and it is written after the Job create succeeds: a start
that is deferred, refused or never reaches the create writes nothing. It
holds:

- the data keys `main.tf.json` and `terraform.tfvars.json`: the rendered
  root module and its variables. Bootstrap data and every variable value
  are in clear text here;
- annotations, in the table below.

| Annotation | Holds |
| --- | --- |
| `captf.io/image` | The image reference |
| `captf.io/identity` | The identity |
| `captf.io/identity-kind` | `Secret` for a namespace-local Secret identity, absent otherwise |
| `captf.io/inputs-hash` | The inputs hash the attempt rendered |
| `captf.io/job` | The apply Job the record belongs to |
| `captf.io/may-have-applied` | Set when the newest apply may have run its apply step and failed or vanished; see [Which record a destroy renders](../deletion/destroy-job.md#which-record-a-destroy-renders) |
| `captf.io/applied` | The applied marker, set after the first successful apply |
| `captf.io/unpullable-images` | JSON list (at most 3) of images a destroy, refresh, drift or restore Job could not pull; cleared by a successful apply |

It also keeps the hub annotations other features use: pending and partial
pool exports, `captf.io/unconfirmed-apply` and `applied-cluster-outputs.json`.
It no longer carries `captf.io/image-digest`: the digest belongs to the applied
record below.

It has one owner reference to the object, and the labels `captf.io/managed`
and the owner-kind and owner-name labels. It has no move label: it travels
with `clusterctl move` by following the owner reference.

What the durable Secret is for:

- **Destroy and drift of an immutable machine, in part.** A `TerraformMachine`
  is never re-rendered once provisioned, so its destroy, refresh and drift
  runs use saved files, image and identity. Mostly those come from the
  applied record; the attempt record is used when the newest apply may have
  applied part of its change.
- **The applied marker.** `captf.io/applied: "true"` is set after the first
  successful apply, or when the manager reads a state that carries an
  inputs hash. Only deleting the Secret removes it. Because the Secret
  moves and status does not, the marker is how an object's history survives
  a move; see [lost state](lifecycle.md#lost-state).

A name that would pass 253 characters is shortened to a prefix and 16 hex
characters of a hash. Cleanup deletes the Secret after a destroy.

## Applied inputs

`captf-applied-<kindshort>-<name>` is the **applied record**: the files
`main.tf.json` and `terraform.tfvars.json` of the newest **successful** apply,
and the digest its pod ran. It is a separate Secret because two copies of
files of up to 1 MB do not fit in one Secret. Its annotations:

| Annotation | Holds |
| --- | --- |
| `captf.io/image` | The image reference of that apply |
| `captf.io/image-digest` | The digest the pod ran, from its container status |
| `captf.io/identity` | The identity |
| `captf.io/identity-kind` | `Secret` for a namespace-local Secret identity |
| `captf.io/inputs-hash` | The inputs hash that apply rendered |
| `captf.io/job` | The apply Job it was promoted from |

It has the same owner reference and labels as the durable Secret
(`captf.io/managed=true`, owner kind and owner name), so it moves with
`clusterctl move`, is kept by `Retain`, is adopted with the retained state,
has its owner reference repaired, and is deleted by cleanup.

**Promotion.** When bookkeeping reads a newly finished successful apply, it
copies the Job's per-run Secret into the applied record. If that Secret is
gone, it uses the attempt record when that names the Job. If neither source
has the Job's inputs, it emits the `AppliedInputsUnknown` Warning and the
applied record keeps the older apply's inputs. Promotion runs before the
per-run Secret is deleted, and it is idempotent: it is skipped when
`captf.io/job` already names the Job, so a crash between the two steps is
harmless.

**The digest.** `captf.io/image-digest` and `status.source.imageDigest` come
from the applied record, and always pair with the files of the latest
success. A promotion whose pod reports no digest keeps the previous record's
digest when the image is the same; otherwise it records none and emits
`DigestUnknown`. `DigestPinned` fires when a promotion records a new or
different digest.

## Per-run inputs

`captf-run-<job>` is created right after the Job, from that reconcile's
rendered inputs; the pod waits for the volume. It holds exactly
`main.tf.json` and `terraform.tfvars.json`, carries the annotations
`captf.io/image`, `captf.io/identity`, `captf.io/identity-kind` and
`captf.io/inputs-hash`, and the label `captf.io/managed=true`, and is owned by
the Job, so Kubernetes removes it with the Job. The controller deletes it
after promoting it (for a successful apply), not when it first sees the Job
finished.

The reason for a second copy is that a running Job must never see its
inputs change. The durable Secret is rewritten whenever a later apply Job
is created; the per-run Secret is written once. A restore Job's
per-run Secret holds a backend-only root module and an empty tfvars file,
and the Job's config volume adds the backup chunks (see [Backups and
restore](backups.md#restore)).

!!! warning "The input Secrets hold the same plain text"

    Anyone who can read Secrets in the namespace can read it. See
    [Security considerations](security.md).

## The plan key

`captf-plankey-<kindshort>-<name>` holds 32 random bytes under the key
`key`. It is owned by the object, labeled `captf.io/managed` with the owner
labels, created the first time a plan needs it and never rotated. Cleanup
deletes it, and it moves by its owner reference.

The runner uses it as the key of an HMAC when it fingerprints a plan, so
the `p2:` plan hash in a `TerraformPlan`'s `spec.planHash` reveals nothing about the
planned values (see [What the plan hash
binds](../approvals/fingerprint.md)).
The key is mounted, read-only at `/captf/plan-key/key` with mode `0440`
(runner flag `--plan-key-file`), only on:

- plan Jobs, which `applyPolicy: Manual` uses;
- the apply Job that carries an approved plan.

A destructive-plan guard run under `Automatic`, and every drift, refresh,
destroy and restore Job, do not mount it. Because the key never rotates, a
hash stays valid for the object's life.

!!! related "See also"

    - [Job Inputs](../inputs.md).
    - [Plan Approval](../../user-guide/plan-approval.md#caveats).
    - [Inside the Job](job.md).
