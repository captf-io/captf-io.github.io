---
description: "Every flag of the CAPTF manager, grouped by purpose, with type, default, what it does and when to change it, plus how to set flags on the Deployment."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "September 29, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-09-29"
authors:
  - "The CAPTF Authors"
icon: lucide/flag
subtitle: "Command-line flags and defaults"
---

# Manager Flags

The CAPTF manager is the `manager` binary in the `manager` container of the
`captf-controller-manager` Deployment. It takes every setting as a
command-line flag; it has no configuration file, and it reads only two
settings from the environment (see [Environment variables](#environment-variables)).
The flags follow the conventions of `kube-controller-manager` and the CAPI
core providers. A flag accepts `--name=value` or `--name value`, and
underscores in place of dashes (`--leader_elect` is `--leader-elect`).
Durations are Go duration strings such as `30m`, `90s` or `1h30m`.

For what each group of flags changes in practice, see
[Configuration](../operator-guide/configuration.md). This page is the
complete list.

## Set a flag

The shipped Deployment sets its arguments in `config/manager/manager.yaml`
in the provider repository. `clusterctl init` installs that manifest, and
there are no clusterctl variables for the manager's arguments, so you
change a flag by editing the `args` of the `manager` container on the live
Deployment, or in a kustomize overlay over the released manifest.

```yaml title="Deployment (abridged)" hl_lines="14 15"
apiVersion: apps/v1
kind: Deployment
metadata:
  name: captf-controller-manager
  namespace: captf-system
spec:
  template:
    spec:
      containers:
      - name: manager
        args:
        - --leader-elect
        - --diagnostics-address=:8443
        - --insecure-diagnostics=false
        - --webhook-port=9443
        - --terraformcluster-concurrency=20
        - --drift-default-interval=1h
```

The first four arguments are the shipped ones; the highlighted two are
additions. The manager logs every parsed flag once at start, one
`FLAG: --name="value"` line each, and refuses to start on a value it
cannot run with: a concurrency below 1, a `--sync-period` or
`--drift-default-interval` that is not positive, a negative
`--state-backups`, or no valid runner image.

!!! warning "A strategic-merge patch that adds one flag drops the others"

    `args` is a plain list, so a strategic-merge patch replaces the whole
    list. Add a flag with a JSON patch, or patch the full list. Either way,
    a hand-patched flag does not survive `clusterctl upgrade apply` unless
    you reapply it. [Changing a flag](../operator-guide/configuration.md#changing-a-flag)
    has the commands.

## The flags you are most likely to change

| Flag | Default | Change it to |
| --- | --- | --- |
| `--leader-elect` | `false` (set by the shipped manifest) | Keep it on whenever more than one replica can run. |
| `--runner-image` | the manager's own image | Pin or mirror the image that supplies the runner binary to every Job. |
| `--watch-filter` | empty | Share one management cluster between provider instances. |
| `--namespace` | empty (all namespaces) | Confine the manager to one namespace. |
| `--drift-default-interval` | `30m` | Move the fleet-wide drift cadence. |
| `--state-backups` | `5` | Keep fewer or more state backups, or none. |
| `--runner-events` | `true` | Turn off runner progress events on a busy cluster. |
| `--terraformcluster-concurrency` and its three siblings | `10` | Raise a kind's parallelism when its objects queue. |
| `--cluster-operation-gate` | `true` | Allow a cluster's operation and its machines' to overlap. |
| `--tls-min-version` | `VersionTLS12` | Raise the TLS floor to `VersionTLS13`. |
| `-v, --v` | `2` | Raise verbosity while diagnosing, then lower it again. |

## CAPTF

These flags set how the manager runs Jobs and what it keeps around them.

| Flag | Type | Default | What it does |
| --- | --- | --- | --- |
| `--cluster-operation-gate` | `bool` | `true` | Keeps a `TerraformCluster`'s apply, destroy or restore from running at the same time as its machines' operations, through a per-Cluster write Lease. The per-object run Lease that stops two Jobs for one object is always on. Turn the gate off only if you accept those overlapping. |
| `--drift-default-interval` | `duration` | `30m` | The drift check interval an object falls back to when neither it nor its cluster's defaults set one. Must be positive. A machine pool whose own or inherited interval is `0` also uses it, since pool drift cannot be disabled. |
| `--runner-events` | `bool` | `true` | Has each Job's runner post progress events (`RunStarted`, `Step*`, `PlanSummary`, `ResourcesChanged`, `RunFinished`) on the owning `Terraform*` object. Emission is best effort and never fails a run. Needs `create` on `events` in the runner ClusterRole. Turn it off to cut event volume. |
| `--runner-image` | `string` | `$CAPTF_MANAGER_IMAGE` | The image of the init container that copies the runner binary into every Job. It must contain `/runner`, which means a CAPTF manager or runner image, never a module image. Unset, it takes the manager's own image. The manager refuses to start when this is empty or not a valid image reference. |
| `--state-backups` | `int` | `5` | How many state backups to keep per object. Each new state serial is copied into `captf-state-backup-*` Secrets, and older copies are pruned. `0` takes no new backups; existing ones stay and can still be restored. Must not be negative. |

## Controllers and concurrency

These flags choose what the manager watches and how many objects it
reconciles at once.

| Flag | Type | Default | What it does |
| --- | --- | --- | --- |
| `--namespace` | `string` | empty | Restricts the manager to one namespace. Empty watches all, which is what `clusterctl init` installs. A manager watches one namespace or all of them, never a chosen set. `TerraformClusterIdentity` is cluster-scoped and is watched everywhere regardless. |
| `--sync-period` | `duration` | `10m` | The minimum interval at which the informers re-enqueue every cached object, on top of event-driven reconciles. Also the interval of the orphan sweep. It reads the local cache only and does not set the drift or health cadence. Must be positive. |
| `--terraformcluster-concurrency` | `int` | `10` | How many `TerraformCluster` objects reconcile at once. Must be at least 1. |
| `--terraformmachine-concurrency` | `int` | `10` | How many `TerraformMachine` objects reconcile at once. Must be at least 1. |
| `--terraformmachinepool-concurrency` | `int` | `10` | How many `TerraformMachinePool` objects reconcile at once. Must be at least 1. |
| `--terraformmachinetemplate-concurrency` | `int` | `10` | How many `TerraformMachineTemplate` objects reconcile at once. Must be at least 1. |
| `--watch-filter` | `string` | empty | Reconcile only objects labeled `cluster.x-k8s.io/watch-filter` with this value. Empty reconciles every object the manager can see. The label key is fixed. |

A reconcile is a handful of API reads and a status patch, and mostly waits
on a Job, so a higher concurrency rarely costs much CPU. Lower it to soften
bursts against a small API server. The admission webhooks serve every
namespace whatever `--namespace` and `--watch-filter` say, so an object the
manager does not watch is admitted and then never reconciled.
[Namespace scoping and `--watch-filter`](../operator-guide/configuration.md)
explains the trade-offs.

## Leader election

Leader election makes sure one manager reconciles at a time. The Lease is
named `controller-leader-election-captf` and is not parameterized.

| Flag | Type | Default | What it does |
| --- | --- | --- | --- |
| `--leader-elect` | `bool` | `false` | Turns leader election on. Enable it whenever more than one replica can run, including during a rolling update. The shipped manifest sets it. |
| `--leader-elect-lease-duration` | `duration` | `15s` | How long a non-leader candidate waits before it forces leadership. |
| `--leader-elect-renew-deadline` | `duration` | `10s` | How long the leader keeps retrying to renew before it gives up leadership. |
| `--leader-elect-retry-period` | `duration` | `2s` | How long a candidate waits between attempts. |

The defaults match `kube-controller-manager` and rarely need changing.
Lower them to replace a crashed leader faster, at the cost of more Lease
traffic.

## Webhooks

The webhook server hosts the validating webhooks. cert-manager issues its
serving certificate, and the Deployment mounts the Secret into the manager
pod.

| Flag | Type | Default | What it does |
| --- | --- | --- | --- |
| `--webhook-cert-dir` | `string` | `/tmp/k8s-webhook-server/serving-certs/` | The directory that holds the serving certificate and key. |
| `--webhook-cert-name` | `string` | `tls.crt` | The certificate's file name in that directory. |
| `--webhook-key-name` | `string` | `tls.key` | The key's file name in that directory. |
| `--webhook-port` | `int` | `9443` | The port the webhook server listens on. The shipped manifest sets `9443`; the webhook Service targets it, so change both together. |

The shipped manifests wire these together. You change them only for a
custom certificate layout.

## Diagnostics and TLS (CAPI)

These flags come from Cluster API's shared manager options and behave as
they do in the CAPI core providers. The diagnostics endpoint serves
Prometheus metrics over HTTPS, authenticated and authorized against the API
server. See [Observability](../operator-guide/observability.md) for what it
serves.

| Flag | Type | Default | What it does |
| --- | --- | --- | --- |
| `--diagnostics-address` | `string` | `:8443` | The address the diagnostics endpoint binds to. With authentication on, it also serves the pprof endpoints and an endpoint that changes the log level at run time. |
| `--insecure-diagnostics` | `bool` | `false` | Serves diagnostics over plain HTTP with no authentication or authorization, and without the pprof and log-level endpoints. For local development only. |
| `--tls-cipher-suites` | `stringSlice` | empty | A comma-separated list of cipher suites for the webhook server and the metrics server (the latter only when diagnostics are secure). Empty uses Go's defaults. The flag's help text lists the preferred and the insecure names. |
| `--tls-curve-preferences` | `int32Slice` | empty | A comma-separated list of numeric Go `crypto/tls` `CurveID` values to allow as key exchange mechanisms. The order is ignored. Empty uses Go's defaults. The supported values depend on the Go version. |
| `--tls-min-version` | `string` | `VersionTLS12` | The minimum TLS version of the webhook and metrics servers: `VersionTLS10`, `VersionTLS11`, `VersionTLS12` or `VersionTLS13`. |

!!! danger "`--insecure-diagnostics` removes authentication from the metrics endpoint"

    Anything that can reach the address then reads the metrics with no
    token. Use it on a workstation, never on a cluster others can reach.

## Logging

The logging flags are the Kubernetes component-base set. The manager runs
at verbosity 2, where the usual reconcile flow is visible. Credentials,
bootstrap data, tfvars content and output values are never logged,
whatever the level.

| Flag | Type | Default | What it does |
| --- | --- | --- | --- |
| `--feature-gates` | `mapStringBool` | empty | A comma-separated `Key=value` list. Only the logging gates in [Feature gates](#feature-gates) exist. |
| `--log-flush-frequency` | `duration` | `5s` | The longest interval between log flushes. |
| `--log-json-info-buffer-size` | `quantity` | `0` | Alpha. Buffers info messages in the JSON format with split streams, to increase performance. `0` disables buffering. Takes `512`, `1K`, `2Ki` and the like. Needs `LoggingAlphaOptions`. |
| `--log-json-split-stream` | `bool` | `false` | Alpha. In the JSON format, writes errors to stderr and info messages to stdout, instead of one stream to stdout. Needs `LoggingAlphaOptions`. |
| `--log-text-info-buffer-size` | `quantity` | `0` | Alpha. The same buffering for the text format with split streams. Needs `LoggingAlphaOptions`. |
| `--log-text-split-stream` | `bool` | `false` | Alpha. In the text format, writes errors to stderr and info messages to stdout. Needs `LoggingAlphaOptions`. |
| `--logging-format` | `string` | `text` | The log format: `text` or `json`. `json` is gated by `LoggingBetaOptions`, which is on by default. |
| `-v, --v` | `Level` | `2` | The log verbosity. Raise it while you diagnose a problem and lower it afterward, since higher levels log more of each reconcile. |
| `--vmodule` | `pattern=N,...` | empty | Per-file verbosity overrides, such as `reconcile*=4`. Works only with the text format. |

To change the level of a running manager without a restart, use the
authenticated diagnostics endpoint; see
[Logs and verbosity](../operator-guide/observability.md#logs-and-verbosity).

## Other flags

| Flag | Type | Default | What it does |
| --- | --- | --- | --- |
| `--health-addr` | `string` | `:9440` | The address of the health endpoint that serves `/healthz` and `/readyz`. The Deployment's probes target port `9440`, so change both together. |
| `--kubeconfig` | `string` | empty | The path to a kubeconfig. You need it only out of cluster. Without it, the manager uses `$KUBECONFIG`, then its in-cluster configuration. |
| `--profiler-address` | `string` | empty | A bind address for a separate pprof profiler, such as `localhost:6060`. Empty leaves it off. Unrelated to the pprof endpoints on the diagnostics address. |
| `-h, --help` | `bool` | `false` | Prints the flag help, grouped by section, and exits. |
| `--version` | `version` | `false` | Prints version information and exits. `--version=raw` prints the raw build stamp. `--version=vX.Y.Z` sets the reported version instead. |

`manager version` prints the same line as `manager --version` and exits.

## Feature gates

`--feature-gates` takes a comma-separated `Key=value` list, for example
`--feature-gates=LoggingAlphaOptions=true`. CAPTF registers no feature gate
of its own. The gates that exist are the component-base logging gates.

| Name | Default | Maturity |
| --- | --- | --- |
| `AllAlpha` | `false` | Alpha |
| `AllBeta` | `false` | Beta |
| `ContextualLogging` | `true` | Beta |
| `LoggingAlphaOptions` | `false` | Alpha |
| `LoggingBetaOptions` | `true` | Beta |

## Environment variables

The manager reads these from its own environment. A custom Deployment or
an overlay that replaces the container's `env` must keep them.

| Variable | What it does |
| --- | --- |
| `CAPTF_MANAGER_IMAGE` | The default of `--runner-image`. The shipped Deployment sets it to the manager's own image, and `clusterctl init` replaces it with the release image. |
| `KUBECONFIG` | Read by the `--kubeconfig` handling when the flag is not given. Only an out-of-cluster manager needs it. |

The manager also reads `POD_NAMESPACE` and `SERVICE_ACCOUNT_NAME`, which the
shipped Deployment sets through the downward API. Without them the webhook
cannot tell which ServiceAccount is the manager and refuses its
`providerID` writes. See
[Manager environment](../operator-guide/configuration.md#manager-environment).

## Shipped arguments

`config/manager/manager.yaml` sets these arguments on the `manager`
container. Every other flag keeps its default.

| Flag | Value |
| --- | --- |
| `--leader-elect` | set |
| `--diagnostics-address` | `:8443` |
| `--insecure-diagnostics` | `false` |
| `--webhook-port` | `9443` |

!!! related "See also"

    - [Configuration](../operator-guide/configuration.md) — when and why to
      change each group of flags.
    - [Observability](../operator-guide/observability.md) — the diagnostics
      endpoint, metrics and verbosity.
    - [Installation](../operator-guide/installation.md) — what
      `clusterctl init` installs.
    - [Job Environment](environment.md) — what the runner Job a manager
      creates looks like.
