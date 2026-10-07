---
title: "Upgrading the CAPTF Provider"
description: "Upgrade the CAPTF provider with clusterctl, understand what an upgrade triggers on existing objects, and roll back."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/circle-arrow-up
subtitle: "Move to a new release safely"
---

# Upgrades

This page covers upgrading an installed CAPTF provider with `clusterctl`,
how CAPTF versions its contract, what an upgrade can trigger on existing
objects, where to read what changed, and how to roll back. See
[Installation](installation.md) for installing CAPTF the first time.

!!! info "Before you begin"

    - CAPTF already installed with `clusterctl init` (see
      [Installation](installation.md)), and a `clusterctl.yaml` naming the
      provider (`name: terraform`).
    - `clusterctl`, at a version that supports upgrading the Cluster API
      release you run.

## Check what changed first

Before upgrading, read what changed between your installed version and the
target one:

- The provider's own release notes on its GitHub release, generated from
  the commits since the previous tag.
- [The module contract changelog](../module-author/contract/v1alpha1/CHANGELOG.md),
  when the entries mention a contract or inputs-hash change (below); it
  records every contract-visible change, newest first, whether or not the
  contract's own version number moved.

The project is pre-1.0 and does not backport: fixes land on `main` and in
the next release, never in an earlier one (see
[SECURITY.md](https://github.com/captf-io/cluster-api-provider-terraform/blob/main/SECURITY.md)).
Staying on an old release means staying without later fixes.

## Upgrade with clusterctl

```sh
clusterctl upgrade plan
```

lists the provider versions clusterctl can upgrade each installed
component to, grouped by the Cluster API contract they implement. Apply a
plan, or name a version for CAPTF directly:

```sh
clusterctl upgrade apply --contract v1beta2
clusterctl upgrade apply --infrastructure terraform:vX.Y.Z
```

!!! note "Only three releases exist"

    CAPTF has released v0.1.0, v0.1.1 and v0.2.0, so `clusterctl upgrade plan`
    has two steps to offer. Neither upgrade path has been run: see
    [Compatibility](compatibility.md#what-is-tested). To try an unreleased
    build, reinstall from a local repository, the same way as a first install
    (see [Installing from a local
    repository](../developer-guide/releasing.md#installing-from-a-local-repository)).

## The runner image after an upgrade

The release components pin the manager image by digest, and
`CAPTF_MANAGER_IMAGE` is set to the same reference, so after an upgrade the
runner image is the same build as the manager. An upgrade replaces the
installed manifests, so an override you set with
[`--runner-image`](configuration.md#--runner-image) is not carried over:
re-apply it after each upgrade.

## Contract versioning

CAPTF's `metadata.yaml` lists its release series for `clusterctl`: each
entry is a `(major, minor)` pair and the Cluster API contract it
implements. The list is append-only — an entry, once published, is never
removed or changed — so `clusterctl upgrade plan` can always resolve an
older installed version's contract. CAPTF has one series so far, `0.1`,
implementing contract `v1beta2`; a later series only appears once a
release under it exists, and only ever adds to the list.

The contract version in `metadata.yaml` is separate from the module
contract version (`v1alpha1`, [Module Contract](../module-author/contract/README.md)):
the first is what Cluster API's own core and other providers require of
CAPTF, the second is what CAPTF requires of a module image. A provider
upgrade can change either, both, or neither.

## What an upgrade can trigger

An upgrade replaces the installed manifests — CRDs, RBAC, the manager and
its webhooks — but does not touch a `Terraform*` object's spec. Things
it can still trigger on existing objects, all driven by the manager's own
reconcile after it restarts on the new version:

- **A one-time re-apply of every provisioned mutable object.** The inputs
  hash (`captf.io/inputs-hash`) covers a hash scheme identifier along with
  the contract version, role, image reference and rendered inputs (see
  [What is (and isn't) in the inputs hash](../concepts/inputs.md#7-what-is-and-isnt-in-the-inputs-hash)).
  A release that changes what the hash covers bumps the scheme, so every
  existing `TerraformCluster`'s and `TerraformMachinePool`'s inputs hash
  changes even though nothing in its spec did; the object's next reconcile
  sees a hash that no longer matches its state and re-applies once (a
  `TerraformCluster` with `spec.applyPolicy: Manual` plans once instead
  and waits for approval; see [Plan
  Approval](../user-guide/plan-approval.md)). A `TerraformMachine` is
  unaffected: its inputs hash is never recomputed
  once it is provisioned.
- **A one-time cleanup of a `TerraformClusterIdentity`'s credentials
  Secret.** Earlier versions put an ownerRef on the Secret named in
  `spec.secretRef`, so deleting the identity garbage-collected it; current
  versions do not own that Secret. The identity's reconcile removes a
  leftover ownerRef the first time it runs after the upgrade, independent
  of whether anything uses the identity. Let the upgraded manager
  reconcile every identity once before deleting one, so this cleanup runs
  first; see [Identities and Credentials](../user-guide/identities.md).
- **Re-approval of waiting plans.** Approvals are `TerraformPlan` objects
  that the manager creates, and an approval cannot carry over from a release
  before `TerraformPlan` existed: `status.plan` is dropped, and the
  `captf.io/approve-plan` and `captf.io/approve-destructive-plan`
  annotations are ignored. The manager does not remove them; delete them
  yourself. A change that waited under `applyPolicy: Manual` gets a new
  plan Job at once. An apply that an older release blocked before a
  destructive plan runs again, guarded, up to 10 minutes after the block,
  and blocks again into a `TerraformPlan`. Either way the new
  `TerraformPlan` needs its own approval (see [Plan
  Approval](../user-guide/plan-approval.md#caveats)). Grant approvers
  `patch` on `terraformplans`; see [Who can
  approve](../concepts/approvals/operating.md#who-can-approve).
- **A one-time unknown baseline for pools that applied before exports were
  recorded.** A `TerraformMachinePool` that applied before CAPTF recorded its
  applied cluster exports has no baseline for the exports guard. On its first
  reconcile after the upgrade, CAPTF records the exports it can prove the pool
  applied (from its newest successful apply, or from its current inputs when no
  apply Job is retained and they match the state). Without that proof, every
  apply of the pool is guarded until one succeeds: a plan that deletes or
  replaces nothing applies and records the baseline, and a destructive plan
  waits for approval, with `ApplyJobSucceeded` saying the exports are unknown
  and giving the command. See [Machine
  pools](../concepts/approvals/destructive-guard.md#machine-pools).

The first two are examples, not the full list: any change the contract
changelog records as covering the inputs hash or an identity's Secret
ownership behaves the same way on the next release that ships it. Read the
changelog entries for the version you are moving to, since only they say
whether either applies.

## Rolling back

`clusterctl` has no dedicated rollback command: rolling back means
installing the older version's manifests the same way you install any
version, `clusterctl upgrade apply --infrastructure terraform:vX.Y.Z`
naming the earlier tag, or reinstalling from that tag's local repository.

!!! warning "Rolling back re-applies every provisioned object again"

    Rolling back reverses an inputs-hash scheme change the same way upgrading
    applies one: the older manager computes the older scheme, so every
    provisioned mutable object re-applies once again on its first reconcile
    after the rollback. `v1alpha1` (the module contract, distinct from the
    `metadata.yaml` contract above) carries no compatibility guarantee between
    its own changes ([Versioning](../module-author/contract/v1alpha1/README.md#versioning)),
    so a rollback that crosses a contract-changing release can also mean the
    older manager and the module images or generated roots from the newer one
    disagree about a field name or an input; check the contract changelog for
    the versions in between before rolling back across one.
