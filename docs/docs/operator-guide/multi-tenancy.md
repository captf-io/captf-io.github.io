---
title: "Multi-Tenancy with CAPTF Identities"
description: "Lay out tenants on one management cluster: namespace isolation, identities, the runner's Secret access, quotas, network policy and an example."
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/users
subtitle: "Isolate teams on one manager"
---

# Multi-Tenancy

CAPTF can serve several tenants from one management cluster. The unit of
isolation is the **namespace**: one tenant, one identity and one workload
cluster per namespace. This page explains what that isolation is made of,
where it is thin, and how to lay out a tenant. It builds on [Identities and
Credentials](../user-guide/identities.md), [RBAC](rbac.md) and the [Security
Model](../concepts/security-model.md), and links to them instead of
repeating them.

## The model

A tenant is a namespace that holds that tenant's Cluster API and `Terraform*`
objects, their Secrets, and the Jobs CAPTF runs for them. What a tenant can
do is decided by three things:

| Layer | Controls | Where |
| --- | --- | --- |
| **Kubernetes RBAC** | Who may create or edit `Terraform*` objects, approve plans and read Secrets | Roles in the tenant namespace |
| **The identity** | Which cloud credentials a namespace may use | `TerraformClusterIdentity.spec.allowedNamespaces` |
| **The namespace itself** | What a Job can read, how much it can use, where it can connect | Pod Security labels, quotas, network policy |

!!! warning "A module runs with the namespace's Secret access and the identity's credentials"

    The point to hold on to is that **a module is code that runs with the
    namespace's Secret access and the identity's cloud credentials**. Whoever
    controls `spec.source.image` of an object, or can edit one, controls both.
    Everything below follows from that.

## Identities and `allowedNamespaces`

A `TerraformClusterIdentity` is cluster-scoped. It names a credentials Secret
(`spec.secretRef`, in any namespace) and says which namespaces may use it.

| `allowedNamespaces` | Meaning |
| --- | --- |
| unset | No namespace may use it |
| `list` | Exactly the named namespaces |
| `selector` | Namespaces whose labels match |
| `selector: {}` | **Every** namespace, including ones not yet created |
| `list` and `selector` | The union |
| `{}` | Rejected: it would read as "no one" or "everyone" |

Protections the admission webhook adds:

- **Creating** an identity, **changing** `spec.secretRef` and **widening**
  `allowedNamespaces` each run a `SubjectAccessReview`: the requester must be
  allowed to `get` the named Secret. A role that may manage identities but
  cannot read the Secret cannot point an identity at it, or grant more
  namespaces access to it. Narrowing is not re-checked.
- **Deleting** an identity is refused while any object resolves to it or any
  namespace still holds its mirror.

Practical rules:

- Give each tenant its **own identity**, with credentials scoped to that
  tenant's cloud account or role, and allow only that tenant's namespace.
  Never use `selector: {}` for an identity with real credentials.
- Keep the source Secret in a **platform namespace** tenants cannot read. The
  tenant's namespace holds only the mirror.
- Do not give tenants `create`, `update` or `patch` on
  `terraformclusteridentities`. The `SubjectAccessReview` limits what a
  requester can point an identity at, but identities are a platform object.

### The mirror per namespace

For each identity a namespace uses, the manager keeps one Secret,
`captf-creds-<identity>`, in that namespace: a copy of the source Secret. All
the namespace's objects that use the identity share it, and each is an
owner of it. The Job mounts it into the module's container as environment
variables and read-only files.

