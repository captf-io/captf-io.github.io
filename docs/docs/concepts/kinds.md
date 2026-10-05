---
description: How CAPTF's seven kinds relate to Cluster API's objects, what stays fixed once an object exists, and what a cluster passes down.
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/shapes
subtitle: "The three Terraform kinds"
---

# The Kinds

If you are learning how CAPTF's objects relate to Cluster API's, start
here. CAPTF adds seven kinds to one API group and version,
`infrastructure.cluster.x-k8s.io/v1alpha1`. Three of them are the objects
that carry the desired state Cluster API's core controllers drive as a
cluster comes up; three are templates that stamp those out; the seventh
holds the cloud credentials the others use. Every field, default and
validation rule is in [Custom Resources](../reference/resources/README.md); this page
explains how the seven fit together, and what stays fixed once an object
exists.

## The seven kinds

| Kind | Cluster API role | Scope | Referenced by |
| --- | --- | --- | --- |
| `TerraformCluster` | InfraCluster | Namespaced | `Cluster.spec.infrastructureRef`, always directly |
| `TerraformMachine` | InfraMachine | Namespaced | `Machine.spec.infrastructureRef`, always directly |
| `TerraformMachinePool` | InfraMachinePool | Namespaced | `MachinePool.spec.template.spec.infrastructureRef`, always directly |
| `TerraformClusterTemplate` | Template | Namespaced | A ClusterClass |
| `TerraformMachineTemplate` | Template | Namespaced | A MachineDeployment, MachineSet, KubeadmControlPlane, another control-plane provider, or a ClusterClass |
| `TerraformMachinePoolTemplate` | Template | Namespaced | A ClusterClass |
| `TerraformClusterIdentity` | None (CAPTF-only) | Cluster | `spec.identityRef` of a cluster, machine or pool in an allowed namespace |

## The three workload kinds

A `TerraformCluster`, `TerraformMachine` or `TerraformMachinePool` runs one
Terraform or OpenTofu module role — cluster, machine or machinepool — as a
Job. What goes into that Job and how the reconcile loop drives it are
covered in [Job inputs](inputs.md) and
[the reconcile lifecycle](lifecycle.md); this section is about the object
itself.

Each of the three is owned by its Cluster API counterpart, not by CAPTF:
the counterpart's own core controller sets the owner reference. A
`TerraformCluster` or `TerraformMachinePool` can be an object you create
and point the `Cluster` or `MachinePool` at directly, or one a
ClusterClass topology expands from a `TerraformClusterTemplate` or
`TerraformMachinePoolTemplate`; either way, the resulting object is owned
the same way. A `TerraformMachine` is normally expanded from a
`TerraformMachineTemplate`, one per `Machine`, by a MachineDeployment,
a MachineSet or a control-plane provider, whether or not a ClusterClass
is involved; a `Machine` can also point at a directly created
`TerraformMachine`, the same way a `Cluster` or `MachinePool` can point
at a directly created `TerraformCluster` or `TerraformMachinePool`.

- **`TerraformCluster`** is owned by a `Cluster`. `spec.controlPlaneEndpoint`
  is mutable until it has a host — set by you, or once by the controller from
  the module's output — and immutable after: every Machine and kubeconfig of
  the cluster points at it. Its `host` and `port` must be set together; the
  webhook rejects one without the other. Everything else, including the module
  image, can change on a live object; a new image or a changed input
  re-applies the module against the existing state. `spec.identityRef` is
  required. `spec.applyPolicy` and the destructive-plan guard are covered in
  [plan preview and approval](../user-guide/plan-approval.md).
- **`TerraformMachine`** is owned by a `Machine`. `spec.source`,
  `spec.identityRef`, `spec.variables` and `spec.variablesFrom` define the
  machine and are immutable after creation: change them through a
  MachineDeployment or control-plane rollout, not in place.
  `spec.providerID` can only move from empty to non-empty, and only by
  the manager's ServiceAccount; a create may still carry one, so
  `clusterctl move` can restore it. A `TerraformMachineTemplate` rejects
  `providerID` outright. `spec.jobs`, `spec.drift` and `spec.remediation` are
  operational policy and stay mutable at any time, so a stuck machine's
  deadline or drift interval can be changed without rolling it. A direct
  delete is refused while a Machine that is not itself being deleted
  references the object through `spec.infrastructureRef`, except a
  `clusterctl move` delete (`clusterctl.cluster.x-k8s.io/delete-for-move`)
  while the Cluster is paused; see
  [the reconcile lifecycle](lifecycle.md) for deletion and finalizers.
