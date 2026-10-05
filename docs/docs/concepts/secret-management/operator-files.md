---
description: "List what an operator provides or keeps right: credentials, runner ClusterRole, manager environment, encryption and backups."
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/folder-key
subtitle: "Credentials, RBAC, keys, backups"
---

# Operator Files and Settings

CAPTF creates most of its Secrets itself. This page lists the few things an
operator provides or must keep right: the credentials Secret and identity,
the runner's ClusterRole, the manager's environment and one flag, the
encryption of Secrets at rest, and what to back up outside the cluster.

## Credentials Secret and identity

One Secret and one identity per set of cloud credentials. The Secret's keys
are exactly what the module's providers read from the environment (and, as
files, from `/var/run/captf/credentials`). The identity names it, and lists
the namespaces that may use it.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: aws-prod
  namespace: platform
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: <value>
  AWS_SECRET_ACCESS_KEY: <value>
---
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformClusterIdentity
metadata:
  name: aws-prod
spec:
  secretRef:
    name: aws-prod
    namespace: platform
  allowedNamespaces:
    list:
      - tenant-a
```

Allow only the namespaces that need the credentials: whatever runs in an
allowed namespace can read the mirror (see [Security
considerations](security.md)). [Identities and
Credentials](../../user-guide/identities.md) describes the other
`allowedNamespaces` forms, and the [identities
runbook](../../operator-guide/runbooks/identity-and-credentials.md) the
failure modes.

## The runner ClusterRole

The manager creates a RoleBinding named `captf-runner` in each namespace
that has an object, to the ClusterRole `captf-runner`. The release
manifests install the ClusterRole; this is what
`config/rbac/runner_clusterrole.yaml` defines, with the `captf-` prefix
that `config/default` adds:

```yaml title="runner_clusterrole.yaml"
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: captf-runner
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list", "create", "update", "delete"]
- apiGroups: ["coordination.k8s.io"]
  resources: ["leases"]
  verbs: ["get", "create", "update"]
- apiGroups: ["events.k8s.io"]
  resources: ["events"]
  verbs: ["create"]
```

!!! note "These are the minimum the state backend uses; do not trim them"

    Reading and writing state needs `get`, `list`, `create` and `update` on Secrets,
    `delete` is needed when Terraform deletes surplus chunks after a state
    shrinks, and the Lease verbs cover lock, unlock and force-unlock. The
    `events` rule is unused with the manager flag `--runner-events=false`.

[RBAC](../../operator-guide/rbac.md) covers the manager's own permissions.

## Manager environment

The manager Deployment must set `POD_NAMESPACE` and `SERVICE_ACCOUNT_NAME`
through the downward API. The shipped manifest does:

```yaml
env:
- name: POD_NAMESPACE
  valueFrom:
    fieldRef:
      fieldPath: metadata.namespace
- name: SERVICE_ACCOUNT_NAME
  valueFrom:
    fieldRef:
      fieldPath: spec.serviceAccountName
```

The webhook uses them to recognize the manager's own ServiceAccount, the
only identity allowed to set `TerraformMachine.spec.providerID`. Without
them the manager logs a warning and the webhook refuses its writes, so
machines never finish provisioning. See [Manager
environment](../../operator-guide/configuration.md#manager-environment).

## The `--state-backups` flag

`--state-backups` sets how many complete state backups the manager keeps
per object. The default is `5`; `0` takes no new backups but leaves the
existing ones restorable; a negative value is rejected at start. Raise it
if you want a longer history to restore from (each backup is a full copy of
the compressed state), and see [Backups and restore](backups.md#retention)
for how the count works. Set it as in [Changing a
flag](../../operator-guide/configuration.md#changing-a-flag).

## Encrypting Secrets at rest

CAPTF adds no encryption of its own to any Secret it keeps, and CAPTF
cannot read OpenTofu's client-side state encryption. Every Secret in this
chapter, including the state, the inputs with their bootstrap data and the
mirrored credentials, is stored by the API server the way any Secret is.
Turn on encryption at rest for Secrets in the management cluster's API
server. An `EncryptionConfiguration` that encrypts Secrets with a key held
in the file:

```yaml title="encryption-config.yaml"
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: <base64-encoded 32-byte key>
      - identity: {}
```

Pass it to the API server with `--encryption-provider-config`.

!!! tip "Prefer a KMS provider when you have one"

    A KMS provider keeps the key outside the cluster and is the better
    choice when you have one; the file above keeps the key on the control
    plane's disk, next to the data it protects.

After enabling it, rewrite the existing Secrets so
they are stored encrypted
(`kubectl get secrets -A -o json | kubectl replace -f -`). The Kubernetes
documentation on [encrypting confidential data at
rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)
is the reference for key rotation and providers.

## What to back up outside the cluster

The backups CAPTF keeps are in the same namespace and owned by the object
(see [Security considerations](security.md#backups-are-not-disaster-recovery)),
so they do not protect against losing the namespace, the object or the
cluster. Keep these outside it:

- **etcd snapshots** of the management cluster, or a Velero (or equivalent)
  backup of the tenant namespaces that includes Secrets. That captures the
  state, the backups and the durable inputs together.
- **The identity source Secrets**, which `clusterctl move` does not carry,
  and the `TerraformClusterIdentity` manifests (`clusterctl move` carries
  the identity object itself, but a backup must hold it too). Store the
  Secrets wherever you store other credentials; keep the manifests in
  version control.
- **The module images** your objects reference, by digest. The durable
  inputs Secret pins the digest of the last successful apply; a destroy
  needs that image to exist.

!!! warning "Treat any such backup as sensitive as the Secrets themselves"

    The backups hold the same state, inputs and credentials.

!!! related "See also"

    - [Installation](../../operator-guide/installation.md) and
      [Configuration](../../operator-guide/configuration.md).
    - [RBAC](../../operator-guide/rbac.md).
    - [Secrets](../../operator-guide/secrets.md).
