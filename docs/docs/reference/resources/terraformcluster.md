---
title: "TerraformCluster API Reference"
description: "Field-by-field reference for the TerraformCluster kind: spec, status, conditions, printer columns, admission rules and lifecycle."
icon: lucide/network
subtitle: "One workload cluster"
---

# TerraformCluster

A `TerraformCluster` is the Cluster API infrastructure object of a CAPTF
cluster. It runs the cluster-role module image you name in `spec.source`
as a Job, keeps the module's Terraform state in a Secret, and reports the
module's outputs (the control-plane endpoint, the failure domains and the
exports that machines and pools inherit) in its spec and status.

A `Cluster` references it through `Cluster.spec.infrastructureRef`, and
Cluster API sets the owner reference from the `Cluster` to the
`TerraformCluster`. You normally create one in one of two ways: a
clusterctl template renders it next to the `Cluster`, or a ClusterClass
topology creates it from a [`TerraformClusterTemplate`](terraformclustertemplate.md).
See [The kinds](../../concepts/kinds.md) for how it relates to the other
kinds.

| Property | Value |
| --- | --- |
| API version | `infrastructure.cluster.x-k8s.io/v1alpha1` |
| Scope | Namespaced |
| Module role | `cluster` (see [Cluster role](../../module-author/contract/v1alpha1/cluster.md)) |
| Referenced by | `Cluster.spec.infrastructureRef` |
| Finalizer | `terraformcluster.infrastructure.cluster.x-k8s.io` |
| Short names | None |
| Categories | `cluster-api` |
| Status subresource | Yes |

## Example

The smallest valid object sets a module image and an identity. A
`TerraformCluster` does nothing until a `Cluster` references it.

```yaml title="terraformcluster.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformCluster
metadata:
  name: demo
  namespace: team-a
spec:
  source:
    image: ghcr.io/captf-io/module-images/noop-cluster:v0.1.0-opentofu
  identityRef:
    name: aws
```

The `Cluster` that uses it:

```yaml title="cluster.yaml"
apiVersion: cluster.x-k8s.io/v1beta2
kind: Cluster
metadata:
  name: demo
  namespace: team-a
spec:
  infrastructureRef:
    apiGroup: infrastructure.cluster.x-k8s.io
    kind: TerraformCluster
    name: demo
```

## Full example

This object sets every spec field. Real clusters rarely need all of them.

```yaml title="terraformcluster.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformCluster
metadata:
  name: demo
  namespace: team-a
spec:
  source:
    image: ghcr.io/captf-io/module-images/aws-cluster:v0.1.0-opentofu
    imagePullPolicy: IfNotPresent
  identityRef:
    name: aws
  jobs:
    activeDeadlineSeconds: 7200   # (1)!
    lockTimeoutSeconds: 600
  variables:
    region: eu-west-1
    vpc_cidr: 10.0.0.0/16
  variablesFrom:
    - secretRef:
        name: demo-cluster-secrets
  controlPlaneEndpoint:           # (2)!
    host: demo-api.example.com
    port: 6443
  drift:
    intervalSeconds: 900          # (3)!
    action: Remediate
  applyPolicy: Manual             # (4)!
  defaults:                       # (5)!
    identityRef:
      name: aws
    jobs:
      activeDeadlineSeconds: 3600
    drift:
      intervalSeconds: 1800
```

