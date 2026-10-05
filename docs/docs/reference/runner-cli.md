---
description: "Look up the runner binary's subcommands, flags, exit codes and result error kinds. The runner is the entrypoint of every CAPTF Job."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/square-terminal
subtitle: "Runner commands and exit codes"
---

# Runner CLI

`runner` is the program inside every CAPTF Job. The manager does not run
Terraform or OpenTofu itself: it creates a Job, and the runner in that Job
prepares the working directory, runs the module's runtime step by step,
and writes a small JSON result that the manager reads back when the Job
ends. The binary is part of the manager image (`/runner`).

You never start the runner by hand in normal use. The manager builds the
Job so that:

1. An init container, from the manager image, runs `/runner copy
   /captf/bin/runner`. This puts a copy of the binary on a shared volume,
   so the module's own image does not need to contain it.
2. The main container, from the module's source image, runs
   `/captf/bin/runner run` with the flags for one operation.

Run it yourself only to reproduce a failed Job in a container you control,
or to read its flags while debugging a Job spec. See the [image
contract](../module-author/image-contract.md) for the paths the runner
expects and [Choosing the Operation](../concepts/jobs/operations.md) for
when the manager picks each operation.

## Synopsis

```text
runner [global flags] copy <dest>
runner [global flags] run --op=<op> [flags]
runner [global flags] version
runner --version[=raw]
```

A bare `runner` prints its usage to standard error and exits with code `2`.

## Global flags

Every subcommand accepts these. They are the logging and version flags
that every Kubernetes component registers, so they behave as they do in
`kube-apiserver` or `kubectl`.

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `--feature-gates` | `key=value,...` | | Enable alpha or beta logging features. The gates are `AllAlpha`, `AllBeta`, `ContextualLogging`, `LoggingAlphaOptions` and `LoggingBetaOptions`. |
| `--log-flush-frequency` | `duration` | `5s` | Longest interval between log flushes. |
| `--log-json-info-buffer-size` | `quantity` | `0` | Alpha. Buffer info messages in JSON format with split streams. `0` disables buffering. Needs the `LoggingAlphaOptions` gate. |
| `--log-json-split-stream` | `bool` | `false` | Alpha. In JSON format, write errors to standard error and info messages to standard output. Needs the `LoggingAlphaOptions` gate. |
| `--log-text-info-buffer-size` | `quantity` | `0` | Alpha. The same buffering for text format with split streams. |
| `--log-text-split-stream` | `bool` | `false` | Alpha. The same stream split for text format. |
| `--logging-format` | `string` | `text` | Log format: `text` or `json`. The `json` format needs the `LoggingBetaOptions` gate, which is on by default. |
| `-v, --v` | `Level` | `0` | Log verbosity. |
| `--version` | `version` | `false` | Print version information and exit. `--version=raw` prints the full build information. `--version=vX.Y.Z` sets the reported version. |
| `--vmodule` | `pattern=N,...` | | Per-file verbosity. Works with the text format only. |

