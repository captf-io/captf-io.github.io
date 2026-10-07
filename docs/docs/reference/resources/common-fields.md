---
title: "Common Fields in CAPTF Custom Resources"
description: "Reference for the spec and status fields TerraformCluster, TerraformMachine and TerraformMachinePool share: source, identity, Jobs, variables, deletion, status."
icon: lucide/component
subtitle: "Fields the module kinds share"
---

# Common Fields

`TerraformCluster`, `TerraformMachine` and `TerraformMachinePool` embed one
shared set of fields. In Go they are `WorkspaceSpec` and `WorkspaceStatus`;
in YAML they sit directly under `spec` and `status` of each kind. This page
documents them once, in full. Each kind's own page ([TerraformCluster](terraformcluster.md),
[TerraformMachine](terraformmachine.md),
[TerraformMachinePool](terraformmachinepool.md)) lists them, notes what
differs for that kind, and links here for the details.

`TerraformCluster` also takes the same Job policy as `spec.defaults.jobs`,
which its machines and pools inherit; see [Jobs](#jobs).

Kind-specific behavior shows up in four places on this page: whether a
field can change after creation, whether `spec.identityRef` is required,
how `spec.jobs` merges with the cluster's defaults, and where an unset
`spec.deletionPolicy` comes from. Each is called out per field.

Defaults on this page come from the admission webhook, the controllers or
the manager's flags. The CRDs declare no schema defaults, so an unset field
stays unset in the stored object and the default is applied when the Job is
built or at reconcile.

## Source

`spec.source` names the module image. It is **required** on every kind. The
image bundles the role module's Terraform or OpenTofu code and the runtime
binary at fixed paths; there is no separate module source and no separate
runtime image. See the [image contract](../../module-author/image-contract.md)
for the layout.

| Field | Type | Description |
| --- | --- | --- |
| `spec.source` | `object` | The role image. **Required.** |
| `spec.source.image` | `string` | The OCI image reference, `registry/repo:tag` or `registry/repo@sha256:<digest>`. The tag or digest is the module version. **Required.** **Range:** 1 to 512 characters. The webhook parses it as a normalized image reference and rejects a syntax error; it does not check the registry or the image content. |
| `spec.source.imagePullPolicy` | `string` | Pull policy of the Job's main container. **Default:** `IfNotPresent`, applied when the Job is built. **Allowed values:** `IfNotPresent`, `Always`, `Never`. Use `Always` with a mutable tag. |

**Mutability.** `spec.source` is mutable on a `TerraformCluster` and a
`TerraformMachinePool`: a new image is a new module version, applied against
the existing state. It is **immutable** on a `TerraformMachine`; the webhook
rejects any change, so you roll the machine by creating a new one (usually
through a new template).

```yaml title="Pin the module by digest"
spec:
  source:
    image: ghcr.io/example/cluster-module@sha256:3f1c0e9d5a7b2c64e8f1a0b9d7c3e5f2a4b6c8d0e1f3a5b7c9d1e3f5a7b9c1d3
    imagePullPolicy: IfNotPresent
```

!!! danger "Referencing an image grants its publisher access to this namespace"

    The module runs in a Job that can read Secrets and holds cloud
    credentials in this namespace. Whoever can publish to the image
    reference can run code with that access. Pin by digest, or use a
    registry and tag policy you control. See [Security
    model](../../concepts/security-model.md).

## Identity reference

`spec.identityRef` names the cluster-scoped `TerraformClusterIdentity` whose
credentials the object's Jobs use. See [Identities and
Credentials](../../user-guide/identities.md#reference-it) for creating an
identity and how its credentials reach a Job.

| Field | Type | Description |
| --- | --- | --- |
| `spec.identityRef` | `object` | The identity to use. Whether it is required depends on the kind (below). |
| `spec.identityRef.name` | `string` | The `TerraformClusterIdentity` name. **Required** when `spec.identityRef` is set. **Range:** 1 to 253 characters. |

How the identity resolves depends on the kind:

- A `TerraformCluster` uses only its own `spec.identityRef`. It is
  required: the webhook rejects a cluster without it, and
  `spec.defaults.identityRef` does not apply to the cluster itself. A
  `TerraformClusterTemplate` may leave it to a ClusterClass patch.
- A `TerraformMachine` or `TerraformMachinePool` uses its own
  `spec.identityRef`, else the cluster's `spec.defaults.identityRef`, else
  the cluster's `spec.identityRef`. If none is set, `IdentityAllowed` is
  `False` with reason `IdentityNotFound`.

**Mutability.** Mutable on a `TerraformCluster` and a
`TerraformMachinePool`. **Immutable** on a `TerraformMachine`.

```yaml
spec:
  identityRef:
    name: aws-prod
```

## Jobs

`spec.jobs` tunes the Kubernetes Jobs that run the module: deadlines, lock
waits, history, ServiceAccount, resources, environment and security
contexts. Every field is optional. It is mutable on all three kinds,
including a provisioned `TerraformMachine`, so you can change a stuck
machine's deadline without replacing it.

`TerraformCluster` also has `spec.defaults.jobs`, the same type. A
`TerraformCluster` ignores its own `spec.defaults.jobs` and uses only
`spec.jobs`; machines and pools merge it under their own `spec.jobs`. See
[Inheritance](#inheritance).

| Field | Type | Description |
| --- | --- | --- |
| `spec.jobs` | `object` | The Job policy. |
| `spec.jobs.successfulJobsHistoryLimit` | `integer` | How many succeeded Jobs to keep per object and operation. The newest succeeded Job of each operation is kept even at 0. **Default:** 3, applied at reconcile. **Range:** 0 to 100. |
| `spec.jobs.failedJobsHistoryLimit` | `integer` | How many failed Jobs to keep per object and operation. The newest failed Job of an operation is kept even at 0 while no newer Job of that operation succeeded, because retry backoff counts it. **Default:** 3, applied at reconcile. **Range:** 0 to 100. |
| `spec.jobs.activeDeadlineSeconds` | `integer` | Bounds a Job's run time, in seconds. A Job that reaches it is interrupted like an eviction and counts as a failure. **Default:** 3600, applied at reconcile when unset. **Range:** 1 to 86400 (one day). Must be greater than `lockTimeoutSeconds`. |
| `spec.jobs.lockTimeoutSeconds` | `integer` | How long the runtime waits for the state lock, passed as `-lock-timeout`. **Default:** 300, applied at reconcile. **Range:** 0 to 3600. Must be less than `activeDeadlineSeconds`. |
| `spec.jobs.serviceAccountName` | `string` | Overrides the runner ServiceAccount. **Default:** the controller creates `captf-runner`, bound to the static `captf-runner` ClusterRole. An override must exist and carry the label `captf.io/runner=true`, or no Job is created. **Range:** 1 to 253 characters. |
| `spec.jobs.imagePullSecrets` | `[]object` | Pull secrets for the Job pod. They cover both the source image and the runner's init image. Each item is a Kubernetes `LocalObjectReference` (`name`). **Range:** 1 to 10 items. See [Kubernetes fields](#kubernetes-fields). |
| `spec.jobs.resources` | `object` | Resource requests and limits of the main container. **Default:** requests of 250m CPU and 512Mi memory, a 2Gi memory limit and no CPU limit. See [Kubernetes fields](#kubernetes-fields). |
| `spec.jobs.env` | `[]object` | Environment variables added to the main container. Keyed by `name`. **Range:** 1 to 64 items. See [Kubernetes fields](#kubernetes-fields). |
| `spec.jobs.securityContext` | `object` | Security context of the main container. Hardened defaults apply and the webhook rejects weakening it. See [Kubernetes fields](#kubernetes-fields). |
| `spec.jobs.podSecurityContext` | `object` | Security context of the Job pod. See [Kubernetes fields](#kubernetes-fields). |

Jobs never retry pods (`backoffLimit` is 0) and never get a TTL. The
controller owns retries and prunes finished Jobs itself, which is what the
history limits control. See [Retries](../../concepts/jobs/retries.md) and
[Deadlines](../../concepts/jobs/deadlines.md).

```yaml title="A tuned job policy"
spec:
  jobs:
    activeDeadlineSeconds: 7200
    lockTimeoutSeconds: 600
    successfulJobsHistoryLimit: 1
    failedJobsHistoryLimit: 5
    serviceAccountName: team-runner
    imagePullSecrets:
      - name: ghcr-pull
    resources:
      requests:
        cpu: "1"
        memory: 1Gi
      limits:
        memory: 4Gi
```

### Deadline and lock rules

The webhook checks one policy at a time, on create and whenever the jobs
policy changes:

- When both are set, `lockTimeoutSeconds` must be less than
  `activeDeadlineSeconds`.
- When only `activeDeadlineSeconds` is set, it must be greater than the
  built-in lock timeout, 300.
- When only `lockTimeoutSeconds` is set, it must be less than the built-in
  deadline, 3600. `lockTimeoutSeconds: 4000` alone is rejected.

The webhook cannot see a machine's or pool's merge with the cluster's
defaults. Reconcile checks the merged policy, and an inconsistent result
sets `ApplyJobSucceeded` to `False` with reason `JobPolicyInvalid`; no Job
runs until you fix one of the two values. See [Tuning
Jobs](../../user-guide/job-tuning.md#deadlines-and-lock-waits).

### Kubernetes fields

These fields use Kubernetes' own types. This page does not list their keys;
see the linked Kubernetes API reference for each.

`spec.jobs.env`
:   A list of [`EnvVar`](https://kubernetes.io/docs/reference/kubernetes-api/core/pod-v1/#EnvVar)
    added to the main container (the one that runs your module). An entry
    whose name starts with `TF_` or `KUBE_` is accepted but silently left
    out of the Job, with no event: the runner and the Job own that
    namespace. See
    [Job Environment](../environment.md#specjobsenv-rejected-names).

`spec.jobs.resources`
:   A [`ResourceRequirements`](https://kubernetes.io/docs/reference/kubernetes-api/core/pod-v1/#ResourceRequirements)
    applied to the main container as a whole. The init container that copies
    the runner binary is not configurable. See [Default
    resources](../environment.md#default-resources).

`spec.jobs.securityContext`
:   A [`SecurityContext`](https://kubernetes.io/docs/reference/kubernetes-api/core/pod-v1/#SecurityContext)
    for the main container. The controller applies these defaults when it
    builds the Job: `seccompProfile` `RuntimeDefault`, `capabilities` drop
    `ALL`, `allowPrivilegeEscalation` `false` and `readOnlyRootFilesystem`
    `true`. `runAsNonRoot` is not defaulted. The container holds cloud
    credentials, so the webhook rejects `privileged: true`,
    `allowPrivilegeEscalation: true`, any `capabilities.add`,
    `readOnlyRootFilesystem: false`, an `Unconfined` seccomp profile,
    `procMount: Unmasked`, `windowsOptions.hostProcess: true`, and an
    explicit `runAsUser: 0` or `runAsNonRoot: false`.

`spec.jobs.podSecurityContext`
:   A [`PodSecurityContext`](https://kubernetes.io/docs/reference/kubernetes-api/core/pod-v1/#PodSecurityContext)
    for the Job pod. The controller defaults `seccompProfile` to
    `RuntimeDefault` and `fsGroup` to the runner's UID (65532), so a
    non-root image user can read the 0440 credential files through the
    group. The webhook applies the same seccomp, root and host-process
    rules as for the container.

`spec.jobs.imagePullSecrets`
:   A list of [`LocalObjectReference`](https://kubernetes.io/docs/reference/kubernetes-api/definitions/local-object-reference-v1/)
    naming Secrets in the object's namespace.

!!! warning "The webhook does not stop an image that runs as root by default"

    It rejects only an explicit root setting. The Job sets neither
    `runAsUser` nor `runAsNonRoot`, so an image whose own `USER` is root is
    admitted and runs as root. Set `runAsNonRoot: true` or a non-zero
    `runAsUser` to require otherwise. See [Tuning
    Jobs](../../user-guide/job-tuning.md#security-contexts).

### Inheritance

A `TerraformMachine` or `TerraformMachinePool` merges its `spec.jobs` field
by field over its cluster's `spec.defaults.jobs`, and those over the
`TerraformCluster`'s own `spec.jobs`. A field the object sets wins; an
unset one comes from the defaults, then from the cluster's own policy; a
field none sets gets the built-in default. Defaults are resolved at reconcile time and never
persisted, so raising a cluster's `spec.defaults.jobs` reaches existing
machines and pools on their next reconcile, as does a provider upgrade that
changes a built-in default.

| Field | Merge |
| --- | --- |
| `spec.jobs.env` | By `name`: the object's entries win on the same name, then the defaults' remaining entries. |
| `spec.jobs.imagePullSecrets` | Union of both lists, the object's first, without duplicates. |
| `spec.jobs.resources`, `spec.jobs.securityContext`, `spec.jobs.podSecurityContext` | Replaced as a whole: setting one on the object drops the default's value entirely. |
| Every other `spec.jobs` field | The object's value, else the default's, else the built-in. |

```yaml title="One policy for every machine and pool"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformCluster
metadata:
  name: prod
spec:
  defaults:
    jobs:
      activeDeadlineSeconds: 5400
      imagePullSecrets:
        - name: ghcr-pull
```

See [What a cluster passes to its machines and
pools](../../concepts/kinds.md#what-a-cluster-passes-to-its-machines-and-pools)
and [Tuning
Jobs](../../user-guide/job-tuning.md#inheriting-from-a-clusters-defaults).

## Variables

`spec.variables` passes module variables as an inline JSON object. Each key
becomes a named argument of the role module, converted by the module's
declared type. A key the module does not declare fails the apply with
"Unsupported argument".

| Field | Type | Description |
| --- | --- | --- |
| `spec.variables` | `map` | The variables, a JSON object of any values. Inline variables win over every `spec.variablesFrom` source. **Range:** when set, 1 to 256 keys. |

Each key must be a Terraform identifier matching
`^[a-zA-Z_][a-zA-Z0-9_-]*$`. The webhook also rejects a key that:

- starts with `captf_`;
- is a contract input of the object's role (a machine cannot set
  `machine_name`, but a cluster can);
- is a module meta-argument: `source`, `version`, `providers`, `count`,
  `for_each`, `depends_on`, `lifecycle` or `locals`.

A value that is not a JSON object is rejected. Error messages name the key,
never the value.

**Mutability.** Mutable on a `TerraformCluster` and a
`TerraformMachinePool`: a change is part of the inputs hash and re-applies
the module (guarded on a cluster by its [apply
policy](../../user-guide/plan-approval.md)). **Immutable** on a
`TerraformMachine`. Variables are never inherited from `spec.defaults`.

```yaml title="Inline variables"
spec:
  variables:
    region: eu-west-1
    node_count: 3
    tags:
      team: platform
      env: prod
```

Inline variables are not sensitive, and every variable is stored in the
inputs Secrets and in state. For merge order and the full story, see
[Module Variables](../../user-guide/variables.md#merge-order-and-formats).

## Variable sources

`spec.variablesFrom` reads module variables from ConfigMaps and Secrets in
the object's own namespace. Every data key of a source becomes a variable of
the same name. Sources apply in list order: a later source wins on a shared
key, and inline `spec.variables` wins over all of them.

| Field | Type | Description |
| --- | --- | --- |
| `spec.variablesFrom` | `[]object` | The sources. **Range:** 1 to 16 items. The list is replaced as a whole on update. |
| `spec.variablesFrom[].configMapRef` | `object` | Names a ConfigMap. Set exactly one of `configMapRef` and `secretRef`; the webhook rejects both or neither. |
| `spec.variablesFrom[].configMapRef.name` | `string` | The ConfigMap name. **Required** when `configMapRef` is set. **Range:** 1 to 253 characters. **Allowed values:** a DNS subdomain name, `^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$`. |
| `spec.variablesFrom[].secretRef` | `object` | Names a Secret. Set exactly one of `configMapRef` and `secretRef`. |
| `spec.variablesFrom[].secretRef.name` | `string` | The Secret name. **Required** when `secretRef` is set. **Range** and **Allowed values:** as for `configMapRef.name`. |
| `spec.variablesFrom[].optional` | `boolean` | When true, a missing or unlabeled source contributes nothing. When false, it holds the object at `DependenciesReady` `False` with reason `VariablesSourceNotFound`. **Default:** `false`. |
| `spec.variablesFrom[].format` | `string` | How data values are passed. `String` passes each value as a string and lets the module's declared type convert it (`"3"` to a number, `"true"` to a bool). `JSON` parses each value as JSON, for lists, maps and objects; a value that is not valid JSON is `VariablesInvalid`. **Default:** `String`, applied at reconcile. **Allowed values:** `String`, `JSON`. |

The source must carry the label `captf.io/variables=true`. The manager
reads and watches only labeled sources, and an unlabeled one counts as
missing. Names in a source are checked with the same rules as inline keys,
but at reconcile, so a bad key is `VariablesInvalid` naming the key and not
a webhook rejection.

A variable whose winning value came from a Secret is declared
`sensitive = true` in the generated root, so Terraform redacts it in plan
and apply output. It is still stored in the inputs Secrets and in state.

**Mutability and effect of a change.**

| Kind | Field | Source data change |
| --- | --- | --- |
| `TerraformCluster` | Mutable. | Re-read on every reconcile; a change to a labeled, referenced source wakes the controller and re-applies the module. |
| `TerraformMachinePool` | Mutable. | The same as a cluster, but the re-apply is never guarded. |
| `TerraformMachine` | **Immutable.** | Read only until the machine is provisioned, then pinned in its inputs Secret; later edits affect only machines created afterward. |

=== "ConfigMap"

    ```yaml
    spec:
      variablesFrom:
        - configMapRef:
            name: network-vars # (1)!
          format: JSON
    ```

    1. The ConfigMap must carry `captf.io/variables: "true"`.

=== "Secret"

    ```yaml
    spec:
      variablesFrom:
        - secretRef:
            name: db-credentials
          optional: true # (1)!
    ```

    1. A missing Secret contributes nothing and does not block the object.

!!! warning "A source CAPTF does not own is not carried by `clusterctl move`"

    CAPTF puts no owner reference on a ConfigMap or Secret it reads. After a
    move, a `TerraformCluster` or `TerraformMachinePool` waits at
    `VariablesSourceNotFound` until you recreate the source in the target
    cluster.

## Deletion policy

`spec.deletionPolicy` decides what deleting the object does with the
infrastructure it manages, and `spec.adoptRetainedState` lets a new object
take over what an earlier one of the same name kept. See [Retain and
Adopt](../../concepts/deletion/retain.md) for the whole story.

| Field | Type | Description |
| --- | --- | --- |
| `spec.deletionPolicy` | `string` | **Allowed values:** `Destroy` (run a destroy Job, then delete the state), `Retain` (remove the finalizer without a destroy, leave the infrastructure running, and keep the state Secrets, the state backups and the durable inputs, labeled `captf.io/retained-from-uid`). **Default:** inherited, else `Destroy`, applied at reconcile. **Mutable**, also while the object is being deleted. |
| `spec.adoptRetainedState` | `boolean` | `true` lets the object adopt state an earlier object of the same kind, namespace and name retained. Without it such state is never adopted: `StateReadable` is `False` with reason `RetainedStateFound` and no Job runs. **Default:** unset (`false`). Never inherited. **Mutable.** |

**Inheritance.** An unset `spec.deletionPolicy` on a `TerraformMachine` or
`TerraformMachinePool` comes from its cluster's
`spec.defaults.deletionPolicy`, else from the `TerraformCluster`'s own
`spec.deletionPolicy`, else `Destroy`. A `TerraformCluster` uses only its
own value. Because the cluster's fields are mutable, setting `Retain` there
reaches machines whose template is immutable without a rollout. An
inherited policy is never guessed: when a deleting machine or pool sets
none and its `TerraformCluster` cannot be found, neither a destroy nor a
Retain runs, and `Deleting` is `True` with reason
`DeletionPolicyUnresolved` until you set `spec.deletionPolicy` on the
object.

**While deleting.** Setting `Retain` on an object that is already being
deleted releases it on the next reconcile, whatever holds it: a lost or
unreadable state, a destroy that failed, or one that cannot start. A Job
that is running finishes first.

```yaml title="Keep the infrastructure when the object is deleted"
spec:
  deletionPolicy: Retain
```

## Workspace status

Every shared status field is rebuilt from the spec, the state Secret, the
durable inputs Secret or the Job list, so none is load-bearing:
`clusterctl move` does not restore status, and the controller recomputes it.
Each kind adds its own status fields (conditions, outputs and so on) on its
own page.

| Field | Type | Description |
| --- | --- | --- |
| `status.observedGeneration` | `integer` | The `metadata.generation` this status was computed for. |
| `status.initialization` | `object` | The Cluster API v1beta2 initialization contract. |
| `status.activeJob` | `object` | The Job running now, if any. |
| `status.lastRun` | `object` | The result of the most recent completed Job. |
| `status.lastDriftCheck` | `time` | When the last drift check completed. |
| `status.lastRefresh` | `time` | When the last refresh or drift check completed. |
| `status.pendingRefreshes` | `integer` | Consecutive pending health samples. |
| `status.observedStateSerial` | `integer` | The state serial the outputs were read from. |
| `status.lastRestoredSerial` | `integer` | The serial of the last consumed restore Job. |
| `status.stateSecretSuffix` | `string` | The state backend's `secret_suffix`. |
| `status.stateBackups` | `[]object` | The kept state backups, newest first. |
| `status.source` | `object` | What the last Job ran. |

### Observed generation

`status.observedGeneration` is the `metadata.generation` the controller last
computed status for. **Range:** 1 or more; unset until the first reconcile.
When it is lower than `metadata.generation`, the status describes an older
spec.

### Initialization

| Field | Type | Description |
| --- | --- | --- |
| `status.initialization` | `object` | Cluster API's initialization status. Omitted until it has a field. |
| `status.initialization.provisioned` | `boolean` | True once the infrastructure is provisioned. |

`status.initialization.provisioned` is derived from state until it first
holds, then latched true for the object's life. It first holds when an apply
has completed, the module's outputs are valid, and the module's `health`
output is present and not `pending`. Cluster API reads it to know when the
infrastructure is ready.

### Active Job

| Field | Type | Description |
| --- | --- | --- |
| `status.activeJob` | `object` | The Job currently running for this object. Unset when none is. |
| `status.activeJob.name` | `string` | The Job name. **Range:** 1 to 63 characters. |
| `status.activeJob.operation` | `string` | The operation the Job runs. **Allowed values:** `apply`, `destroy`, `drift`, `refresh`, `restore`, `plan`. |
| `status.activeJob.attempt` | `integer` | The operation's Job sequence number, the `a<N>` in the Job name, starting at 1. It counts every Job of the operation still retained, not retries: the 40th refresh is attempt 40. **Range:** 1 or more. |
| `status.activeJob.startTime` | `time` | When the Job started. |

```yaml
status:
  activeJob:
    name: prod-apply-a3
    operation: apply
    attempt: 3
    startTime: "2026-10-02T09:14:07Z"
```

### Last run

`status.lastRun` is copied from the runner's termination message when the
newest Job finishes, so it holds the outcome of one Job whether it
succeeded or failed.

| Field | Type | Description |
| --- | --- | --- |
| `status.lastRun` | `object` | The most recent completed Job. |
| `status.lastRun.job` | `string` | The Job name. **Range:** 1 to 63 characters. |
| `status.lastRun.operation` | `string` | The operation the Job ran. **Allowed values:** `apply`, `destroy`, `drift`, `refresh`, `restore`, `plan`. |
| `status.lastRun.steps` | `[]object` | The runtime commands the runner executed, in order. **Range:** 1 to 16 items. |
| `status.lastRun.steps[].name` | `string` | The step name, such as `init`, `validate`, `plan`, `apply` or `apply-refresh-only`. **Range:** 1 to 64 characters. |
| `status.lastRun.steps[].exitCode` | `integer` | The step's exit code. |
| `status.lastRun.steps[].durationMilliseconds` | `integer` | The step's wall time in milliseconds. **Range:** 0 or more. |
| `status.lastRun.error` | `object` | Set when the run failed. |
| `status.lastRun.error.kind` | `string` | The failure class. **Allowed values:** `image-layout` (the image breaks the image contract), `step` (a runtime step failed), `interrupted` (the step was stopped from outside: a drain, an eviction, a Job deletion or its deadline), `blocked` (an apply stopped before a destructive plan that is not approved; nothing changed), `plan-changed` (an approved plan planned other changes; nothing changed). |
| `status.lastRun.error.step` | `string` | The step that failed, for kind `step`. **Range:** 1 to 64 characters. |
| `status.lastRun.error.summary` | `string` | The runner's short description of the failure. **Range:** 1 to 512 bytes. It is not raw stderr: anyone who can get the object can read status, so the full output stays in the Job's logs. |
| `status.lastRun.drift` | `object` | Set when a drift run found changes. |
| `status.lastRun.drift.create` | `integer` | Resources the plan would create. **Range:** 0 or more. |
| `status.lastRun.drift.update` | `integer` | Resources the plan would update in place. **Range:** 0 or more. |
| `status.lastRun.drift.replace` | `integer` | Resources the plan would replace: delete and create again. A replacement counts here only. **Range:** 0 or more. |
| `status.lastRun.drift.delete` | `integer` | Resources the plan would delete, not counting replacements. **Range:** 0 or more. |
| `status.lastRun.drift.resources` | `[]string` | Addresses of the drifted resources. **Range:** 1 to 20 items of 1 to 512 characters. |

```yaml
status:
  lastRun:
    job: prod-drift-a12
    operation: drift
    steps:
      - name: init
        exitCode: 0
        durationMilliseconds: 4120
      - name: plan
        exitCode: 2
        durationMilliseconds: 31877
    drift:
      create: 0
      update: 1
      replace: 0
      delete: 0
      resources:
        - aws_security_group.nodes
```

`error.kind` `blocked` and `plan-changed` are covered in [Destructive plan
guard](../../concepts/approvals/destructive-guard.md) and [Manual
approval](../../concepts/approvals/manual-approval.md).

### Drift checks and refreshes

| Field | Type | Description |
| --- | --- | --- |
| `status.lastDriftCheck` | `time` | When the last drift check completed. |
| `status.lastRefresh` | `time` | When the last refresh or drift check completed. For a kind whose apply can itself give a definite health reading, it is when that apply finished, because the reading stands in for the refresh after the apply. |
| `status.pendingRefreshes` | `integer` | The number of consecutive health samples (completed refresh or drift Jobs) that read `pending` since the last other reading or the last apply. Unset otherwise. **Range:** 1 or more. |

While health is `pending`, `status.pendingRefreshes` spaces the refreshes of
a `TerraformCluster` or `TerraformMachine`: 30 seconds, then 1, 2 and 4
minutes, and at most 5 minutes. A `TerraformMachinePool` instead refreshes
every 30 seconds flat while its health is pending or its membership is
converging, whatever the count. The count lives in status
only, so after `clusterctl move` it restarts at 0 and the spacing restarts at
30 seconds. A disabled drift interval (`spec.drift.intervalSeconds: 0`) means
no drift checks, so `status.lastDriftCheck` does not advance. See [Drift and
Health](../../concepts/drift-and-health.md#what-runs-and-when).

### State

| Field | Type | Description |
| --- | --- | --- |
| `status.observedStateSerial` | `integer` | The Terraform state serial the outputs were read from. **Range:** 1 or more. |
| `status.lastRestoredSerial` | `integer` | The backup serial of the last restore Job the controller consumed, whether it succeeded or failed, so a `captf.io/restore-state` annotation naming it does not run again. **Range:** 1 or more. |
| `status.stateSecretSuffix` | `string` | The `kubernetes` backend `secret_suffix` of this object's state. Informational: the controller derives it deterministically and never reads it back. **Range:** 1 to 63 characters. |
| `status.stateBackups` | `[]object` | The state backups the controller keeps, newest first, as of the last backup, prune or restore request. **Range:** 1 to 16 items. |
| `status.stateBackups[].serial` | `integer` | The state serial the backup holds. Set it as the `captf.io/restore-state` annotation to restore it. **Range:** 1 or more. |
| `status.stateBackups[].takenAt` | `time` | When the controller copied the state. |
| `status.stateBackups[].bytes` | `integer` | The compressed size of the backup, summed over its Secrets. **Range:** 1 or more. |

The number of backups kept comes from the manager's `--state-backups` flag,
which defaults to 5; the field itself holds at most 16. See [Terraform
State](../../concepts/state.md#state-backups) for how and when backups are
taken, and the [state restore
runbook](../../operator-guide/runbooks/state-restore.md) for restoring one.

```yaml
status:
  observedStateSerial: 42
  stateSecretSuffix: <16 hex digits>-c   # of sha256(namespace/kind/name)
  stateBackups:
    - serial: 42
      takenAt: "2026-10-02T09:20:51Z"
      bytes: 18342
    - serial: 41
      takenAt: "2026-10-01T16:02:13Z"
      bytes: 18310
```

### Image in use

`status.source` records what the last Job actually ran, as opposed to what
`spec.source` asks for. It is omitted until a Job has run.

| Field | Type | Description |
| --- | --- | --- |
| `status.source` | `object` | What the last Job ran. |
| `status.source.image` | `string` | The image reference that ran last, as written in the spec. **Range:** 1 to 512 characters. |
| `status.source.imageDigest` | `string` | The digest the container runtime resolved the image to (the pod's `imageID`). Informational: the pinned copy lives on the durable inputs Secret as `captf.io/image-digest`. **Range:** 1 to 512 characters. |
| `status.source.runtimeVersion` | `string` | The version reported by `<command> version -json`. **Range:** 1 to 64 characters. |

```yaml
status:
  source:
    image: ghcr.io/example/cluster-module:v1.4.0
    imageDigest: ghcr.io/example/cluster-module@sha256:3f1c0e9d5a7b2c64e8f1a0b9d7c3e5f2a4b6c8d0e1f3a5b7c9d1e3f5a7b9c1d3
    runtimeVersion: 1.9.8
```

!!! related "See also"

    - [TerraformCluster](terraformcluster.md), [TerraformMachine](terraformmachine.md) and [TerraformMachinePool](terraformmachinepool.md) for the kind-specific fields.
    - [Module Variables](../../user-guide/variables.md) for merge order, formats and what a change does.
    - [Tuning Jobs](../../user-guide/job-tuning.md) for choosing job settings.
    - [Identities and Credentials](../../user-guide/identities.md) for creating the identity `spec.identityRef` names.
    - [Terraform State](../../concepts/state.md) for the state backend, backups and restore.
    - [Drift and Health](../../concepts/drift-and-health.md) for the checks behind `status.lastDriftCheck` and `status.lastRefresh`.
    - [Job Environment](../environment.md) for the Job's fixed environment, resources and security contexts.
