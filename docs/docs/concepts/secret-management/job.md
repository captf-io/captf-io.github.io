---
title: "Secrets Inside the Terraform Job"
description: See what a Job pod mounts, which environment and permissions it gets, and which runner steps run for each operation.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/cog
subtitle: "Secrets inside the runner Pod"
---

# Inside the Job

A Job has one init container, which copies the runner binary into a shared
volume, and one main container, which runs the role image with the runner
as its entry point. The runner prepares a working directory, then runs
Terraform or OpenTofu steps against it. This page lists what the pod
mounts, what environment it gets, which permissions it holds, and which
steps run for each operation. Fields you can change are in [Tuning
Jobs](../../user-guide/job-tuning.md); the full environment is in the
[Job environment](../../reference/environment.md) reference.

## Volumes

| Volume | Mount | Access | Contents |
| --- | --- | --- | --- |
| `runner` | `/captf/bin` | Read-only in the main container; read-write in the init container | The runner binary |
| `work` | `/captf/work` | Read-write | The working directory, `HOME` and `TF_DATA_DIR` |
| `tmp` | `/tmp` | Read-write | Scratch space |
| `config` | `/captf/config` | Read-only | The per-run Secret; for a restore, a projection of it with the backup chunks |
| `creds` | `/var/run/captf/credentials` | Read-only | The credentials mirror, one file per key |
| `plan-key` | `/captf/plan-key` | Read-only | The plan key, on plan and approved-apply Jobs only |

The three Secret volumes use mode `0440`, and the pod's `fsGroup` defaults
to `65532`, so a non-root image user can read them through that group. Both
containers have a read-only root filesystem by default; a user
`securityContext` on the main container can change that, within the limits
[Tuning Jobs](../../user-guide/job-tuning.md#security-contexts) lists. The
init container mounts only `/captf/bin`.

## Environment

The Job sets `TF_IN_AUTOMATION=1`, `TF_INPUT=0`, `HOME=/captf/work`,
`TMPDIR=/tmp`, `KUBE_NAMESPACE` and `CHECKPOINT_DISABLE=1`, and the
credentials mirror adds its keys through `envFrom`. Entries you put in
`spec.jobs.env` that begin with `TF_` or `KUBE_` are dropped.

The runner then builds the environment each step sees from what the pod
has: it removes every remaining `TF_*` and `KUBE_*` variable, whatever its
source (the identity Secret, the image's `ENV`), forces `TF_DATA_DIR` to
`/captf/work/.terraform` and `HOME` to the working directory, and adds
`TF_CLI_CONFIG_FILE` when the image ships providers. So a module cannot be
steered by a `TF_WORKSPACE`, `TF_VAR_*` or `TF_CLI_ARGS` that arrived with
a credential. See [Credentials](credentials.md#delivery-to-the-runtime).

## Preparing the working directory

Before the first step, the runner:

- copies the top-level files of `/captf/config` into `/captf/work/root`
  with mode `0600`: the rendered module and the tfvars;
- when the image has `/captf/providers`, writes a CLI configuration at
  `/captf/work/cli.tfrc` with mode `0600` that installs providers only
  from that filesystem mirror (`direct` is excluded), so a Job never
  downloads a provider.

## ServiceAccount and RBAC

The Job runs as the ServiceAccount `captf-runner` in the object's
namespace, or as an override ServiceAccount you label
`captf.io/runner=true`. The manager creates the ServiceAccount and a
RoleBinding named `captf-runner` to the ClusterRole `captf-runner`, per
namespace, before the first Job. Its rules are shipped in
`config/rbac/runner_clusterrole.yaml`:

| Resource | Verbs | Why |
| --- | --- | --- |
| `secrets` | `get`, `list`, `create`, `update`, `delete` | The backend reads, writes, lists and deletes surplus state chunks |
| `leases` (`coordination.k8s.io`) | `get`, `create`, `update` | The state lock, unlock and force-unlock; the backend never deletes the Lease, so there is no `delete` |
| `events` (`events.k8s.io`) | `create` | Run progress events on the object |

!!! warning "The Secret verbs cover every Secret in the namespace"

    Kubernetes RBAC cannot restrict a Secret verb to labeled or named
    objects when the names are dynamic, so these verbs cover every Secret in
    the namespace. [Security considerations](security.md#the-runner-can-reach-every-secret-in-its-namespace)
    explains what that means.

When a namespace has no `Terraform*` objects
left, the manager deletes the managed ServiceAccounts, RoleBindings and
Leases there, both after the last finalizer is removed and periodically.

## Steps by operation

Every operation begins with `init`, which receives the backend settings
(see [Terraform state Secrets](state.md#the-backend)). If the controller
found a stale lock before starting the Job, a force-unlock step follows
`init`. Then:

| Operation | Steps after `init` |
| --- | --- |
| `apply` | `validate`, `apply -auto-approve` |
| Guarded or approved `TerraformCluster` apply | `validate`, `plan -detailed-exitcode -out`, `show -json`, then `apply` of the saved plan |
| `plan` (`applyPolicy: Manual`) | `validate`, `plan -out`, `show -json` |
| `destroy` | `destroy` |
| `refresh` | `apply -refresh-only` |
| `drift` | `apply -refresh-only`, `plan -refresh=false`, `show -json` |
| `restore` | `state push -force`, `state list` |

The steps that touch state (`init`, `plan`, `apply`, `destroy`, `refresh`
and `state push`) pass `-lock-timeout`, from `lockTimeoutSeconds` (default
300 seconds). The others, `validate`, `show`, force-unlock and `state list`,
do not.

## Locks

Terraform takes the state lock for the run, in the Lease
`lock-tfstate-default-<suffix>`. Before it starts a Job, the manager checks
that Lease. A lock is force-unlocked only when its holder is one of the
object's own runner pods and that pod is gone or has finished. Any other
holder leaves the lock alone and reports `StateReadable=False`/`StateLocked`,
and you must unlock it yourself; see the [stale lock
runbook](../../operator-guide/runbooks/stale-lock.md).

CAPTF has two more Leases of its own, in the object's namespace, apart from
the backend's: the run lease `captf-run-<suffix>` keeps two Jobs from
running for one object, and the cluster write lease
`captf-cluster-<16 hex of sha256("<ns>/cluster")>` makes machines and pools
wait while a `TerraformCluster` applies, destroys or restores (the
cluster lease is on by default; `--cluster-operation-gate=false` turns it
off, and the run lease is always on). They are
released when the Job finishes, by cleanup and by the namespace sweep. See
[run leases](../lifecycle.md#run-leases-and-the-cluster-operation-gate).

## Redaction

The runner replaces known secrets with `(sensitive)` in failure summaries,
events and its own logs. This is best effort; see [What CAPTF keeps out of
status, events and
logs](../security-model.md#what-captf-keeps-out-of-status-events-and-logs).

!!! related "See also"

    - [Runtime environment](../../module-author/runtime-environment.md), what
      a module sees.
    - [RBAC](../../operator-guide/rbac.md).
    - [Runner CLI](../../reference/runner-cli.md).
