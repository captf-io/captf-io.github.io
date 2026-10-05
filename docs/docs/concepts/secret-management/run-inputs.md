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

Three more Secrets belong to each object's runs: a durable copy of the last
rendered inputs, a per-run copy handed to one Job, and the key behind the
plan hash. What goes into the inputs, and how the hash over them is
computed, is in [Job Inputs](../inputs.md); this page covers where the
rendered files are kept and for how long.

## Durable inputs

`captf-inputs-<kindshort>-<name>` is written when an apply Job starts. It
holds:

- the data keys `main.tf.json` and `terraform.tfvars.json`: the rendered
  root module and its variables. Bootstrap data and every variable value
  are in clear text here;
- annotations, in the table below.

| Annotation | Holds |
| --- | --- |
| `captf.io/image` | The image reference |
| `captf.io/identity` | The identity |
| `captf.io/image-digest` | The digest the image resolved to, pinned after a successful apply |
| `captf.io/applied` | The applied marker, set after the first successful apply |

It has one owner reference to the object, and the labels `captf.io/managed`
and the owner-kind and owner-name labels. It has no move label: it travels
with `clusterctl move` by following the owner reference.

What the durable Secret is for:

- **Destroy and drift of an immutable machine.** A `TerraformMachine` is
  never re-rendered once provisioned, so its destroy, refresh and drift
  runs use the files, image and identity saved here.
- **Pinning the image.** Changing the image reference clears the pinned
  digest, which is set again after the next successful apply.
- **The applied marker.** `captf.io/applied: "true"` is set after the first
  successful apply, or when the manager reads a state that carries an
  inputs hash. Only deleting the Secret removes it. Because the Secret
  moves and status does not, the marker is how an object's history survives
  a move; see [lost state](lifecycle.md#lost-state).

A name that would pass 253 characters is shortened to a prefix and 16 hex
characters of a hash. Cleanup deletes the Secret after a destroy.

## Per-run inputs

`captf-run-<job>` is created right after the Job, from that reconcile's
rendered inputs; the pod waits for the volume. It holds exactly
`main.tf.json` and `terraform.tfvars.json`, carries only the label
`captf.io/managed=true`, and is owned by the Job, so Kubernetes removes it
with the Job. The controller also deletes it the first time it sees the
Job finished.

The reason for a second copy is that a running Job must never see its
inputs change. The durable Secret is rewritten whenever a later apply
renders new inputs; the per-run Secret is written once. A restore Job's
per-run Secret holds a backend-only root module and an empty tfvars file,
and the Job's config volume adds the backup chunks (see [Backups and
restore](backups.md#restore)).

!!! warning "Both Secrets hold the same plain text"

    Anyone who can read Secrets in the namespace can read it. See
    [Security considerations](security.md).

## The plan key

`captf-plankey-<kindshort>-<name>` holds 32 random bytes under the key
`key`. It is owned by the object, labeled `captf.io/managed` with the owner
labels, created the first time a plan needs it and never rotated. Cleanup
deletes it, and it moves by its owner reference.

The runner uses it as the key of an HMAC when it fingerprints a plan, so
the `p2:` plan hash in `status.plan.planHash` reveals nothing about the
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
