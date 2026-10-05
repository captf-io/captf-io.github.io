---
description: "Anatomy of the runner Job: containers, environment, credentials, volumes, resources, security contexts, runner arguments and the names spec.jobs.env rejects."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/variable
subtitle: "Variables set in the Job"
---

# Job Environment

Every Terraform or OpenTofu operation runs as one Kubernetes Job. The
manager builds it, the runner binary inside it drives the runtime, and your
module image supplies the module. This page is an anatomy of that Job: the
containers, the environment each one gets, the volumes, the fixed fields,
the default resources and security contexts, the runner's command line, and
what the runner does to the environment before it runs your module.

Use it to answer what a module sees at run time. For the fields you can
change, see [Tuning Jobs](../user-guide/job-tuning.md) and
[`spec.jobs`](resources/common-fields.md#jobs). For the order of the steps
the runner runs, see [Runtime
Environment](../module-author/runtime-environment.md). For the Job's place
in the lifecycle, see [Jobs, Retries and Concurrency](../concepts/jobs/README.md).

## Anatomy of a Job

A Job has one init container and one main container, sharing five
volumes (six for a plan or an apply):

- The **init container**, named `runner`, runs the manager's runner image
  (`--runner-image`). It copies one static binary, the runner, into a
  shared volume and exits.
- The **main container**, named `source`, runs your module image
  (`spec.source.image`) with the copied runner as its command. The runner
  checks the image layout, builds the working directory and runs the
  runtime as a child process.

The image's own `ENTRYPOINT` and `CMD` never run. The example below is an
apply Job for a `TerraformCluster`, abridged to the fields this page
describes.

```yaml title="Job pod spec (abridged)"
spec:
  backoffLimit: 0                          # the controller owns retries
  activeDeadlineSeconds: 3600              # spec.jobs.activeDeadlineSeconds
  template:
    spec:
      restartPolicy: Never
      terminationGracePeriodSeconds: 600   # SIGTERM, then SIGKILL after 10 min
      serviceAccountName: captf-runner     # spec.jobs.serviceAccountName
      securityContext:
        seccompProfile: {type: RuntimeDefault}
        fsGroup: 65532                     # lets a non-root image user read 0440 files
      initContainers:
      - name: runner                       # the manager's runner image
        image: ghcr.io/captf-io/cluster-api-provider-terraform:vX.Y.Z
        command: ["/runner", "copy", "/captf/bin/runner"]
        volumeMounts:
        - {name: runner, mountPath: /captf/bin}
        # fixed resources and a locked-down security context: see below
      containers:
      - name: source                       # your module image
        image: registry.example.com/modules/cluster:v1
        command: ["/captf/bin/runner", "run"]
        args:
        - --op=apply
        - --bin=/captf/runtime
        - --lock-timeout=300s
        - --stop-timeout=570s
        # ... the rest of the runner flags: see "Runner command and args"
        env:
        - {name: TF_IN_AUTOMATION, value: "1"}
        - {name: TF_INPUT, value: "0"}
        - {name: HOME, value: /captf/work}
        - {name: TMPDIR, value: /tmp}
        - {name: KUBE_NAMESPACE, value: default}
        - {name: CHECKPOINT_DISABLE, value: "1"}
        # ... then the entries of spec.jobs.env that are not TF_* or KUBE_*
        envFrom:
        - secretRef: {name: captf-creds-<identity>}   # the credentials mirror
        volumeMounts:
        - {name: runner, mountPath: /captf/bin, readOnly: true}
        - {name: work, mountPath: /captf/work}
        - {name: tmp, mountPath: /tmp}
        - {name: config, mountPath: /captf/config, readOnly: true}
        - {name: creds, mountPath: /var/run/captf/credentials, readOnly: true}
        - {name: plan-key, mountPath: /captf/plan-key, readOnly: true}
        securityContext:
          allowPrivilegeEscalation: false
          capabilities: {drop: [ALL]}
          readOnlyRootFilesystem: true
        resources:
          requests: {cpu: 250m, memory: 512Mi}
          limits: {memory: 2Gi}
        terminationMessagePolicy: ReadFile  # the runner writes its result here
```

The Job also carries labels that name the owner and the operation, and, for
an apply, a plan and a restore, an annotation with the inputs hash it
renders. See [Job names, attempts and history](../concepts/jobs/naming.md)
for the naming scheme.

## Fixed Job fields

| Field | Value | Meaning |
| --- | --- | --- |
| `backoffLimit` | `0` | The controller owns retries and the attempt number is in the Job name, so the pod never retries itself. |
| `restartPolicy` | `Never` | A failed container is not restarted. |
| `ttlSecondsAfterFinished` | unset | No Job expires on its own. The controller reads backoff and conditions from retained Jobs and prunes them by the history limits. |
| `terminationGracePeriodSeconds` | `600` | SIGTERM lets the runner finish in-flight provider calls and write its result before SIGKILL. A shorter period would kill a run mid-call and leave resources created but never recorded. |
| `activeDeadlineSeconds` | `3600` | The default. Set `spec.jobs.activeDeadlineSeconds` to change it. |
| `lockTimeoutSeconds` | `300` | The default, passed to the runner as `--lock-timeout`. Set `spec.jobs.lockTimeoutSeconds` to change it. |

The runner's stop timeout is the grace period less a 30-second margin
(`--stop-timeout=570s`), which leaves time to write the result. See
[Deadlines](../concepts/jobs/deadlines.md) for how the deadline and the lock
timeout interact.

## Main container environment

The Job sets these variables on the main container. A module sees them
unchanged, except `HOME`, which the runner sets again to the same value.

| Name | Value | What it does |
| --- | --- | --- |
| `TF_IN_AUTOMATION` | `1` | Tells the runtime it runs unattended, so it leaves out interactive follow-up hints. |
| `TF_INPUT` | `0` | Disables interactive prompts. The runner also passes `-input=false`. |
| `HOME` | `/captf/work` | The runner's working directory. The image's own `HOME` may not be writable. |
| `TMPDIR` | `/tmp` | The Job's `/tmp` volume, since the image's root filesystem is read-only. |
| `KUBE_NAMESPACE` | the object's namespace | The namespace of the `kubernetes` state backend, so state Secrets land beside the owning object. |
| `CHECKPOINT_DISABLE` | `1` | Stops Terraform from calling `checkpoint-api.hashicorp.com` on every command. A pod that holds cloud credentials otherwise makes that call, and it can stall on its timeout when a namespace drops egress silently. |

The Job builds `env` from these six, then appends the entries of
`spec.jobs.env` that do not begin with `TF_` or `KUBE_`; see
[`spec.jobs.env` rejected names](#specjobsenv-rejected-names). The Job does
not set `TF_DATA_DIR` or `TF_CLI_CONFIG_FILE`. The runner sets both for the
runtime; see [What the runner changes](#what-the-runner-changes).

An explicit `env` entry wins over `envFrom`. A credential key that is
named like one of these six therefore never replaces the Job's value.

## Identity credentials

The identity's credentials arrive in the main container two ways at once,
both from the credentials mirror. The mirror is a Secret named
`captf-creds-<identity>` in the object's namespace, which the manager copies
from the Secret that `TerraformClusterIdentity.spec.secretRef` names.

- **`envFrom`.** Every key of the mirror becomes an environment variable
  with that name. A module's providers read `AWS_ACCESS_KEY_ID` and the like
  from the environment as they do anywhere else. Kubernetes skips a key that
  is not a valid variable name.
- **Files.** The `creds` volume mounts the mirror at
  `/var/run/captf/credentials`, read-only, one file per key, mode `0440`. A
  module reads a key file or certificate from there, for example by naming
  the path in a provider setting.

!!! warning "Every key in the identity Secret reaches the runtime"

    The mirror is a byte copy of the whole Secret, so every key becomes a
    variable and a file, whether or not the module uses it. A key that
    begins with `TF_` or `KUBE_` is removed from the runtime's environment
    (see [What the runner changes](#what-the-runner-changes)) but stays
    available as a file.

The mirror, its rotation and its revocation are covered in
[Credentials](../concepts/secret-management/credentials.md#delivery-to-the-runtime),
and the identity itself in [Identities and
Credentials](../user-guide/identities.md).

## Volumes and mounts

The init container mounts only `runner`, read-write. The main container
mounts the volumes below. The three Secret volumes use mode `0440`.

| Mount path | Volume | Access | Contents |
| --- | --- | --- | --- |
| `/captf/bin` | `runner` | read-only | The runner binary, copied in by the init container. |
| `/captf/work` | `work` | read-write | Scratch space: the generated root at `/captf/work/root`, the CLI configuration, plan files and `TF_DATA_DIR`. |
| `/tmp` | `tmp` | read-write | General temporary storage (`TMPDIR`). |
| `/captf/config` | `config` | read-only | The per-run Secret: the rendered `main.tf.json` and `terraform.tfvars.json`. For a restore Job, a projection of it plus the backup's state chunks under `restore/<index>`. |
| `/var/run/captf/credentials` | `creds` | read-only | The identity's credential files. |
| `/captf/plan-key` | `plan-key` | read-only | The plan fingerprint key, as the single file `key`. Plan and apply Jobs only; other operations never see it. |

`runner`, `work` and `tmp` are empty directories that live as long as the
pod. The pod's `fsGroup` defaults to `65532`, so a non-root image user reads
the `0440` files through the group. `/captf/module`, `/captf/runtime` and
the optional `/captf/providers` are not volumes: they are paths in your
image. See [Image Contract](../module-author/image-contract.md#fixed-paths)
for the layout and [Run Inputs and the Plan
Key](../concepts/secret-management/run-inputs.md#the-plan-key) for the
key.

## Default resources

The init container only copies one static binary and never varies with the
module, so its resources are fixed and not configurable.

| Container | Kind | Values |
| --- | --- | --- |
| init (`runner`) | requests | `cpu=10m`, `memory=32Mi` |
| init (`runner`) | limits | `cpu=100m`, `memory=64Mi` |
| main (`source`), when `spec.jobs.resources` is unset | requests | `cpu=250m`, `memory=512Mi` |
| main (`source`), when `spec.jobs.resources` is unset | limits | `memory=2Gi`, and no CPU limit |

The main container has no default CPU limit because throttling a slow apply
is worse than a slow apply. A pod with no requests at all runs at the
BestEffort class, which Kubernetes evicts or OOM-kills first on a crowded
node, and that is the wrong place for a Terraform process with several large
providers. Setting `spec.jobs.resources` replaces the default as a whole;
see [Resources](../user-guide/job-tuning.md#resources).

## Security contexts

| Scope | Field | Value |
| --- | --- | --- |
| pod | `seccompProfile` | `RuntimeDefault` |
| pod | `fsGroup` | `65532`, so a non-root image user reads the `0440` credential files through the group |
| init (`runner`) | `allowPrivilegeEscalation` | `false` |
| init (`runner`) | `capabilities.drop` | `ALL` |
| init (`runner`) | `runAsNonRoot`, `runAsUser` | `true`, `65532` |
| init (`runner`) | `readOnlyRootFilesystem` | `true` |
| main (`source`) | `allowPrivilegeEscalation` | `false` |
| main (`source`) | `capabilities.drop` | `ALL`, always, whatever `spec.jobs.securityContext` holds |
| main (`source`) | `readOnlyRootFilesystem` | `true` |
| main (`source`) | `runAsNonRoot`, `runAsUser` | not set |

`spec.jobs.podSecurityContext` and `spec.jobs.securityContext` overlay these
defaults field by field, within the limits the webhook enforces; see
[Security contexts](../user-guide/job-tuning.md#security-contexts).

!!! note "The main container is not forced to run as non-root"

    A module image built from the `hashicorp/terraform` image runs as root,
    so the Job leaves `runAsNonRoot` and `runAsUser` unset. The webhook
    rejects an explicit root setting, but an image that runs as root by
    default still does. The container holds cloud credentials, so build the
    image to run as a non-root user: the
    [CAPTF base images](../module-author/image-contract.md#captf-base-images)
    already run as `captf` (65532). See [Pod
    security](../concepts/security-model.md#pod-security).

## Runner command and args

The main container's command is `/captf/bin/runner run`. The Job passes
these arguments, in this order. Every path is fixed by the [image
contract](../module-author/image-contract.md#fixed-paths). The runner CLI's
other flags keep their defaults; see [Runner CLI](runner-cli.md).

| Flag | Value | What it does |
| --- | --- | --- |
| `--op` | `apply`, `destroy`, `refresh`, `drift`, `restore` or `plan` | The operation this Job runs. |
| `--bin` | `/captf/runtime` | The image's `tofu` or `terraform` binary. |
| `--image` | the source image reference | Identifies the image that ran, in events and logs. |
| `--module` | `/captf/module` | The image's role module. |
| `--providers` | `/captf/providers` | The image's optional provider mirror. The runner checks whether it exists. |
| `--workdir` | `/captf/work` | The parent of the generated root. |
| `--config` | `/captf/config` | The per-run Secret's mount. |
| `--lock-timeout` | `300s`, or `spec.jobs.lockTimeoutSeconds` | How long the backend waits for the state lock before it fails. |
| `--stop-timeout` | `570s` | How long the runner has after SIGTERM to finish in-flight work and write its result. |
| `--backend-config=secret_suffix` | a per-attempt suffix | The suffix of the `kubernetes` backend's Secret name. |
| `--backend-config=namespace` | the object's namespace | The backend's namespace. |
| `--backend-config=in_cluster_config` | `true` | Tells the backend to use the pod's in-cluster credentials. |
| `--backend-config=labels` | the state Secret labels, as an HCL object | The labels the backend puts on the state Secrets it manages. |
| `--force-unlock` | a stale lock ID | Set only when the controller found a stale backend lock. The runner force-unlocks it after `init`. |
| `--guard-deletes` | no value | Set for every `TerraformCluster` apply, and for a `TerraformMachinePool` apply that renders a change of the cluster's exports. The runner stops before a plan that deletes or replaces a resource unless that is approved. |
| `--inputs-hash` | the approval hash of the rendered inputs | Set with `--guard-deletes`. It is the hash an approval must name: a cluster's inputs hash, or a pool's inputs hash without `bootstrap_data`. |
| `--allow-deletes-hash` | an approved hash | Set with `--guard-deletes` when the object carries `captf.io/approve-destructive-plan`. It allows a destructive plan for that exact input set. |
| `--expect-plan` | an approved plan hash | Set with `--guard-deletes` under `applyPolicy: Manual`, from the cluster's `captf.io/approve-plan`. The apply plans again and applies only if the plan matches. |
| `--restore-chunks` | the chunk count | Restore Jobs only: how many backup state chunks the config volume projects. |
| `--restore-resources` | the managed resource count | Restore Jobs only: the backup's recorded count. The restore fails if `state list` shows none when this is not `0`. |
| `--plan-key-file` | `/captf/plan-key/key` | Plan and apply Jobs only: the file that holds the key of the plan fingerprint. |
| `--event-object` | `<apiVersion>/<kind>/<namespace>/<name>/<uid>` of the owner | Set only when the manager runs with `--runner-events`. It lets the runner report progress as events about the owning object. |
| `--job-name` | the Job's name | Set with `--event-object`: the Job the events relate to. |

## What the runner changes

The runner starts from the container's environment: the Job's variables, the
identity `envFrom`, the image's own `ENV` and `spec.jobs.env`. Before it
runs the first command, it builds a new environment for the runtime and
leaves everything else out. Given a pod environment that carries every kind
of credential-bearing or backend-changing variable:

```text
TF_IN_AUTOMATION=1
TF_INPUT=0
KUBE_NAMESPACE=default
CHECKPOINT_DISABLE=1
TF_LOG=DEBUG
TF_VAR_region=us-east-1
TF_WORKSPACE=default
TF_CLI_ARGS_apply=-parallelism=1
KUBE_CONFIG_PATH=/tmp/kubeconfig
HOME=/root
TMPDIR=/tmp
AWS_ACCESS_KEY_ID=AKIA...
```

the runtime sees:

```text
AWS_ACCESS_KEY_ID=AKIA...
CHECKPOINT_DISABLE=1
HOME=/captf/work
KUBE_NAMESPACE=default
TF_DATA_DIR=/captf/work/.terraform
TF_INPUT=0
TF_IN_AUTOMATION=1
TMPDIR=/tmp
```

and the runner logs the dropped names, never their values, as
`Ignoring environment variables the runner owns`: `KUBE_CONFIG_PATH`,
`TF_CLI_ARGS_apply`, `TF_LOG`, `TF_VAR_region` and `TF_WORKSPACE`.

The rules are:

- `TF_DATA_DIR` is always `/captf/work/.terraform`, whatever the pod
  inherited.
- `HOME` is always `/captf/work`.
- `TMPDIR` is kept when the pod sets it, and the Job sets it to `/tmp`.
  Otherwise it is `/captf/work/tmp`, which the runner creates.
- `TF_CLI_CONFIG_FILE` is set only when the image ships a provider mirror;
  see [Provider mirror and CLI configuration](#provider-mirror-and-cli-configuration).
- Every other `TF_*` and `KUBE_*` variable is dropped. Only `TF_IN_AUTOMATION`,
  `TF_INPUT` and `KUBE_NAMESPACE` stay, because the Job sets them and an
  explicit `env` entry beats `envFrom`, so they never carry a credential's or
  an image's value.

Each drop closes a way to change a run from outside the module.
`TF_WORKSPACE` moves state, `TF_CLI_ARGS*` rewrites every command,
`TF_VAR_*` overrides the rendered inputs, `TF_LOG` logs provider traffic
with its credentials, and `KUBE_*` redirects the `kubernetes` backend.

## Provider mirror and CLI configuration

The Job cannot know whether the image ships providers, so the runner
decides. When `/captf/providers` exists, it writes `/captf/work/cli.tfrc`
with mode `0600`:

```hcl title="/captf/work/cli.tfrc"
provider_installation {
  filesystem_mirror {
    path    = "/captf/providers"
    include = ["*/*/*"]
  }
  direct {
    exclude = ["*/*/*"]
  }
}
```

and sets `TF_CLI_CONFIG_FILE=/captf/work/cli.tfrc`. `init` then installs
every provider from the image and contacts no registry, and it fails with a
clear error for a provider the mirror lacks instead of downloading it. The
three-segment `*/*/*` pattern matches every provider on every registry host.
The two-segment form matches only the default one.

Without `/captf/providers`, the runner writes no file and sets no
variable, and `init` falls back to the runtime's default direct
installation, which needs registry egress. The runner never sets
`TF_PLUGIN_CACHE_DIR`, since a plugin cache must not coincide with a
filesystem mirror. The mirror layout is in [Image
Contract](../module-author/image-contract.md#provider-mirror-layout).

## `spec.jobs.env` rejected names

`spec.jobs.env` adds variables to the main container, up to 64 entries.
The Job reserves every name that begins with `TF_` or `KUBE_`: the runner
and the Job own those two prefixes. That covers the three the Job sets
itself (`TF_IN_AUTOMATION`, `TF_INPUT` and `KUBE_NAMESPACE`) and every
setting a person might reach for, such as `TF_LOG`, `TF_VAR_*`,
`TF_WORKSPACE`, `TF_CLI_ARGS*`, `TF_CLI_CONFIG_FILE` and `KUBE_CONFIG_PATH`.

!!! warning "A reserved name is dropped without an error or an event"

    The API accepts an entry with a `TF_` or `KUBE_` name and the Job
    builder leaves it out. Nothing reports it, and the entry stays in the
    object's spec. If a variable has no effect, check its prefix first.

Other names are applied, including `HOME`, `TMPDIR` and
`CHECKPOINT_DISABLE`, which the Job also sets. The runner forces `HOME`
again, so setting it has no effect on the runtime. There is no way to turn
on provider debug logging from `spec.jobs.env`. To debug a provider, run
the image's `/captf/runtime` by hand with `TF_LOG` set; [Runtime
Environment](../module-author/runtime-environment.md#environment-set-and-dropped)
describes the recipe.

!!! related "See also"

    - [Tuning Jobs](../user-guide/job-tuning.md) — the `spec.jobs` fields
      that change this Job.
    - [Inside the Job](../concepts/secret-management/job.md) — the Secrets
      the pod mounts and the permissions it holds.
    - [Runtime Environment](../module-author/runtime-environment.md) — the
      commands the runner runs and how a failure is reported.
    - [Runner CLI](runner-cli.md) — every runner flag and default.
    - [Image Contract](../module-author/image-contract.md) — the paths your
      image must provide.