- **Revocation.** Drop a namespace from `allowedNamespaces` and the manager
  deletes the mirror there, whatever still references it, and starts no new
  Job for the namespace's objects. A destroy waits, with `IdentityNotAllowed`,
  until access returns, or the object is retained. See [Revoke
  access](../user-guide/identities.md#revoke-access).
- **The mirror is a Secret the tenant's workloads can read.** Anyone with
  `get` on Secrets in the namespace can read the credentials. Scope the
  credentials, not just the access.
- **Rotation is not instant.** A change to the source reaches the mirror on
  the manager's next reconcile. See [Rotate
  credentials](../user-guide/identities.md#rotate-credentials).

## The runner reads every Secret in its namespace

!!! danger "Any module image can read, replace or delete every Secret in its namespace"

    The Job runs as the `captf-runner` ServiceAccount, bound by a RoleBinding in
    each namespace to a ClusterRole with `get`, `list`, `create`, `update` and
    `delete` on Secrets, unscoped by name. The Kubernetes state backend needs
    that: it lists and writes its own chunks, and RBAC cannot name Secrets that do
    not exist yet. The ServiceAccount token is mounted in the Job pod, and the
    state backend uses it. As a result, **any module image can read, replace or
    delete every Secret in its namespace**: other objects' state and inputs, the
    credential mirrors, and Cluster API Secrets such as a cluster's kubeconfig and
    CA. See [What the runner can read, and
    why](../concepts/security-model.md#what-the-runner-can-read-and-why).

Consequences for a platform team:

- **Do not put two trust domains in one namespace.** Two tenants, or a trusted
  platform cluster and an untrusted module author, in one namespace give each
  the other's state and credentials.
- **An untrusted or experimental module gets its own namespace**, with its
  own identity whose credentials can do no more than that experiment needs.
- **The manager itself holds Secret access cluster-wide**: its ClusterRole
  grants get, list, watch, create, update, patch and delete on Secrets in
  every namespace, and it can bind the `captf-runner` ClusterRole in any
  namespace. `--namespace` narrows what it watches, not what it may do, and a
  namespaced install is not supported (see [The grant is
  cluster-wide](rbac.md#the-grant-is-cluster-wide)). Protect the manager's
  namespace and its image supply chain accordingly.

### Override ServiceAccounts

`spec.jobs.serviceAccountName` can name another ServiceAccount for a Job. It
must exist and carry the label `captf.io/runner=true`, or the object reports
`RunnerRBACReady=False`/`ServiceAccountNotOptedIn` and runs nothing. The label
is consent: whoever may label a ServiceAccount opts it in. The manager then
adds it to the namespace's `captf-runner` RoleBinding, and prunes subjects no
object uses. This is for a namespace administrator who needs a Job to run as
a ServiceAccount with extra cloud-side permissions (workload identity), not
a way to narrow the runner: the binding gives the Secret rights to every
subject. See [Custom ServiceAccounts](rbac.md#custom-serviceaccounts-and-the-runner-opt-in).

## Who writes specs and who approves

Approval is Kubernetes RBAC, by design. An approval is a patch of a
`TerraformPlan` (`spec.approved`), so it is authorized by who may `patch`
`terraformplans`, not by any right on the target. The manual-action
annotation (`captf.io/restore-state`) and `spec.deletionPolicy` are
authorized by who may `patch` the object, and the webhooks do not restrict
them. Whoever holds `patch` on a `TerraformCluster` can edit its spec, set
`spec.deletionPolicy` and set that annotation.

`create` on `terraformplans` equals approve, because the webhook accepts a plan
created approved (`clusterctl move` creates plans again). Grant it only to the
manager and the identity that runs `clusterctl move`.

The pattern for a tenant, from [Operating the
gates](../concepts/approvals/operating.md#who-can-approve):

- **Approvers** hold `get`, `list`, `watch` and `patch` on `terraformplans` in
  the tenant namespace, and no more.
- **Spec changes** come from a pipeline's ServiceAccount, through a reviewed
  change (GitOps). People hold read-only access otherwise.
- **Machines and pools are mostly not gated**, so the split protects the
  cluster module and a pool's exports changes. See
  [Limits](../concepts/approvals/limits.md).
- An optional `ValidatingAdmissionPolicy` can let a bot approve non-destructive
  plans while destructive ones need a human group; see [Tiered
  auto-approval](../concepts/approvals/operating.md#tiered-auto-approval).

Which fields a spec writer can change also differs by kind. A
`TerraformMachine`'s source, identity and variables are immutable; its
`jobs`, `drift` and `remediation` policy is not. A `TerraformCluster` and a
`TerraformMachinePool` are fully mutable by whoever has `update`.

## Quotas, limits and network policy

- **Pod Security.** The Job pod meets `baseline` by default. Label each tenant
  namespace with the level you enforce. For `restricted`, the module image
  must run as non-root. See [Pod
  security](../concepts/security-model.md#pod-security).
- **ResourceQuota.** A tenant's quota has to allow what CAPTF creates: Jobs
  and pods (finished Jobs are retained until pruned, 3 successful and 3
  failed per op by default), Secrets (the state and its chunks, up to five
  backups of each, the durable inputs, the plan key, the mirror, and a
  per-run Secret per running Job) and Leases (a run lease per object, a write
  lease per Cluster and a state lock per object). The default Job pod requests
  250m CPU and 512Mi, sets a 2Gi memory limit and **no CPU limit**. If the
  quota covers `limits.cpu`, add a `LimitRange` that defaults a CPU limit, or
  pods without one are refused (Kubernetes behavior). CAPTF has no
  quota-specific condition: a refusal appears as a reconcile error or a Job
  that never starts. See [Production Readiness](production-readiness.md#runner-jobs).
- **Network policy.** The manager's policy does not cover Job pods. Copy
  `job-egress-sample.yaml` into each tenant namespace and add the cloud and
  registry egress that tenant's modules need. Egress is the control that
  limits where the identity's credentials can be sent. See [Network
  exposure](../concepts/security-model.md#network-exposure).
- **Several managers.** One manager watches one namespace or all of them,
  never a chosen set, and the leader-election lease name is fixed. To give
  groups of tenants their own manager instance, use `--watch-filter` and
  label the objects, and read [Namespace scoping and
  `--watch-filter`](configuration.md#namespace-scoping-and---watch-filter)
  first: the webhook still admits every namespace, and an object no instance
  watches is never reconciled.

## An example tenant

The platform team creates, per tenant `acme`:

1. A **namespace** `tenant-acme`, labeled for Pod Security
    (`pod-security.kubernetes.io/enforce: baseline`).
2. A **credentials Secret** `acme-cloud` in the platform namespace
    `captf-credentials`, holding credentials scoped to Acme's cloud account.
3. An **identity**:

    ```yaml
    apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
    kind: TerraformClusterIdentity
    metadata:
      name: acme
    spec:
      secretRef:
        name: acme-cloud
        namespace: captf-credentials
      allowedNamespaces:
        list:
          - tenant-acme
    ```

4. A **ResourceQuota** and **LimitRange** sized as above, and a **NetworkPolicy**
    for Job pods from the sample.
5. **Roles** in `tenant-acme`. The pipeline's ServiceAccount authors clusters
    and machines; approvers are a smaller group with `patch` on
    `terraformclusters`. This is the pipeline's Role:

    ```yaml
    apiVersion: rbac.authorization.k8s.io/v1
    kind: Role
    metadata:
      name: captf-spec-pipeline
      namespace: tenant-acme
    rules:
    - apiGroups: ["infrastructure.cluster.x-k8s.io"]
      resources:
      - terraformclusters
      - terraformmachines
      - terraformmachinepools
      - terraformclustertemplates
      - terraformmachinetemplates
      - terraformmachinepooltemplates
      verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
    - apiGroups: ["cluster.x-k8s.io"]
      resources: ["clusters", "machinedeployments", "machinepools"]
      verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
    - apiGroups: ["batch"]
      resources: ["jobs"]
      verbs: ["get", "list", "watch"]
    - apiGroups: [""]
      resources: ["pods", "pods/log", "events"]
      verbs: ["get", "list", "watch"]
    ```

    Note what is **absent**: no `secrets` rule. The pipeline does not read
    the credential mirror or the state through the API, although the modules
    they run can (see above). The approvers' Role is the one in [Operating the
    gates](../concepts/approvals/operating.md#who-can-approve), bound to a
    smaller group.

Bind the Roles to groups with RoleBindings in the tenant namespace. Give the
tenant no `ClusterRole` that reaches `terraformclusteridentities`.

!!! related "See also"

    - [Identities and Credentials](../user-guide/identities.md).
    - [RBAC](rbac.md) and [Secrets](secrets.md).
    - [Security Model](../concepts/security-model.md) and [Security
      considerations](../concepts/secret-management/security.md).
    - [Approvals and Gates](../concepts/approvals/README.md).
    - [Production Readiness](production-readiness.md).
