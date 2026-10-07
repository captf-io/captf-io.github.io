---
title: "TerraformClusterIdentity API Reference"
description: "Reference for the cluster-scoped TerraformClusterIdentity kind: its credentials Secret, allowed namespaces, status, conditions, validation and lifecycle."
icon: lucide/key-round
subtitle: "Credentials and who may use them"
---

# TerraformClusterIdentity

A `TerraformClusterIdentity` names a Secret of cloud credentials and the
namespaces allowed to use it. It is cluster-scoped. A platform admin
creates it, along with the Secret. `TerraformCluster.spec.identityRef`,
`TerraformCluster.spec.defaults.identityRef` and the `spec.identityRef` of a
`TerraformMachine` or `TerraformMachinePool` reference it by name. The
manager copies the Secret into each allowed namespace that uses the
identity and mounts that copy into the Jobs it runs there.

| Property | Value |
| --- | --- |
| API version | `infrastructure.cluster.x-k8s.io/v1alpha1` |
| Scope | Cluster |
| Created by | A platform admin, with `kubectl apply` |
| Referenced by | `TerraformCluster` (`spec.identityRef`, `spec.defaults.identityRef`), `TerraformMachine` and `TerraformMachinePool` (`spec.identityRef`), with `kind` unset or `TerraformClusterIdentity` |
| Finalizers | None. The delete webhook protects an identity in use instead |
| Short names | None |
| Categories | `cluster-api` |
| Status subresource | Yes |

## Example

A minimal identity for one namespace, and the Secret it points at:

```yaml title="identity.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformClusterIdentity
metadata:
  name: aws
spec:
  secretRef:
    name: aws
    namespace: captf-system
  allowedNamespaces:
    list:
      - team-a
---
apiVersion: v1
kind: Secret
metadata:
  name: aws
  namespace: captf-system
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: REPLACE_WITH_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY: REPLACE_WITH_SECRET_ACCESS_KEY
```

## Full example

Every spec field set. `list` and `selector` are combined: a namespace is
allowed when either matches.

```yaml title="identity.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformClusterIdentity
metadata:
  name: aws
spec:
  secretRef:
    name: aws # (1)!
    namespace: captf-system # (2)!
  allowedNamespaces:
    list: # (3)!
      - team-a
      - team-b
    selector: # (4)!
      matchLabels:
        captf.io/identity-aws: "true"
```

1. The Secret's name. A DNS subdomain, up to 253 characters.
2. The Secret's namespace. Required, and any namespace works. It does not
   have to be an allowed namespace.
3. Up to 100 namespace names. At least one if `list` is set.
4. A Kubernetes label selector over namespace labels. Namespaces it
   matches are allowed in addition to those in `list`.

## Spec

`spec` must have at least one property, and `spec.secretRef` is required
while `spec.type` is `Secret` (the only type, and the default when unset).
Every field is mutable: the CRD and webhook mark none immutable.