Invalid logging flags fail with exit code `2`. For `run`, they also write a
result (see [Result error kinds](#result-error-kinds)).

## copy

```text
runner copy <dest>
```

Copies the running binary to `<dest>` and sets it executable (mode `0755`).
`<dest>` is the one required argument and takes no flags. The Job's init
container uses it to place the runner at `/captf/bin/runner`.

```sh
/runner copy /captf/bin/runner
```

It exits `0` on success, `1` when it cannot read or write a file, and `2`
when it does not get exactly one argument.

## run

```text
runner run --op=<op> [flags]
```

Runs one operation in the Job's main container. It takes no arguments, only
flags. `--op` is required, and takes one of these:

| Operation | What the runner does |
| --- | --- |
| `apply` | Runs `init`, `validate`, then `apply`. With `--guard-deletes` or `--expect-plan`, it plans first, checks the plan, and applies the saved plan only when the checks pass. |
| `destroy` | Runs `init`, then `destroy`. |
| `refresh` | Runs `init`, then a refresh-only apply to update state from the real resources. |
| `drift` | Runs `init`, a refresh-only apply, then a plan without refresh, and reads the plan to report whether anything differs. |
| `plan` | Runs `init`, `validate`, then `plan`, and summarizes the plan for review. Nothing is applied. |
| `restore` | Runs `init`, then pushes a state backup assembled from `<config>/restore` and lists the result as a check. |

Every operation runs `init` first, with `-backend-config` values from
`--backend-config` and the lock timeout from `--lock-timeout`. When
`--force-unlock` is set, `force-unlock` runs right after `init`.

The result goes to `--result` when the run ends, whether it succeeded or
not.

### Paths and environment

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `--bin` | `stringArray` | `/captf/runtime` | The runtime command, one flag per element. Repeat it to pass a command with arguments. |
| `--config` | `string` | `/captf/config` | Directory with the rendered root module and tfvars: the mount of the per-run Secret. |
| `--module` | `string` | `/captf/module` | The module directory. |
| `--providers` | `string` | `/captf/providers` | The provider mirror directory. Optional. |
| `--workdir` | `string` | `/captf/work` | The writable work directory. |
| `--image` | `string` | | The source image reference, echoed in the result. |
| `--result` | `string` | `/dev/termination-log` | Where to write the result. |

### Runtime behavior

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `--op` | `string` | | The operation: `apply`, `destroy`, `refresh`, `drift`, `restore` or `plan`. Required. |
| `--backend-config` | `stringArray` | | A value for `init -backend-config`. Repeatable. |
| `--lock-timeout` | `duration` | `5m0s` | How long a step waits for the state lock. |
| `--stop-timeout` | `duration` | `1m0s` | How long an interrupted step has to stop before the runner sends it `SIGKILL`. |
| `--force-unlock` | `string` | | A stale lock ID to force-unlock after `init`. |

### Approval and plan checks

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `--guard-deletes` | `bool` | `false` | For `apply`: stop before a plan that deletes or replaces a resource, unless `--allow-deletes-hash` equals `--inputs-hash`. |
| `--inputs-hash` | `string` | | The hash of the inputs the Job renders. An approval of a destructive plan must name it. |
| `--allow-deletes-hash` | `string` | | The hash approved for a destructive plan. |
| `--expect-plan` | `string` | | For `apply`: the approved plan hash. Stops with error kind `plan-changed` unless the plan's hash matches. |
| `--plan-key-file` | `string` | `/captf/plan-key/key` | For `plan` and an approved `apply`: the file with the key of the plan fingerprint. Both fail when it cannot be read. |

See [The Destructive-Plan Guard](../concepts/approvals/destructive-guard.md)
and [Manual Plan Approval](../concepts/approvals/manual-approval.md) for
how the manager sets these.

### Restore and events

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `--restore-chunks` | `int` | `0` | For `restore`: the number of backup chunks under `<config>/restore`. |
| `--restore-resources` | `int` | `0` | For `restore`: the backup's count of managed resources. When it is not `0`, `state list` must show at least one. |
| `--event-object` | `string` | | Emit progress events about this object, as `<apiVersion>/<kind>/<namespace>/<name>/<uid>`. No events when unset. |
| `--job-name` | `string` | | The Job the events relate to. |

### Example

A plan Job for a cluster, as the manager would start it, trimmed to the
flags that matter:

```sh
/captf/bin/runner run \
  --op=plan \
  --image=registry.example.com/acme/cluster:v1.2.0 \
  --inputs-hash=<inputs-hash>
```

- `<inputs-hash>` is the hash the manager computed for the inputs it
  rendered into `--config`.

The manager supplies the rest through the defaults above and the mounts it
builds. A run that finishes writes its result to the container's
termination log, which the manager reads from the Pod status.

## version

```text
runner version
```

Prints the program name and its build information, then exits `0`.
`runner --version=raw` prints the full build information instead.

```sh
runner version
```

## Exit codes

| Code | Name | Meaning |
| --- | --- | --- |
| `0` | `ExitOK` | Every step succeeded, or an apply's plan had no changes to apply. |
| `1` | `ExitFailure` | A step failed, was interrupted, stopped before a destructive plan (blocked), or found that its approved plan had changed. Also returned when preflight or preparation fails, or when the result cannot be written. The runner never passes a step's own exit code through: that code is recorded in the result's `steps[].exit`, and a Terraform exit code `2` never becomes the process code. |
| `2` | `ExitUsage` | Bad input (the only source of `2`): an unknown `--op`, a bad flag, unexpected arguments or invalid logging flags. |

## Result document

`runner run` writes one JSON document, at most 4096 bytes. The manager
parses it, so the field names are fixed. `version` is `1`.

| Field | Contents |
| --- | --- |
| `version` | The result document version. |
| `op` | The operation that ran. |
| `image` | `ref`, the `--image` value as given (the resolved digest comes from the Pod status), and `providersMirror`, whether the image ships a provider mirror. |
| `runtime` | `command`, the runtime invocation, and `version`, the runtime version. |
| `steps` | One entry per command that ran: `name`, `exit` (the command's own exit code; a step killed by a signal or never started is recorded as `1`) and `seconds`. |
| `drift` | For a drift check: `detected`, the `add`, `change` and `destroy` counts, and `resources`, a list of addresses. `null` for other operations. |
| `error` | `null` on success, otherwise `kind`, `step` (the failing step, or `null`) and `tail`. |
| `changes` | Optional. The `add`, `change`, `destroy` and, when present, `import` counts from the runtime's final summary line of an apply or destroy. Absent when the step printed none. |
| `plan` | Optional. The plan summary of a plan Job, or of an apply whose plan changed. |

`error.tail` is a curated summary, not raw output, and is capped at 512
bytes. For `validate` it comes from the step's JSON diagnostics; for every
other step, from the `Error:` lines of its stderr. When there are none, it
names the step and its exit code. The full output is in the Pod log.

When the document is over 4096 bytes, the runner drops fields in a fixed
order. [Runtime Environment](../module-author/runtime-environment.md#output-size-limits)
lists that order.

## Result error kinds

`runner run` always writes a result document, to `--result` (the
termination log by default). A successful run has `error: null`. A failed
run carries an `error` object with a `kind`, the `step` that failed and a
bounded `tail` that summarizes the failure. The `kind` is one of:

| Kind | Meaning |
| --- | --- |
| `image-layout` | The image does not follow the [image contract](../module-author/image-contract.md): the module or runtime is not where the contract puts it. Fix the image. |
| `step` | A runtime step (`init`, `plan`, `apply` and so on) failed, or the runner's own setup failed, such as preparing the work directory or assembling a restore. A bad flag also reports this kind, with step `flags`. |
| `interrupted` | The Job was canceled while a step ran, for example by a drain, an eviction or a deletion. It does not count toward retry backoff. |
| `blocked` | A guarded `apply` stopped before a plan that deletes or replaces resources, because no approval names the inputs hash. It changed nothing, and the manager does not retry it until the inputs or the approval change. |
| `plan-changed` | An `apply` approved for one plan (`--expect-plan`) found a different plan. It changed nothing, carries the new plan and waits for it to be approved. |

!!! note "Results are small by design"

    The kubelet truncates a termination message at 4096 bytes. The runner
    drops optional detail, such as the plan's resource list, before it
    drops the counts and hashes the manager needs. The full output of every
    step is in the Pod log.

!!! related "See also"

    - [Image Contract](../module-author/image-contract.md) for the paths the
      runner uses.
    - [Retries and Backoff](../concepts/jobs/retries.md) for how the manager
      treats each failure.
    - [Choosing the Operation](../concepts/jobs/operations.md) for what
      selects each `--op`.
