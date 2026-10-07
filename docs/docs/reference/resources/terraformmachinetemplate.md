---
title: "TerraformMachineTemplate API Reference"
description: "Reference for the TerraformMachineTemplate kind: the template Cluster API clones into TerraformMachines, and the scale-from-zero status read from the image."
icon: lucide/copy
subtitle: "A TerraformMachine to clone"
---

# TerraformMachineTemplate

A `TerraformMachineTemplate` is the blueprint Cluster API clones into one
[`TerraformMachine`](terraformmachine.md) per `Machine`. `spec.template` holds
the metadata and spec each clone is created with. Three kinds of owner
reference it:

- a MachineDeployment or MachineSet, through `spec.template.spec.infrastructureRef`
  of the Machine template;
- a KubeadmControlPlane (or another control-plane provider), through
  `spec.machineTemplate.infrastructureRef`;
- a ClusterClass, as the infrastructure template of a control plane or a
  worker class.

Unlike the other template kinds, a `TerraformMachineTemplate` has a status.
The manager reads the module image's labels and records the node size and
platform the image declares in `status.capacity` and `status.nodeInfo`, so
the Cluster Autoscaler can scale a MachineDeployment up from zero replicas
without a running node to measure.

| | |
| --- | --- |
| API version | `infrastructure.cluster.x-k8s.io/v1alpha1` |
| Kind | `TerraformMachineTemplate` |
| Scope | Namespaced |
| Module role | `machine`, through the machines it creates |
| Created by | You (or a cluster template or ClusterClass you apply) |
| Referenced by | MachineDeployment, MachineSet, KubeadmControlPlane and ClusterClass `infrastructureRef` |
| Finalizer | none |
| Short names | `tfmt` |
| Categories | `cluster-api` |
| Status subresource | yes |

## Example

```yaml title="terraformmachinetemplate.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachineTemplate
metadata:
  name: demo-md-0
  namespace: default
spec:
  template:
    metadata:
      labels:
        team: platform
    spec:
      source:
        image: ghcr.io/captf-io/module-images/aws-machine:v0.1.0-opentofu
      identityRef:
        name: aws-prod
      remediation:
        annotateMachine: true
```

