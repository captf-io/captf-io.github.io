---
title: "Known Limitations of CAPTF"
description: What CAPTF does not do yet or does with a catch, with the workaround and the page that has the detail.
tags:
  - Evaluators
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/triangle-alert
subtitle: "Gaps to know before you adopt"
---

# Known Limitations

This page lists what CAPTF does not do, or does with a catch, as the code
stands today. Each item says what the limit is, what follows from it, and
where the detail is. A limit that has a workaround says so. For versions and
what has and has not been tested, see [Compatibility](compatibility.md).

## Scope: self-built control planes only

CAPTF does not provide infrastructure for managed Kubernetes services. It is
built for self-managed, self-built control planes (kubeadm, RKE2): you bring
the Kubernetes distribution and bootstrap mechanism, and CAPTF handles the
underlying cloud infrastructure. For managed Kubernetes (EKS, AKS, GKE, OKE),
use the cloud provider's own Cluster API provider (CAPA for EKS, CAPZ for AKS,
CAPG for GKE, CAPOCI for OKE). See [Control-Plane
Integration](../module-author/control-planes/README.md).

## Maturity

- **Pre-alpha.** v0.1.0 and v0.1.1 are released, but nothing has been
  applied to a real cloud. Every API kind is
  `v1alpha1`, and the module contract is `v1alpha1` and provisional: it may
  change before a real module has provisioned a cluster with it. See
  [Project status](../index.md#project-status).
- **End-to-end coverage is narrow and opt-in.** Two suites run on a local
  kind cluster: one checks the installed components and a real reconcile,
  and one drives the noop modules through a cluster, machines and a machine
  pool. They are not in CI; you run them with `make e2e-foundation` and
  `make e2e-noop`. No real cloud, no module that creates cloud resources,
  `clusterctl upgrade` or `clusterctl move` has been exercised. The unit
  tests mock the Kubernetes API and Job execution, and CI runs them with
  lint and the offline verifications. See
  [Compatibility](compatibility.md#what-is-tested).

## Approvals and gates

- **Only the `TerraformCluster` is fully gated.** `applyPolicy: Manual` and
  the destructive-plan guard exist on the cluster. A machine's apply never
  waits for approval. A pool's apply is guarded in one case only: when it
  renders changed cluster exports. See [What is
  guarded](../concepts/approvals/limits.md#what-is-guarded).
- **A pool's exports guard has limits.** A destructive pool apply of changed
  exports is **held**: the pool keeps applying with the exports of its last
  successful apply until the change is approved. The guard needs the record of
  the last applied exports, which shares the durable Secret's budget with the
  rendered inputs, and `clusterctl move` carries the plan but not the Jobs, so a moved plan still gates the apply. Keep
  shared and destructive infrastructure in the cluster module, keep exports
  stable, and use `prevent_destroy` on what must not go. See [Machine
  pools](../concepts/approvals/destructive-guard.md#machine-pools) and
  [Cluster outputs reach pools and
  machines](../concepts/approvals/limits.md#cluster-outputs-reach-pools-and-machines).
- **An approval binds a plan, not the apply.** It names the plan's hash and
  the apply must plan the same again; it does not promise what the provider
  does. See [An approval binds a
  plan](../concepts/approvals/limits.md#an-approval-binds-a-plan-not-the-apply).

## Security

!!! danger "A module image can read every Secret in its namespace and forge a plan hash"

    - **The module image can read the plan key.** The per-object key that
      makes plan hashes unforgeable by accident is mounted read-only in the
      module's container for plan and approved-apply Jobs. A hostile module
      can read it and forge a plan hash. It protects against drift, not
      against the module. See [The plan key is readable by the
      module](../concepts/approvals/limits.md#the-plan-key-is-readable-by-the-module).
    - **The runner can read and write every Secret in its namespace.** RBAC
      cannot scope the state backend's access. Namespaces are the only
      tenant boundary. See
      [Multi-Tenancy](multi-tenancy.md#the-runner-reads-every-secret-in-its-namespace).

- **No encryption at rest of its own.** State, inputs and credential mirrors
  are Kubernetes Secrets. See [No encryption at
  rest](../concepts/secret-management/security.md#no-encryption-at-rest-of-its-own).

## State

- **OpenTofu state encryption is unsupported.** An encrypted state reads as
  `StateReadable=False`/`StateEncrypted`, and no backup of it is ever taken. See
  [Unreadable State](runbooks/state-unreadable.md#stateencrypted).
- **The state file version must be 4.** Another version reads as
  `StateCorrupt`.
- **Backups are not disaster recovery.** They are in the same namespace,
  owned by the object, and rotated out after `--state-backups`. See [Disaster
  Recovery](disaster-recovery.md).
- **Owner references are repaired on the next reconcile, not at once.**
  The controller owns a state chunk, backup, durable inputs Secret and plan
  key again on the next reconcile that finds no Job running. The gaps are
  narrow: nothing is re-owned while the object is paused (so `clusterctl
  move` is not raced), state chunks wait while a Job holds the run lease,
  and a restored Secret that still names an old UID can be garbage-collected
  before the first reconcile. See [Disaster Recovery](disaster-recovery.md).

## Jobs and leases

- **The lease grace gap.** If a `TerraformCluster`'s inputs change while it
  waits for machine operations, the old leases are held by a Job that will
  never exist, and the new Job waits out the one-minute grace. It resolves
  itself. See [The known gap](../concepts/jobs/leases.md#the-known-gap).
- **No flag caps running Jobs.** The concurrency flags cap reconciles per
  kind, not Jobs. The bounds are one Job per object and your quotas.
- **No quota-specific condition.** A ResourceQuota refusal shows as a
  reconcile error or a Job that never starts. See [Production
  Readiness](production-readiness.md#runner-jobs).
- **A single manager watches one namespace or all of them.** The
  leader-election lease name is fixed, so per-namespace manager instances do
  not work; use `--watch-filter`. See [Namespace scoping](configuration.md#namespace-scoping-and---watch-filter).

## Deletion and move

- **A paused object's deletion waits.** A paused object, or one under a
  paused Cluster, never runs a destroy. `Deleting` says so. This is by design,
  so `clusterctl move` can delete source objects. See [Pause stops a
  deletion](../concepts/deletion/order.md#pause-stops-a-deletion).
- **A moved object in a deleted namespace looks never-applied.** Status does
  not move, and the `captf.io/applied` marker is on a Secret the namespace
  deletion removes. Its finalizer then comes off with nothing destroyed. See
  [The known limit](../concepts/deletion/namespaces.md#the-known-limit).
- **The credential source Secret does not move.** Copy it to the target
  yourself. See [clusterctl move](runbooks/move.md).

## Machine pools

- **The Cluster Autoscaler's `clusterapi` provider is unsupported on
  pools.** The controller supports autoscaling **in the cloud**, driven by
  the pool's min and max annotations, and writes the observed replicas back
  to `MachinePool.spec.replicas`. The `clusterapi` provider needs
  MachinePool Machines and drains nodes before it scales down, and neither
  exists; its changes to `spec.replicas` are overwritten by the write-back.
  The Cluster Autoscaler's cloud providers resize the scaling group
  directly and work with the AWS, Azure and OCI reference modules, but not
  GCP's regional group. See
  [Autoscale with the Kubernetes Cluster Autoscaler](../user-guide/machine-pools.md#autoscale-with-the-kubernetes-cluster-autoscaler).
- **MachinePool Machines are unsupported, by design.** Every MachinePool
  Machine deletion ends with terminating one chosen instance in the cloud's
  scaling group, and Terraform cannot do that. Pool instances have no
  `Machine` objects, so a `MachineHealthCheck` never selects them, and
  Cluster API never drains them. Use a MachineDeployment of
  `TerraformMachine`s for per-node lifecycle. See
  [MachinePool Machines](../module-author/contract/v1alpha1/machinepool.md#machinepool-machines).
- **The bootstrap Secret is not watched.** A rotated token reaches the pool at
  its next reconcile, at the latest one membership-refresh interval later.

!!! related "See also"

    - [Compatibility](compatibility.md).
    - [Production Readiness](production-readiness.md).
    - [Approvals and Gates: Limits](../concepts/approvals/limits.md).
