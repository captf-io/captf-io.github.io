---
title: "TerraformClusterTemplate API Reference"
description: "Field-by-field reference for the TerraformClusterTemplate kind: the template a ClusterClass uses to create a TerraformCluster, with its immutability rules."
icon: lucide/copy
subtitle: "A TerraformCluster to clone"
---

# TerraformClusterTemplate

A `TerraformClusterTemplate` holds the metadata and spec of the
[`TerraformCluster`](terraformcluster.md) that a ClusterClass creates. It
has no status and runs nothing itself.

A `ClusterClass` references it in `spec.infrastructure.templateRef`. When
you create a `Cluster` with `spec.topology`, Cluster API clones
`spec.template` into a `TerraformCluster`, applies the class's patches to
the clone, and points the `Cluster`'s `spec.infrastructureRef` at it. You
create a template once per class, and every `Cluster` on the class gets
its own `TerraformCluster`. Without a ClusterClass you create the
`TerraformCluster` directly and never need a template. See
[Templates and ClusterClass](../../user-guide/clusterclass.md).

| Property | Value |
| --- | --- |
| API version | `infrastructure.cluster.x-k8s.io/v1alpha1` |
| Scope | Namespaced |
| Module role | `cluster`, through the `TerraformCluster` it creates |
| Referenced by | `ClusterClass.spec.infrastructure.templateRef` |
| Finalizer | None |
| Short names | None |
| Categories | `cluster-api` |
| Status subresource | No |

## Example

```yaml title="terraformclustertemplate.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformClusterTemplate
metadata:
  name: noop
  namespace: team-a
spec:
  template:
    metadata:
      labels:
        team: platform
    spec:
      source:
        image: ghcr.io/captf-io/module-images/noop-cluster:v0.1.0-opentofu
      identityRef:
        name: aws
      drift:
        intervalSeconds: 900
```

A ClusterClass often leaves `identityRef` out and sets it, and the image,
with a patch. The template then triggers a warning on create, not an
error; see [Validation](#validation).

## Spec

`spec.template` is required, and it must set at least one property.

| Field | Type | Description |
| --- | --- | --- |
| `spec.template` | object | **Required.** The `TerraformCluster` to create. **Immutable** in its `spec`; see [Validation](#validation). |
| `spec.template.metadata` | object | Optional. Metadata copied onto the created `TerraformCluster`. **Mutable.** |
| `spec.template.metadata.labels` | map | Labels copied onto the created object. Keys and values must be valid Kubernetes labels. |
| `spec.template.metadata.annotations` | map | Annotations copied onto the created object. Keys must be valid annotation keys. |
| `spec.template.spec` | object | **Required.** The spec of the created `TerraformCluster`: exactly the [`TerraformCluster` spec](terraformcluster.md#spec). **Immutable.** |
| `spec.template.spec.source` | object | The module image. **Required** by the webhook. See [Source](common-fields.md#source). |
| `spec.template.spec.identityRef` | object | The identity for the Jobs. Optional here; a patch or the `Cluster` can set it, but the created object is rejected without one. See [Identity reference](common-fields.md#identity-reference). |
| `spec.template.spec.jobs` | object | Job policy. See [Jobs](common-fields.md#jobs). |
| `spec.template.spec.variables` | object | Inline module variables. See [Variables](common-fields.md#variables). |
| `spec.template.spec.variablesFrom` | array | Variable sources. See [Variable sources](common-fields.md#variable-sources). |
| `spec.template.spec.controlPlaneEndpoint` | object | The API server endpoint. See [Control-plane endpoint](terraformcluster.md#control-plane-endpoint). |
| `spec.template.spec.drift` | object | Drift policy. See [Drift](terraformcluster.md#drift). |
| `spec.template.spec.applyPolicy` | string | `Automatic` or `Manual`. See [Apply policy](terraformcluster.md#apply-policy). |
| `spec.template.spec.defaults` | object | Values the cluster's machines and pools inherit. See [Defaults](terraformcluster.md#defaults). |
| `spec.template.spec.deletionPolicy` | string | Deletion policy of the cluster, and of its machines and pools that set none. See [Deletion policy](common-fields.md#deletion-policy). |
| `spec.template.spec.adoptRetainedState` | boolean | Lets the cluster adopt the state an earlier cluster of its name retained. See [Deletion policy](common-fields.md#deletion-policy). |

Defaults are the same as for a `TerraformCluster`: the CRD declares none,
and the controller applies them to the created object at reconcile.

## Printer columns

`kubectl get terraformclustertemplates` shows:

| Column | Source |
| --- | --- |
| `IMAGE` | `spec.template.spec.source.image` |
| `AGE` | `metadata.creationTimestamp` |

## Validation

The validating webhook
(`validation.terraformclustertemplate.infrastructure.cluster.x-k8s.io`)
checks every create and update.

- `spec.template.metadata` must hold valid labels and annotations.
- `spec.template.spec` follows the `TerraformCluster` rules for
  `source`, `jobs`, `defaults.jobs`, `variables` and `variablesFrom`;
  see [Validation](terraformcluster.md#validation). The endpoint, drift
  and apply policy rules come from the CRD schema.
- `spec.template.spec.identityRef` is not required. A template without
  one is admitted with the warning "spec.template.spec sets no
  identityRef; TerraformClusters created from this template are rejected
  unless a patch sets one".
- `spec.template.spec` is immutable. Any update that changes it is
  rejected with "TerraformClusterTemplate spec.template.spec is
  immutable; create a new TerraformClusterTemplate instead". Only
  `spec.template.metadata` can change.
- A ClusterClass topology dry-run is exempt from the immutability check,
  so Cluster API can validate patches that touch `spec.template.spec`.
- A jobs policy is checked on an update only when it changed, and not at
  all while the template is deleting.
- Deleting a template is always admitted.

!!! warning "Change a template by creating a new one"

    To change a field of `spec.template.spec`, create a template under a
    new name and point `ClusterClass.spec.infrastructure.templateRef` at
    it. See
    [Template immutability and rolling out a change](../../user-guide/clusterclass.md#template-immutability-and-rolling-out-a-change).

!!! related "See also"

    - [TerraformCluster](terraformcluster.md)
    - [Common fields](common-fields.md)
    - [TerraformMachineTemplate](terraformmachinetemplate.md)
    - [Templates and ClusterClass](../../user-guide/clusterclass.md)
    - [The kinds](../../concepts/kinds.md#templates)