- **`TerraformMachinePool`** is owned by a `MachinePool`. Unlike a
  `TerraformMachine`, every field is mutable: a change to `spec.source`,
  `spec.variables`, `spec.variablesFrom` or any other field re-applies the
  module on the next reconcile. A pool has no `spec.applyPolicy`. Its apply is
  guarded only when it renders a change of the cluster's exports (see
  [the guard](approvals/destructive-guard.md#machine-pools)). With
  autoscaling enabled, it also writes the group's observed replica count back
  to `MachinePool.spec.replicas`; see
  [machine pools](../user-guide/machine-pools.md).

## Templates

`TerraformClusterTemplate`, `TerraformMachineTemplate` and
`TerraformMachinePoolTemplate` each hold `spec.template`, the metadata and
spec a `TerraformCluster`, `TerraformMachine` or `TerraformMachinePool` is
created with. A `TerraformClusterTemplate` and a `TerraformMachinePoolTemplate`
are each expanded by a ClusterClass topology into one `TerraformCluster` or
`TerraformMachinePool`, which the `Cluster` or `MachinePool` then
references directly. A `TerraformMachineTemplate` is expanded, with or
without a ClusterClass, by a MachineDeployment, a MachineSet, a
KubeadmControlPlane or another control-plane provider, into one
`TerraformMachine` per `Machine`. See
[ClusterClass](../user-guide/clusterclass.md) for how templates and
flavors fit together.

!!! warning "A template's spec is immutable"

    `spec.template.spec` is immutable once a template exists, like every
    Cluster API template: create a new template and point the owner at it
    instead of editing one in place. `spec.template.metadata` stays mutable.

The one exception is a ClusterClass topology dry-run, which the webhook
recognizes and exempts from the immutability check, so a topology patch
that only touches `spec.template.spec` can still be validated without
tripping it.

A `TerraformMachineTemplate` additionally reports `status.capacity` and
`status.nodeInfo`, resolved from its image's labels, for Cluster
Autoscaler scale-from-zero. `TerraformMachinePoolTemplate` has no status:
a pool has no scale-from-zero, so there is no capacity to resolve.

## `TerraformClusterIdentity`

`TerraformClusterIdentity` is cluster-scoped and has no Cluster API
counterpart: it exists only to hold `spec.secretRef`, the credentials
Secret a `TerraformCluster`'s, `TerraformMachine`'s or
`TerraformMachinePool`'s module run is allowed to use, and
`spec.allowedNamespaces`, which namespaces may reference it. Every field
is mutable, including `secretRef`; changing it re-checks that the
requester may read the new Secret. Deleting an identity is refused while
any object still uses it or still has its credentials mirrored into a
namespace. See [identities](../user-guide/identities.md) for creating,
rotating and revoking credentials, and how they reach a Job.

## What a cluster passes to its machines and pools

A `TerraformCluster`'s `spec.defaults` apply only to its
`TerraformMachine`s and `TerraformMachinePool`s, never to the cluster
itself, and are merged field by field: a field the machine or pool sets
wins, an unset one comes from `spec.defaults`, and a field neither sets
gets the built-in default. A machine or pool finds its `Cluster` by its
own `cluster.x-k8s.io/cluster-name` label, then the `TerraformCluster`
through the Cluster's `spec.infrastructureRef`.

- **`identityRef`**: a machine or pool uses its own `identityRef` when it
  sets one, else the cluster's `spec.defaults.identityRef`, else the
  cluster's own `spec.identityRef`.
- **`jobs`**: merged field by field with `spec.defaults.jobs`, own over
  defaults; see [Tuning Jobs](../user-guide/job-tuning.md#inheriting-from-a-clusters-defaults)
  for the full merge algorithm.
- **`drift`**: only `intervalSeconds` is inherited — the object's own,
  else `spec.defaults.drift.intervalSeconds`, else the manager's built-in
  default. A pool's own `drift.action` is never inherited; unset, it
  defaults to `Report` regardless of the cluster's defaults, which carry
  no `action` to inherit.

!!! note "The pool exception"

    A `TerraformMachine`'s drift can be turned off with `intervalSeconds: 0`,
    and an inherited `spec.defaults.drift` of 0 turns it off the same way,
    but a `TerraformMachinePool`'s drift can never be turned off; see
    [Drift and health](drift-and-health.md#what-runs-and-when) for why.

!!! related "See also"

    - [Custom Resources](../reference/resources/README.md) for every
      field, default and validation rule.
    - [The reconcile lifecycle](lifecycle.md) for what runs when, retries,
      deletion and finalizers.
    - [Job inputs](inputs.md) for what each role's Job receives.
    - [ClusterClass](../user-guide/clusterclass.md) for templates in use.
    - [Machine pools](../user-guide/machine-pools.md) for autoscaling and
      replica write-back.
    - [Identities](../user-guide/identities.md) for `TerraformClusterIdentity`
      in depth.