`spec.template.spec` is the only required part, and inside it only
`source.image`. Everything under it is a [`TerraformMachine`
spec](terraformmachine.md#spec) and means the same there.

## Spec

`spec` holds `spec.template` and the optional `spec.capacity`.

| Field | Type | Description |
| --- | --- | --- |
| `spec.template` | object | The `TerraformMachine` created from this template. **Required.** Must set at least one property. |
| `spec.template.metadata` | object | Metadata copied onto each created `TerraformMachine`. **Optional.** **Mutable.** |
| `spec.template.metadata.labels` | map of string | Labels copied onto each machine. Keys and values must be valid Kubernetes labels. **Optional.** |
| `spec.template.metadata.annotations` | map of string | Annotations copied onto each machine. Keys must be valid annotation keys. **Optional.** |
| `spec.template.spec` | object | The spec of each created `TerraformMachine`. **Required.** **Immutable** (see [Validation](#validation)). |
| `spec.capacity` | map of resource name to quantity | The resources of the node the template creates, for example `cpu: "4"` and `memory: 16Gi`. Overrides the image label `io.captf.capacity` entirely, with no per-resource merge. **Optional.** **Mutable**, and never copied to the machines. See [Override the capacity](#override-the-capacity). |

Each field directly under `spec.template.spec` is the `TerraformMachine`
field of the same name:

| Field | Type | Description |
| --- | --- | --- |
| `spec.template.spec.source` | object | The machine-role module image. **Required.** See [`spec.source`](terraformmachine.md#spec). |
| `spec.template.spec.identityRef` | object | The identity the machines' Jobs use. Machines fall back to their `TerraformCluster`'s defaults when unset. See [`spec.identityRef`](terraformmachine.md#spec). |
| `spec.template.spec.jobs` | object | Job tuning for each machine. See [`spec.jobs`](terraformmachine.md#spec). Only its `imagePullSecrets` take part in resolving this template's status. |
| `spec.template.spec.variables` | object | Inline module variables for each machine. See [`spec.variables`](terraformmachine.md#spec). |
| `spec.template.spec.variablesFrom` | list | Variable sources for each machine. See [`spec.variablesFrom`](terraformmachine.md#spec). |
| `spec.template.spec.drift` | object | Drift check policy of each machine. See [Drift](terraformmachine.md#drift). |
| `spec.template.spec.remediation` | object | Remediation policy of each machine. See [Remediation](terraformmachine.md#remediation). |
| `spec.template.spec.deletionPolicy` | string | Deletion policy of each machine. Usually left unset, so machines follow their `TerraformCluster`, whose policy can change without a rollout. See [Deletion policy](common-fields.md#deletion-policy). |
| `spec.template.spec.adoptRetainedState` | boolean | Lets each machine adopt the state an earlier machine of its name retained. See [Deletion policy](common-fields.md#deletion-policy). |
| `spec.template.spec.providerID` | string | Must be empty. The controller assigns a provider ID to each machine. See [Provider ID](terraformmachine.md#provider-id). |

The fields under `spec.template.spec` are documented once, on
[TerraformMachine](terraformmachine.md); the shared ones in depth on [Common
Fields](common-fields.md). A change to a field in a template reaches
machines only through a rollout: see [Validation](#validation).

## Status

The controller resolves the status once for each image reference, from the
image's config labels. Tags are not polled again: a new image is a new
template. When `spec.template.spec.source.image` differs from
`status.capacitySource.image`, or `spec.capacity` no longer matches
`status.capacity`, the controller resolves it again.

| Field | Type | Description |
| --- | --- | --- |
| `status.capacity` | map of resource name to quantity | The resources of the node the template creates: `spec.capacity` when set, else the image label `io.captf.capacity`, for example `cpu: "4"`. Unset when neither declares any or the label is invalid. |
| `status.nodeInfo` | object | The platform of the node, from the image label `io.captf.node-info`. Unset when the image declares none or the label is invalid. Must set at least one property. |
| `status.nodeInfo.architecture` | string | The node's CPU architecture. **Allowed values:** `amd64`, `arm64`, `s390x`, `ppc64le`. |
| `status.nodeInfo.operatingSystem` | string | The node's operating system, for example `linux`. **Range:** 1 to 64 characters. |
| `status.capacitySource` | object | Records where `capacity` and `nodeInfo` came from. |
| `status.capacitySource.source` | string | `Spec` when `status.capacity` is `spec.capacity`, `Image` when it comes from the image label. **Allowed values:** `Spec`, `Image`. |
| `status.capacitySource.image` | string | The `spec.template.spec.source.image` last resolved. **Range:** 1 to 512 characters. Required when `source` is `Image`; unset when `source` is `Spec` and the image could not be inspected. |
| `status.conditions` | list | The `CapacityResolved` and `VariablesValid` conditions. **Range:** at most 32. |
| `status.conditions[].type` | string | The condition type: `CapacityResolved` or `VariablesValid`. |
| `status.conditions[].status` | string | `True`, `False` or `Unknown`. |
| `status.conditions[].reason` | string | A CamelCase reason. Every reason is on [Conditions](../conditions.md#capacityresolved) and [Conditions](../conditions.md#variablesvalid). |
| `status.conditions[].message` | string | A human-readable detail. |
| `status.conditions[].lastTransitionTime` | time | When `status` last changed. |
| `status.conditions[].observedGeneration` | integer | The `metadata.generation` the condition was computed for. |

### Where the values come from

The manager reads the image's config over the registry API, not by pulling
it. For an image index it takes the `linux` image of the manager's own
architecture, else the first `linux` image. It authenticates with the
Secrets in `spec.template.spec.jobs.imagePullSecrets`, in the template's
namespace. A template has no `TerraformCluster`, so the cluster's
`spec.defaults.jobs.imagePullSecrets` do not apply here. The two labels are
defined on the [image contract](../../module-author/image-contract.md#oci-labels).

| Label | Value | Sets |
| --- | --- | --- |
| `io.captf.capacity` | A JSON object of resource name to Kubernetes quantity, such as `{"cpu":"4","memory":"16Gi"}`. Each key must be a valid resource name and each value a quantity. An empty object is invalid. | `status.capacity` |
| `io.captf.node-info` | A JSON object `{"architecture":"amd64","operatingSystem":"linux"}` with at least one key and no others. | `status.nodeInfo` |

```yaml title="status of a resolved template"
status:
  capacity:
    cpu: "4"
    memory: 16Gi
  nodeInfo:
    architecture: amd64
    operatingSystem: linux
  capacitySource:
    source: Image
    image: ghcr.io/captf-io/module-images/aws-machine:v0.1.0-opentofu
  conditions:
    - type: CapacityResolved
      status: "True"
      reason: CapacityResolved
      lastTransitionTime: "2026-10-02T08:10:31Z"
```

The Cluster API provider of the Cluster Autoscaler reads `status.capacity` and
`status.nodeInfo` from the infrastructure template of a MachineDeployment or
MachineSet that is at zero replicas, to decide whether a pending Pod would fit
a new node. The labels are optional, and pool images ignore them.

### Override the capacity

A label describes one node size, so it suits a module that fixes the
instance type. When the module takes the size as a variable (`instance_type`,
`vm_size`, `shape`, ...), set `spec.capacity` to the size you chose instead
of building one image per size, and leave `io.captf.capacity` off the image:
[`tfcapi-lint`](../tfcapi-lint-cli.md) warns with
`image/capacity-size-variable` when both exist.

```yaml title="spec.capacity"
spec:
  capacity:
    cpu: "4"
    memory: 16Gi
  template:
    spec:
      source:
        image: ghcr.io/captf-io/module-images/aws-machine:v0.1.0-opentofu
      variables:
        instance_type: m6i.xlarge
```

- `spec.capacity` replaces the image's capacity label as a whole: a resource
  the override omits is not filled in from the label, and an invalid label
  is then ignored. `status.capacitySource.source` becomes `Spec`.
- The override does not need the registry. If the image cannot be
  inspected, `status.capacity` is still set from `spec.capacity`,
  `capacitySource.image` stays unset, the last known `nodeInfo` is kept (unset
  if never resolved), and `CapacityResolved` stays `True` with a message that
  starts "image not inspected". The manager keeps retrying for `nodeInfo`.
- `nodeInfo` still comes from the image's `io.captf.node-info`.
- It is mutable and stays out of `spec.template`, so changing it does not roll
  any machine. Keep it equal to the size the variables select: CAPTF does not
  check that they agree.
- The Cluster Autoscaler's
  `capacity.cluster-autoscaler.kubernetes.io/*` annotations (`cpu`, `memory`,
  `ephemeral-disk`, `maxPods`, GPU keys) on the MachineDeployment or
  MachineSet take precedence over `status.capacity`, per resource. The order,
  highest first: those annotations, `spec.capacity`, the image label.
- Capacity is a set of quantities, never a node count. CAPTF does not write
  the number of nodes or Machines for a template. The only count it writes is
  the observed one, copied back to `MachinePool.spec.replicas` for a pool in
  autoscaling mode (`ReplicasManagedByModule`); an external scaler can change
  the count freely.

### Conditions

A template has two conditions, `CapacityResolved` and `VariablesValid`, and
no `Ready` condition. `CapacityResolved`:

| Status | Reasons | Meaning |
| --- | --- | --- |
| `True` | [`CapacityResolved`](../conditions.md#capacityresolved) | Every label the image carries parsed; `capacity` and `nodeInfo` are set from them. |
| `True` | [`CapacityResolved`](../conditions.md#capacityresolved) | With `spec.capacity` set and the image unreadable: the message starts "image not inspected" and names the failure class. `capacity` is set from the spec. |
| `True` | [`CapacityNotDeclared`](../conditions.md#capacityresolved) | The image carries neither label. Both fields stay unset. This is not an error. |
| `False` | [`ImageInspectFailed`](../conditions.md#capacityresolved) | The registry could not be read: authentication failed, the image was not found, or the registry was unreachable. The previous values stay. The message names the class of failure, never the registry's own text. The manager retries, doubling the delay from 30 seconds to at most 10 minutes. |
| `False` | [`CapacityLabelInvalid`](../conditions.md#capacityresolved) | A label is present but invalid. That field is unset; a valid other label is still applied. The manager does not retry the same image, because the tag is not polled again. |

`VariablesValid` says whether the template's `variables` and
`variablesFrom` fit the variables schema the image publishes in
`io.captf.variables-schema` ([image
contract](../../module-author/image-contract.md#oci-labels)); the manager
reads it from the same image config, in the same pass:

| Status | Reasons | Meaning |
| --- | --- | --- |
| `True` | [`VariablesValid`](../conditions.md#variablesvalid) | The variables fit the schema. |
| `True` | [`VariablesSchemaNotDeclared`](../conditions.md#variablesvalid) | The image has no usable schema; nothing is checked. |
| `False` | [`VariablesRejected`](../conditions.md#variablesvalid) | A variable is unknown, required and not set, or of the wrong type. The message names the variable, never the value. |
| `Unknown` | [`VariablesSourcePending`](../conditions.md#variablesvalid), [`VariablesSchemaUnavailable`](../conditions.md#variablesvalid) | A source is missing, or the image could not be read. The manager retries. |

The manager emits a `CapacityResolved` Normal event when the values change and
an `ImageInspectFailed` Warning event on the first failure. See
[Events](../events.md).

## Printer columns

`kubectl get terraformmachinetemplates` (or `kubectl get tfmt`) shows:

| Column | Source | Description |
| --- | --- | --- |
| `Image` | `.spec.template.spec.source.image` | The module image. |
| `Age` | `.metadata.creationTimestamp` | Time since creation. |

## Validation

The admission webhook checks templates on create and update. Deletes are
always allowed.

- `spec.template.spec` is immutable. Create a new template and point the owner
  at it; Cluster API rolls the machines. This holds even for fields that are
  mutable on a `TerraformMachine` (`jobs`, `drift`, `remediation`). Checked on
  update.
- The immutability rule does not apply to a ClusterClass topology dry-run, so
  a topology patch can be validated. Checked on update.
- `spec.template.spec.providerID` must be empty: a value would stamp every
  clone with one instance's identity. Checked on create and update.
- `spec.template.metadata` labels and annotations must be valid keys and
  values. `spec.template.metadata` itself is mutable. Checked on create and
  update.
- `spec.template.spec` follows the `TerraformMachine` spec rules:
  `source.image` is required and must parse, `jobs` may not weaken the
  security contexts, `lockTimeoutSeconds` must be below
  `activeDeadlineSeconds`, and `variables` and `variablesFrom` are
  well-formed. Checked on create and update.
- `spec.template` must set at least one property, and `spec.template.spec` is
  required. Checked on create and update.

A template's rules are the same as the machine's, so a bad image reference or
a root-running security context is rejected when you create the template, not
when Cluster API clones it. See [TerraformMachine
validation](terraformmachine.md#validation) for each one.

!!! related "See also"

    - [TerraformMachine](terraformmachine.md) for every field under
      `spec.template.spec`.
    - [Common Fields](common-fields.md) for the shared workspace fields.
    - [The Kinds](../../concepts/kinds.md#templates)
    - [Image contract: OCI labels](../../module-author/image-contract.md#oci-labels)
    - [Conditions](../conditions.md#capacityresolved) and
      [Events](../events.md)