| Field | Type | Description |
| --- | --- | --- |
| `spec` | object | The desired state: the credentials Secret and who may use it. **Required.** |
| `spec.type` | string | How the credentials are supplied. A union discriminator: each value selects the fields that must be set. **Allowed values:** `Secret`, the only one. **Default:** `Secret`. |
| `spec.secretRef` | object | The credentials Secret. **Required** when `spec.type` is `Secret`. |
| `spec.requiredKeys` | array of string | Keys the credentials Secret must hold. See [Required keys](#required-keys). **Range:** up to 64 items, each 1 to 253 characters from `[-._a-zA-Z0-9]`. Items are unique (a set). **Default:** unset, which checks nothing. |
| `spec.allowedNamespaces` | object | Which namespaces may reference the identity. **Default:** unset, which allows no namespace. **Mutable.** |

### Secret reference

| Field | Type | Description |
| --- | --- | --- |
| `spec.secretRef.name` | string | Name of the Secret. **Required.** **Mutable.** **Range:** 1 to 253 characters. **Allowed values:** a DNS subdomain (lowercase alphanumerics, `-` and `.`, starting and ending with an alphanumeric). |
| `spec.secretRef.namespace` | string | Namespace of the Secret. **Required.** **Mutable.** **Default:** none; unlike some Kubernetes references it is never defaulted to the manager's namespace. **Range:** 1 to 63 characters. **Allowed values:** a DNS label. |

The Secret may live in any namespace. The admission webhook requires that the
user who creates or changes the identity may `get` it, which keeps an
identity from exposing a Secret its author cannot read. See
[Validation](#validation).

### Required keys

`spec.requiredKeys` lists key names that the Secret's `data` must hold. When
one is missing, the identity's `Ready` is `False` with reason
`CredentialsIncomplete`, its message names the missing keys, and every object
that uses the identity gets `IdentityAllowed=False` with the same reason and
starts no Job. Only key names are compared, never values, so the check is the
same for every cloud: list `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
for an AWS identity, or `credentials` and `config` for a file-based one. An
empty value counts as present.

```yaml title="identity.yaml"
spec:
  secretRef:
    name: aws
    namespace: captf-system
  requiredKeys:
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY
```

To use a Secret without an identity object, see
[Identity reference](common-fields.md#identity-reference): `kind: Secret`
names a Secret in the object's own namespace, and `requiredKeys` does not
apply to it.

### Allowed namespaces

`spec.allowedNamespaces` decides which namespaces may use the identity. The
manager checks it each time an object resolves its credentials, so changing
it takes effect on the next reconcile of every object that uses the
identity.

| Field | Type | Description |
| --- | --- | --- |
| `spec.allowedNamespaces.list` | array of string | Names of allowed namespaces. **Range:** 1 to 100 items, each 1 to 63 characters. **Allowed values:** DNS labels. Items are unique (a set). |
| `spec.allowedNamespaces.selector` | LabelSelector | Allows every namespace whose labels match. An empty selector (`{}`) matches every namespace, including ones that do not exist yet. |

How the values combine:

| `allowedNamespaces` | Allowed namespaces |
| --- | --- |
| Unset | None |
| `list` only | Exactly the listed namespaces |
| `selector` only | Namespaces whose labels match |
| `list` and `selector` | The union: a namespace in `list`, or one the selector matches |
| `selector: {}` | Every namespace |
| `{}` (neither field) | Rejected at admission |

The empty object is rejected rather than read as "every namespace" or "no
namespace", because the most permissive value should not look like the least.
Write `selector: {}` for every namespace. A `list` of zero items also fails
validation (`MinItems=1`).

`spec.allowedNamespaces.selector` is a standard Kubernetes
[`LabelSelector`](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#label-selectors)
applied to the labels of the `Namespace` object, so `matchLabels` and
`matchExpressions` both work. CAPTF reads the namespace of the referencing
object at reconcile time. It does not list namespaces ahead of time. A
selector that is invalid, or a namespace that does not exist, denies access (except `selector: {}`, which allows every namespace, existing or not; an invalid selector is a denial, not a retry); the labels are read from the API server uncached, so a label change applies at once;
a failed read of the namespace leaves the check `Unknown`
(`IdentityCheckFailed`) and retries.

```yaml title="identity.yaml"
spec:
  allowedNamespaces:
    selector:
      matchExpressions:
        - key: environment
          operator: In
          values: ["staging", "production"]
```

!!! warning "Anyone who can label a namespace can opt it in"

    A selector trusts namespace labels. Anyone who may edit the labels on
    a namespace can bring it under the selector, so restrict who may label
    namespaces, or prefer `list`.

## The credentials Secret

The Secret is a plain `Opaque` Secret. Which keys it holds is defined by the
module that uses the identity: name the keys for the variables its providers
read, not for CAPTF. For the keys each cloud expects, see the
[AWS](../../cloud-modules/aws/README.md#identity-secret),
[Azure](../../cloud-modules/azure/README.md#identity-secret),
[GCP](../../cloud-modules/gcp/README.md#identity-secret),
[OCI](../../cloud-modules/oci/README.md#identity-secret) and
[OpenStack](../../cloud-modules/openstack/README.md#identity-secret) module
pages. For creating it, see
[Identities and Credentials](../../user-guide/identities.md#create-the-credentials-secret).

A Job never mounts the source Secret. The manager copies it into the
namespace of each object that uses the identity, as `captf-creds-<identity>`
(labeled `captf.io/mirrored: "true"`, annotated with `captf.io/source-hash`;
see [Annotations and labels](../annotations-labels.md)). The Job gets the
copy twice:

- As environment variables, one per key, through `envFrom`. A key starting
  with `TF_` or `KUBE_` is not passed to the environment, except the
  variables the Job sets itself.
- As read-only files, one per key, under `/var/run/captf/credentials/<key>`
  with file mode `0440`. Every key appears as a file, including `TF_` and
  `KUBE_` keys.

The identity never owns the source Secret. The mirror is owned by the
objects that use it, and the manager deletes it when none remain.

!!! danger "Every Job in an allowed namespace carries these credentials"

    Anything that runs in the Job, including the module's Terraform code and
    its providers, can read them. Grant an identity only the cloud
    permissions the modules need, and allow only the namespaces that should
    have them. See the [security model](../../concepts/security-model.md).

## Status

The manager sets `status`; you do not write it. `status` has at least one
property when present.

| Field | Type | Description |
| --- | --- | --- |
| `status` | object | The observed state: whether the credentials Secret exists, and where it is mirrored. |
| `status.namespaces` | array of string | Namespaces where a mirror of the credentials Secret currently exists and an object uses the identity. Sorted. **Range:** up to 1000 items, each 1 to 63 characters. |
| `status.conditions` | array of Condition | The identity's conditions. Only `Ready` is set. **Range:** up to 32 items. Keyed by `type`. |
| `status.conditions[].type` | string | The condition type: `Ready`. |
| `status.conditions[].status` | string | `True`, `False` or `Unknown`. |
| `status.conditions[].reason` | string | A machine-readable reason: `SecretFound`, `SecretNotFound` or `CredentialsIncomplete`. See [Conditions](../conditions.md). |
| `status.conditions[].message` | string | A human-readable detail. For `SecretNotFound` it names the Secret as `namespace/name`. For `CredentialsIncomplete` it also lists the missing keys. |
| `status.conditions[].lastTransitionTime` | time | When `status` last changed. |
| `status.conditions[].observedGeneration` | integer | The `metadata.generation` the condition was computed from. |

A namespace appears in `status.namespaces` only when it holds the mirror
Secret, correctly labeled and annotated, and at least one object there uses
the identity. A Secret with the mirror's name that someone else created does
not count.

??? example "Example status"

    ```yaml
    status:
      conditions:
        - type: Ready
          status: "True"
          reason: SecretFound
          observedGeneration: 2
          lastTransitionTime: "2026-10-01T14:03:11Z"
      namespaces:
        - team-a
        - team-b
    ```

## Conditions

An identity sets one condition, `Ready`.

| Status | Meaning |
| --- | --- |
| `True` | The credentials Secret named by `spec.secretRef` exists and holds every key in `spec.requiredKeys` (`SecretFound`). |
| `False` | The Secret does not exist (`SecretNotFound`), or lacks a required key (`CredentialsIncomplete`). Objects that use this identity start no Job until it is fixed. |
| `Unknown` | Not set by the identity controller. |

`Ready` says nothing about which namespaces are allowed or whether a mirror
exists; the objects that reference the identity report that through their
`IdentityAllowed` and `CredentialsMirrored` conditions. The controller does
not watch the source Secret, so it re-reads it every five minutes while `Ready`
is `True` and every 30 seconds while it is `False`, and notices a Secret
created or deleted out of band within that time. `status.namespaces` is
computed from the manager's cache. It also emits
`IdentitySecretNotFound` (also for `CredentialsIncomplete`) and
`IdentitySecretFound` events when `Ready` changes. Every reason and its meaning is in [Conditions](../conditions.md).

## Printer columns

`kubectl get terraformclusteridentities` shows:

| Column | Source |
| --- | --- |
| `Secret` | `.spec.secretRef.name` |
| `Namespace` | `.spec.secretRef.namespace` |
| `Ready` | The `status` of the `Ready` condition |
| `Age` | `.metadata.creationTimestamp` |

## Validation

The CRD schema and the validating admission webhook enforce these rules. The
webhook runs on create, update and delete, and a request fails if the webhook
is unreachable.

Schema rules:

- `spec` must have at least one property. `spec.type` must be `Secret`, and
  with it (or with `type` unset) `spec.secretRef` is required, so
  `spec.secretRef.name` and `spec.secretRef.namespace` are too, with the
  length and character limits in [Secret reference](#secret-reference).
- `spec.requiredKeys` has up to 64 unique items, each a valid Secret key.
- `spec.allowedNamespaces` must set `list`, `selector` or both. The empty
  object is rejected with a message telling you to write `selector: {}`.
- `spec.allowedNamespaces.list` has 1 to 100 unique items, each a DNS label.
- `status.conditions` has at most 32 items and `status.namespaces` at most
  1000.

Webhook rules, on create and update:

- `spec.secretRef.name` and `spec.secretRef.namespace` must be non-empty.
- Each `spec.allowedNamespaces.list` item must be a valid DNS label.
- `spec.allowedNamespaces.selector` must parse as a label selector.
- The requesting user must be allowed to `get` the Secret. The webhook
  sends a `SubjectAccessReview` for verb `get` on `secrets` in
  `spec.secretRef.namespace`, named `spec.secretRef.name`, as the requester
  (user, groups and extra attributes). If it is denied, the request fails
  with `user "<name>" may not get Secret <namespace>/<name>`. On create the
  check always runs. On update it runs only when `spec.secretRef` or
  `spec.allowedNamespaces` changed, in either direction, because the first
  chooses a Secret and the second chooses where it is copied. Changing
  only labels or annotations skips it.

Webhook rules, on delete:

- The delete is refused while any `TerraformCluster`, `TerraformMachine` or
  `TerraformMachinePool`, in any namespace, resolves to the identity through
  its own `identityRef` or a fallback. An object being deleted still counts.
  The message names one such object.
- The delete is refused while `status.namespaces` is not empty. The message
  lists the namespaces.

The `TerraformCluster`, `TerraformMachine` and `TerraformMachinePool` webhooks
do not look up the identity they reference. A cluster must set a non-empty
`spec.identityRef`, but the name need not exist when you create it. The
controllers check it at reconcile time and report `IdentityNotFound`,
`NamespaceNotAllowed` or `IdentityNotAllowed` through conditions, and start no
Job. See [`identityRef`](common-fields.md#identity-reference) and the pages
for [`TerraformCluster`](terraformcluster.md),
[`TerraformMachine`](terraformmachine.md) and
[`TerraformMachinePool`](terraformmachinepool.md).

## Lifecycle

- **Create.** Create the Secret, then the identity. The creator must be able
  to `get` the Secret. `Ready` becomes `True` once the Secret exists. See
  [Create the identity](../../user-guide/identities.md#create-the-identity).
- **Reference.** An object in an allowed namespace sets `identityRef`; the
  manager creates the mirror there. See
  [Reference it](../../user-guide/identities.md#reference-it).
- **Rotate.** Edit the Secret's data in place. The mirror in each allowed
  namespace is rewritten the next time an object that uses the identity
  reconciles, and within one `--sync-period` at the latest. A Job created
  after that gets the new values. A running Job keeps its old environment
  for its whole run, and its mounted files follow the mirror. To switch to
  another Secret, edit `spec.secretRef`, which reconciles every user at once
  and runs the `get` check again. See
  [Rotate credentials](../../user-guide/identities.md#rotate-credentials).
- **Revoke.** Remove a namespace from `spec.allowedNamespaces`. The manager
  starts no new Job there and deletes the mirror in that namespace. An
  object being deleted in a revoked namespace waits to destroy until the
  namespace is allowed again. See
  [Revoke access](../../user-guide/identities.md#revoke-access).
- **Delete.** Refused while the identity is in use or still mirrored, as
  described in [Validation](#validation). Deleting it never deletes the
  source Secret. See
  [Delete an identity](../../user-guide/identities.md#delete-an-identity).

!!! related "See also"

    - [Identities and Credentials](../../user-guide/identities.md): create,
      reference, rotate and revoke an identity.
    - [Credentials](../../concepts/secret-management/credentials.md): the
      mirror's lifecycle.
    - [Security model](../../concepts/security-model.md): the trust boundary
      around mounted credentials.
    - [Conditions](../conditions.md): every reason this kind and its users set.
    - [Annotations and labels](../annotations-labels.md): the mirror's labels
      and annotations.
    - [Common fields](common-fields.md#identity-reference): `identityRef` on
      the other kinds.
    - [`TerraformCluster`](terraformcluster.md)