1. `lockTimeoutSeconds` must stay below `activeDeadlineSeconds`. See
   [Validation](#validation).
2. Optional. Set it only when you own the endpoint (a fixed DNS name or
   VIP). Omit it and the controller copies the module's
   `control_plane_endpoint` output here once. It is immutable after that.
3. This cluster is checked every 15 minutes and drift is reverted
   automatically.
4. Every change is planned first and waits for `captf.io/approve-plan`.
5. Inherited by this cluster's machines and pools. It never applies to
   the `TerraformCluster` itself.

## Spec

`spec` must set at least one property, and `spec.source` and
`spec.identityRef` are required in practice (see
[Validation](#validation)). The fields shared with the other
Job-running kinds are documented on
[Common fields](common-fields.md); the table links each one.

| Field | Type | Description |
| --- | --- | --- |
| `spec.source` | object | The module image to run and how to pull it. See [Source](common-fields.md#source). **Required.** `spec.source.image` must be a valid image reference. |
| `spec.identityRef` | object | The `TerraformClusterIdentity` that supplies cloud credentials to the Jobs. See [Identity reference](common-fields.md#identity-reference). **Required.** |
| `spec.jobs` | object | Job policy: deadline, lock timeout, resources, service account, security context and history limits. See [Jobs](common-fields.md#jobs). **Mutable.** |
| `spec.variables` | object | Inline module variables, a JSON object. See [Variables](common-fields.md#variables). **Mutable.** |
| `spec.variablesFrom` | array | ConfigMaps and Secrets that supply module variables, at most 16. See [Variable sources](common-fields.md#variable-sources). **Mutable.** |
| `spec.controlPlaneEndpoint` | object | The API server endpoint. See [Control-plane endpoint](#control-plane-endpoint). |
| `spec.drift` | object | Drift detection policy. See [Drift](#drift). **Mutable.** |
| `spec.applyPolicy` | string | When a change is applied. See [Apply policy](#apply-policy). **Default:** `Automatic`. **Mutable.** |
| `spec.defaults` | object | Values this cluster's machines and pools inherit. See [Defaults](#defaults). **Mutable.** |

### Control-plane endpoint

`spec.controlPlaneEndpoint` is the host and port of the workload
cluster's API server. A value you set is passed to the module as its
`control_plane_endpoint` input, which tells the module to use it instead
of creating a load balancer. When you leave it unset and the module
outputs an endpoint, the controller writes that output here once and
records `module` in the `captf.io/endpoint-source` annotation. Cluster
API then copies the endpoint to `Cluster.spec.controlPlaneEndpoint`. The
[module contract](../../module-author/contract/v1alpha1/cluster.md#control_plane_endpoint-input)
describes the input rules, including the fallback to
`Cluster.spec.controlPlaneEndpoint`.

| Field | Type | Description |
| --- | --- | --- |
| `spec.controlPlaneEndpoint` | object | Optional. **Default:** unset. The controller fills it from the module's output when you do not. **Mutable** until it has a host and a port, then **Immutable.** |
| `spec.controlPlaneEndpoint.host` | string | The API server hostname or IP address. **Range:** 1 to 512 characters. Set together with `port`. |
| `spec.controlPlaneEndpoint.port` | integer | The API server port. **Range:** 1 to 65535. Set together with `host`. |

!!! warning "A complete endpoint cannot be changed or cleared"

    Every Machine and kubeconfig of the cluster points at the endpoint,
    so the webhook rejects any change once both `host` and `port` are
    set. To use a different endpoint, create a new cluster.

### Drift

`spec.drift` controls the periodic check that compares the real
infrastructure with the module. See
[Drift and health](../../concepts/drift-and-health.md) for what runs and
when, and [Drift](../../user-guide/drift.md) for how to use it.

| Field | Type | Description |
| --- | --- | --- |
| `spec.drift` | object | Optional. **Default:** unset; both fields below then take their defaults. **Mutable.** |
| `spec.drift.intervalSeconds` | integer | Seconds between drift checks. **Default:** the manager's `--drift-default-interval` (30 minutes), applied at reconcile; see [Manager flags](../manager-flags.md). **Range:** 0 or more. `0` disables drift checks, and with them every health sample after provisioning. **Mutable.** |
| `spec.drift.action` | string | What happens when a check finds changes. **Default:** `Report`, applied at reconcile. **Allowed values:** `Report` (record the finding only), `Remediate` (apply the current inputs and revert out-of-band changes). **Mutable.** |

!!! warning "Disabling drift also stops health sampling"

    With `spec.drift.intervalSeconds: 0` the `InfrastructureHealthy`
    condition stops updating after provisioning, because health is read
    only from a completed refresh or drift Job. See
    [Disable drift checks](../../user-guide/drift.md#disable-drift-checks).

### Apply policy

| Field | Type | Description |
| --- | --- | --- |
| `spec.applyPolicy` | string | **Default:** `Automatic`, applied at reconcile. **Allowed values:** `Automatic`, `Manual`. **Mutable.** |

With `Automatic`, every change to the inputs, and every drift
remediation, applies as soon as the controller sees it. Only a plan that
deletes or replaces resources waits, for the
`captf.io/approve-destructive-plan` annotation. With `Manual`, the
controller runs a plan Job first, publishes the result in
[`status.plan`](#status), and applies it only when the
`captf.io/approve-plan` annotation names `status.plan.planHash`. The apply
runs only if it plans exactly the same changes again. The first apply of
a new cluster, which has no state yet, is never gated. See
[Plan approval](../../user-guide/plan-approval.md#plan-preview-applypolicy-manual)
and [Manual approval](../../concepts/approvals/manual-approval.md).

### Defaults

`spec.defaults` holds values the cluster's `TerraformMachine` and
`TerraformMachinePool` objects inherit field by field: a value a machine
or pool sets wins, an unset one comes from here. The values never apply
to the `TerraformCluster` itself, and there is no `source` because every
role names its own image.

| Field | Type | Description |
| --- | --- | --- |
| `spec.defaults` | object | Optional. **Mutable.** |
| `spec.defaults.identityRef` | object | The identity of machines and pools that set no `identityRef`. **Default:** `spec.identityRef`. Same shape as [Identity reference](common-fields.md#identity-reference). |
| `spec.defaults.identityRef.name` | string | The name of the `TerraformClusterIdentity`. |
| `spec.defaults.jobs` | object | A Job policy merged field by field under each machine's or pool's own `jobs`. Same type as `spec.jobs`; see [Jobs](common-fields.md#jobs). It is validated like `spec.jobs`. |
| `spec.defaults.drift` | object | A drift policy merged field by field under each machine's or pool's own `drift`. It has no `action`: a machine always reports, and a pool sets its own. |
| `spec.defaults.drift.intervalSeconds` | integer | **Default:** the manager's `--drift-default-interval`. **Range:** 0 or more. `0` disables a machine's drift checks but not a pool's, which then uses the manager default. |

See [Templates and ClusterClass](../../user-guide/clusterclass.md) and
[Identities](../../user-guide/identities.md) for the usual setup.

## Status

Nothing in `status` is load-bearing: the controller rebuilds every value
from the spec, the state Secret, the durable inputs Secret or the Job
list, and `clusterctl move` does not carry status over.

| Field | Type | Description |
| --- | --- | --- |
| `status.conditions` | array | Conditions of the object, at most 32, keyed by `type`. See [Conditions](#conditions). |
| `status.conditions[].type` | string | The condition type, such as `Ready`. |
| `status.conditions[].status` | string | `True`, `False` or `Unknown`. |
| `status.conditions[].reason` | string | A CamelCase reason; see [Conditions](../conditions.md). |
| `status.conditions[].message` | string | A human-readable detail. It can name a Job and plan counts but never a variable value. |
| `status.conditions[].lastTransitionTime` | time | When `status` last changed. |
| `status.conditions[].observedGeneration` | integer | The `metadata.generation` the condition was computed for. |
| `status.initialization` | object | Cluster API's initialization status; holds `provisioned`. See [Initialization](common-fields.md#initialization). |
| `status.observedGeneration` | integer | The generation this status was computed for. See [Observed generation](common-fields.md#observed-generation). |
| `status.activeJob` | object | The Job running for this object now, if any. See [Active job](common-fields.md#active-job). |
| `status.lastRun` | object | The result of the most recent completed Job. See [Last run](common-fields.md#last-run). |
| `status.lastDriftCheck` | time | When the last drift check completed. See [Drift checks and refreshes](common-fields.md#drift-checks-and-refreshes). |
| `status.lastRefresh` | time | When the last refresh or drift check completed. See [Drift checks and refreshes](common-fields.md#drift-checks-and-refreshes). |
| `status.pendingRefreshes` | integer | Consecutive refreshes that read health as pending. See [Drift checks and refreshes](common-fields.md#drift-checks-and-refreshes). |
| `status.observedStateSerial` | integer | The state serial the outputs were read from. See [State](common-fields.md#state). |
| `status.lastRestoredSerial` | integer | The serial of the last restore Job consumed. See [State](common-fields.md#state). |
| `status.stateSecretSuffix` | string | The backend `secret_suffix` of this object's state. See [State](common-fields.md#state). |
| `status.stateBackups` | array | The state backups kept, newest first, at most 16. See [State](common-fields.md#state). |
| `status.source` | object | What the last Job actually ran. See [Image in use](common-fields.md#image-in-use). |
| `status.failureDomains` | array | The failure domains from the module's `failure_domains` output. Between 1 and 100 entries, keyed by `name`. Cluster API uses them to spread control-plane Machines. |
| `status.failureDomains[].name` | string | **Required.** The failure domain name. **Range:** 1 to 256 characters. |
| `status.failureDomains[].controlPlane` | boolean | Whether control-plane machines may use this domain. |
| `status.failureDomains[].attributes` | map | Free-form string attributes the module reports for the domain. |
| `status.exports` | any JSON value | A copy of the module's `exports` output, published for consumers outside CAPTF to read through the Kubernetes API. Absent or null exports publish `{}`. Not published, and the field cleared, when the compact JSON exceeds 64 KiB (65536 bytes); the manager then emits the `ExportsNotPublished` Warning event. Not set for an externally managed cluster. Readable by anyone who can `get` the object, so it must never hold secrets. The controller never reads it back. |
| `status.plan` | object | The change waiting for approval under `spec.applyPolicy: Manual`. Empty when none waits. Approve it by setting `captf.io/approve-plan` to `status.plan.planHash`. |
| `status.plan.inputsHash` | string | **Required** when a plan is set. The hash of the inputs the plan was made for. **Range:** 1 to 128 characters. |
| `status.plan.job` | string | **Required** when a plan is set. The Job that made the plan: a plan Job, or an approved apply that found the plan changed. **Range:** 1 to 63 characters. |
| `status.plan.planHash` | string | **Required** when a plan is set. A fingerprint of the plan's changes, and the value that approves it. **Range:** 1 to 128 characters. |
| `status.plan.add` | integer | Resources the plan creates. **Range:** 0 or more. |
| `status.plan.change` | integer | Resources the plan updates in place. **Range:** 0 or more. |
| `status.plan.destroy` | integer | Resources the plan destroys, counting replacements. **Range:** 0 or more. |
| `status.plan.outputChanges` | integer | Root module outputs the plan changes. An output change alone needs approval, because cluster exports feed every machine and pool module. **Range:** 0 or more. |
| `status.plan.resources` | array of strings | `<address> (<labels>)` of each changed resource, sorted by address, at most 50, each 1 to 600 characters. The labels are the action (`create`, `update`, `delete`, `replace`, `read` or `forget`), or `import` or `move` for an otherwise unchanged resource, comma-separated: `aws_instance.a (import)`. Values are never shown. |
| `status.plan.truncated` | boolean | `true` when `status.plan.resources` lists fewer resources than the plan changes. |
| `status.plan.createdAt` | time | When the plan was made. |

`status` must set at least one property when present.

??? example "Example status"

    ```yaml
    status:
      conditions:
        - type: Ready
          status: "True"
          reason: Ready
          observedGeneration: 3
          lastTransitionTime: "2026-10-02T09:14:07Z"
        - type: ApplyJobSucceeded
          status: Unknown
          reason: PlanAwaitingApproval
          message: Plan awaits approval; see status.plan
          observedGeneration: 3
          lastTransitionTime: "2026-10-02T11:40:12Z"
        - type: EndpointAvailable
          status: "True"
          reason: EndpointAvailable
          observedGeneration: 3
          lastTransitionTime: "2026-10-02T09:14:07Z"
      initialization:
        provisioned: true
      observedGeneration: 3
      failureDomains:
        - name: eu-west-1a
          controlPlane: true
        - name: eu-west-1b
          controlPlane: true
      exports:
        schema: captf.io/aws-cluster/v1
        region: eu-west-1
      lastRun:
        job: demo-plan-4f7c2
        operation: plan
      lastRefresh: "2026-10-02T11:30:01Z"
      source:
        image: ghcr.io/captf-io/module-images/aws-cluster:v0.1.0-opentofu
      plan:
        inputsHash: 9a1c0f3e6d5b
        job: demo-plan-4f7c2
        planHash: 7be2d41a0c93
        add: 1
        change: 2
        destroy: 0
        outputChanges: 0
        resources:
          - aws_security_group_rule.api (create)
          - aws_lb.api (update)
          - aws_lb_listener.api (update)
        truncated: false
        createdAt: "2026-10-02T11:40:12Z"
    ```

## Conditions

A `TerraformCluster` sets the conditions below. Each section of
[Conditions](../conditions.md) lists every reason and what it means; this
page does not copy them.

| Type | `True` | `False` | `Unknown` |
| --- | --- | --- | --- |
| [`Ready`](../conditions.md#ready) | Every input is healthy. Cluster API mirrors it into the `Cluster`'s `InfrastructureReady`. | An input is `False`. | An input is `Unknown`. |
| [`DependenciesReady`](../conditions.md#dependenciesready) | The `Cluster` and everything the object waits for exist. | The owner `Cluster` is missing or does not reference this object back, the `Cluster` references another provider, or a `variablesFrom` source is missing or invalid. | Still waiting for the owner. |
| [`IdentityAllowed`](../conditions.md#identityallowed) | The identity exists and allows the namespace. | No identity is set, the identity is missing, does not allow the namespace or has no Secret. | The identity check could not be completed. |
| [`CredentialsMirrored`](../conditions.md#credentialsmirrored) | The identity's Secret is copied for the Job. | It cannot be copied. | The mirror is pending: it has not been made yet, or no identity resolved. |
| [`RunnerRBACReady`](../conditions.md#runnerrbacready) | The runner's ServiceAccount and RBAC exist. | They cannot be created, or an override ServiceAccount lacks the `captf.io/runner=true` label. | Never `Unknown`. Until the controller first reaches it, the condition is absent and counts as `Unknown` in `Ready`. |
| [`ApplyJobSucceeded`](../conditions.md#applyjobsucceeded) | The last apply or destroy succeeded. | It failed, hit its deadline or could not start, or a destructive plan is blocked. | No apply has completed yet, the run waits for a lease or for the cluster's machines and pools, or a plan awaits approval or changed. A running apply keeps the last result. |
| [`StateReadable`](../conditions.md#statereadable) | The Terraform state can be read. | It is encrypted, corrupt, inconsistent, lost or locked by another holder. | No state exists yet. |
| [`RestoreJobSucceeded`](../conditions.md#restorejobsucceeded) | The last state restore succeeded. | It failed, or the requested backup does not exist. | The restore waits for a run lease or for other operations. Set only once a restore is requested with `captf.io/restore-state`. |
| [`OutputsValid`](../conditions.md#outputsvalid) | The module's outputs satisfy the contract. | An output is missing or invalid. | Required outputs are still `null`. |
| [`InfrastructureHealthy`](../conditions.md#infrastructurehealthy) | The module's health output reads healthy. | It is provisioning, or it reads pending, unhealthy, degraded, stopped or terminated. | Before the first apply, or health is unknown. |
| [`DriftJobSucceeded`](../conditions.md#driftjobsucceeded) | The last drift or refresh Job succeeded. | It failed or hit its deadline. | No check has completed, a Job is running or waits for a lease, or the durable inputs Secret is missing. |
| [`DriftDetected`](../conditions.md#driftdetected) | The last drift check found changes: reported, pending remediation or being remediated. | It found none. | No check has completed. |
| [`DeletionBlocked`](../conditions.md#deletionblocked) | Machines or pools of the cluster still exist, so the destroy waits. | Nothing blocks the destroy. | Never `Unknown`. |
| [`EndpointAvailable`](../conditions.md#endpointavailable) | A valid control-plane endpoint is known. | The cluster is provisioned but has no endpoint. | Never `Unknown`; the condition is not set before provisioning. |
| [`Paused`](../conditions.md#paused) | The object or its `Cluster` is paused. | It is not paused. | Never `Unknown`. |
| [`Deleting`](../conditions.md#deleting) | The object is being deleted. It makes `Ready` `False`. | It is not. | Never `Unknown`. |

`DriftDetected`, `DeletionBlocked` and `DriftJobSucceeded` have negative
or informational meaning and never feed `Ready`; `DeletionBlocked`
and `DriftDetected` read `True` when something needs attention.
After provisioning, `Ready` summarizes only `InfrastructureHealthy` and
`Deleting`, so a failed re-apply does not flip the `Cluster`'s
`InfrastructureReady` and suspend its MachineHealthChecks. See
[Ready summarization](../conditions.md#ready-summarization).

## Printer columns

`kubectl get terraformclusters` shows:

| Column | Source | Notes |
| --- | --- | --- |
| `CLUSTER` | The `cluster.x-k8s.io/cluster-name` label | The owning `Cluster`. |
| `READY` | `status.conditions` entry of type `Ready` | Its `status`. |
| `PROVISIONED` | `status.initialization.provisioned` | |
| `ENDPOINT` | `spec.controlPlaneEndpoint.host` | |
| `IMAGE` | `spec.source.image` | Only with `-o wide`. |
| `AGE` | `metadata.creationTimestamp` | |

## Validation

The validating webhook (`validation.terraformcluster.infrastructure.cluster.x-k8s.io`)
and the CRD schema enforce these rules on create and update. The webhook
reports every violation it finds at once.

**Required fields**

- `spec` must set at least one property.
- `spec.source.image` must be set and a valid image reference. The image's
  content and registry are not checked.
- `spec.identityRef.name` must be set. `spec.defaults.identityRef` is not
  a substitute: it only applies to machines and pools.

**Immutable fields**

- `spec.controlPlaneEndpoint` is mutable until it has both a host and a
  port. After that, any change or removal is rejected. A half-set
  endpoint stored earlier stays completable, and unrelated updates to it
  are not rejected.
- Every other field is mutable. A new `spec.source.image` is a new module
  version, applied against the existing state.

**Cross-field and range rules**

- `spec.controlPlaneEndpoint` must set both `host` and `port`, or neither.
  `host` is 1 to 512 characters and `port` is 1 to 65535.
- `spec.applyPolicy` must be `Automatic` or `Manual`.
- `spec.drift.action` must be `Report` or `Remediate`.
  `spec.drift.intervalSeconds` and `spec.defaults.drift.intervalSeconds`
  must be 0 or more.
- `spec.jobs` and `spec.defaults.jobs` are validated only when they
  change, so an older policy never blocks a finalizer patch:
    - The container and pod security contexts may not weaken the
      hardened defaults: no privileged mode, privilege escalation, added
      capabilities, writable root filesystem, unmasked `/proc`,
      `runAsNonRoot: false`, `runAsUser: 0`, `Unconfined` seccomp profile
      or Windows host process.
    - `lockTimeoutSeconds` must be less than `activeDeadlineSeconds`. When
      only one is set, it is compared with the other's built-in default
      (a 300 second lock timeout, a 3600 second deadline).
- `spec.variables` must be a JSON object of at most the contract's
  maximum number of keys. Each key must be a Terraform identifier that
  is not a `captf_` name, a cluster-role contract input or a module
  meta-argument.
- Each `spec.variablesFrom[]` entry must set exactly one of `configMapRef`
  and `secretRef`; there are at most 16 entries. Keys in the referenced
  sources are checked at reconcile, not at admission.
- `status.conditions` holds at most 32 entries and `status.failureDomains`
  at most 100.

**Defaulting.** The CRD declares no defaults. The controller applies
`Automatic` for `spec.applyPolicy`, `Report` for `spec.drift.action` and
the manager's `--drift-default-interval` for `spec.drift.intervalSeconds`
at reconcile; the stored object stays as you wrote it.

Deleting a `TerraformCluster` is always admitted. On a deleting object the
Job policy rules are skipped, so its finalizer stays removable.

## Lifecycle

On create, the controller waits for the owning `Cluster`, resolves the
identity, mirrors credentials, prepares the runner's RBAC and runs an
apply Job. After the apply it validates the module's outputs, writes the
endpoint and failure domains, publishes the module's `exports` to
`status.exports` and sets `status.initialization.provisioned`.
The controller refreshes `status.exports` on every reconcile that reads
the state, and never reads it back; machines and pools take the exports
from the state, not from status. Machines and pools wait for the
cluster's apply to finish. See
[The reconcile lifecycle](../../concepts/lifecycle.md) and
[Job inputs](../../concepts/inputs.md).

On change, the controller compares the rendered inputs with the last
applied ones and runs a new apply. A plan that deletes or replaces
resources waits for approval, and under `Manual` every change does. See
[Approvals](../../concepts/approvals/README.md). Between changes it runs
refresh and drift Jobs on the interval in `spec.drift`; see
[Drift and health](../../concepts/drift-and-health.md).

On delete, the controller holds the destroy while any machine or pool
of the cluster still exists (`DeletionBlocked`), then runs a destroy Job
and removes the finalizer. A missing or unreadable state, or a failed
destroy, holds the deletion until you restore the state or abandon the
object. See [Deletion](../../concepts/deletion/README.md) and
[Deletion order](../../concepts/lifecycle.md#deletion-order).

!!! related "See also"

    - [Common fields](common-fields.md)
    - [TerraformClusterTemplate](terraformclustertemplate.md)
    - [TerraformMachine](terraformmachine.md)
    - [TerraformMachinePool](terraformmachinepool.md)
    - [TerraformClusterIdentity](terraformclusteridentity.md)
    - [Conditions](../conditions.md)
    - [Annotations and labels](../annotations-labels.md)
    - [Manager flags](../manager-flags.md)
    - [Cluster role contract](../../module-author/contract/v1alpha1/cluster.md)
