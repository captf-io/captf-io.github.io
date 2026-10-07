---
title: "TerraformMachinePoolTemplate API Reference"
description: "Every field, printer column and admission rule of the TerraformMachinePoolTemplate kind, the ClusterClass template for TerraformMachinePool."
icon: lucide/copy
subtitle: "A TerraformMachinePool to clone"
---

# TerraformMachinePoolTemplate

A `TerraformMachinePoolTemplate` is the blueprint a ClusterClass uses for the
infrastructure of a `MachinePool`. A ClusterClass `machinePools` class
references it in `infrastructure.templateRef`, and when a topology creates a
`MachinePool` from that class, Cluster API clones `spec.template` into a
[`TerraformMachinePool`](terraformmachinepool.md) that the `MachinePool`
references. You do not need a template for a pool you create by hand; see
[Templates and ClusterClass](../../user-guide/clusterclass.md).

The template has no status. A pool has no scale-from-zero, so there is no
capacity or node information to resolve.

| Property | Value |
| --- | --- |
| API version | `infrastructure.cluster.x-k8s.io/v1alpha1` |
| Kind | `TerraformMachinePoolTemplate` |
| Scope | Namespaced |
| Module role | `machinepool`, through the `TerraformMachinePool` it creates |
| Created by | You |
| Referenced by | A ClusterClass `machinePools[].infrastructure.templateRef` |
| Finalizer | None |
| Short names | None |
| Categories | `cluster-api` |
| Status subresource | No |

## Example

```yaml title="machinepool-template.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachinePoolTemplate
metadata:
  name: aws-workers-v1
  namespace: team-a
spec:
  template:
    metadata:
      labels:
        node-role.kubernetes.io/worker: "" # (1)!
    spec:
      source:
        image: ghcr.io/captf-io/module-images/aws-machinepool:v0.1.0-opentofu
      identityRef:
        name: aws-prod
      variables:
        instance_type: m6i.large
      drift:
        action: Remediate
```

1. Metadata on `spec.template.metadata` is copied to the created
   `TerraformMachinePool`. The module also receives the labels as its
   `node_labels` input.

## Spec

The `spec` block holds one field, `spec.template`, and `spec.template.spec` is required inside it.

| Field | Type | Description |
| --- | --- | --- |
| `spec.template` | object | The `TerraformMachinePool` to create. **Required.** |
| `spec.template.metadata` | object | Metadata copied onto the created object. **Optional.** |
| `spec.template.metadata.labels` | map of strings | Labels for the created object. **Optional.** **Allowed values:** valid Kubernetes label keys and values. |
| `spec.template.metadata.annotations` | map of strings | Annotations for the created object. **Optional.** **Allowed values:** valid Kubernetes annotation keys. |
| `spec.template.spec` | object | The `TerraformMachinePool` spec to create. **Required.** **Immutable.** Takes the fields below. |
| `spec.template.spec.source` | object | The module image. See [`spec.source`](terraformmachinepool.md#spec). **Required.** |
| `spec.template.spec.identityRef` | object | The identity for the pool's Jobs. See [`spec.identityRef`](terraformmachinepool.md#spec). |
| `spec.template.spec.jobs` | object | Job tuning. See [`spec.jobs`](terraformmachinepool.md#spec). |
| `spec.template.spec.variables` | object | Inline module variables. See [`spec.variables`](terraformmachinepool.md#spec). |
| `spec.template.spec.variablesFrom` | list | Variable sources. See [`spec.variablesFrom`](terraformmachinepool.md#spec). |
| `spec.template.spec.drift` | object | Drift interval and action. See [Drift](terraformmachinepool.md#drift). |
| `spec.template.spec.membershipRefreshIntervalSeconds` | integer | Membership refresh interval. See [Membership refresh](terraformmachinepool.md#membership-refresh). |
| `spec.template.spec.deletionPolicy` | string | Deletion policy of the pool. See [Deletion policy](common-fields.md#deletion-policy). |
| `spec.template.spec.adoptRetainedState` | boolean | Lets the pool adopt the state an earlier pool of its name retained. See [Deletion policy](common-fields.md#deletion-policy). |
| `spec.template.spec.providerID` | string | Accepted but not meaningful: the controller writes it on the created pool. See [Provider IDs](terraformmachinepool.md#provider-ids). |
| `spec.template.spec.providerIDList` | list of strings | Accepted but not meaningful: the controller writes it on the created pool. See [Provider IDs](terraformmachinepool.md#provider-ids). |

The fields take the same types, ranges and defaults as on the pool, and the
same CRD schema limits apply. Defaults and inheritance from the cluster's
`spec.defaults` apply to the created pool, not to the template.

## Printer columns

`kubectl get terraformmachinepooltemplates` shows:

| Column | Source |
| --- | --- |
| `IMAGE` | `spec.template.spec.source.image`. |
| `AGE` | Time since creation. |

## Validation

The validating webhook
(`validation.terraformmachinepooltemplate.infrastructure.cluster.x-k8s.io`,
on create and update) applies these rules.

- **Template spec rules.** `spec.template.spec` is checked like a pool's spec:
  a valid `spec.template.spec.source.image` reference, the Job policy rules and
  the variable rules for the `machinepool` role. See
  [Validation](terraformmachinepool.md#validation) on the pool. The Job
  policy is checked on update only when it changed.
- **Template metadata.** `spec.template.metadata.labels` and
  `spec.template.metadata.annotations` must be valid label and annotation
  keys and values.
- **Immutability.** After creation, `spec.template.spec` cannot change: the
  webhook rejects it with "TerraformMachinePoolTemplate spec.template.spec is
  immutable; create a new TerraformMachinePoolTemplate instead". The
  template's metadata can change. To roll out a change, create a new
  template and point the ClusterClass at it, which rolls a new pool through
  the `MachinePool`'s own mechanism. The check is skipped for the server-side
  apply dry-runs a ClusterClass topology performs. The pool a template creates
  is itself mutable. See
  [Template immutability and rolling out a change](../../user-guide/clusterclass.md#template-immutability-and-rolling-out-a-change).
- **Delete.** Always allowed.

!!! related "See also"

    - [TerraformMachinePool](terraformmachinepool.md) and
      [Common Fields](common-fields.md).
    - [Templates and ClusterClass](../../user-guide/clusterclass.md) and
      [Machine Pools](../../user-guide/machine-pools.md).
    - [The Kinds](../../concepts/kinds.md#templates).
