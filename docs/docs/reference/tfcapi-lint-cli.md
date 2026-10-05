---
description: "Look up the tfcapi-lint commands, flags, exit codes and every check it runs against a CAPTF module or image, with severity and fix."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/scan-line
subtitle: "Lint flags and rule IDs"
---

# tfcapi-lint CLI

`tfcapi-lint` checks a Terraform or OpenTofu module, or the OCI image built
from it, against the CAPTF module contract and image contract. It reads the
module's files and the image's layers. It never runs `init`, `plan` or
`apply`, and it needs neither `terraform` nor `tofu`.

This page is the reference: every command, flag, exit code and check. For a
walkthrough, registry credentials and CI patterns, see
[tfcapi-lint](../module-author/tfcapi-lint.md).

## Install

Each provider release attaches one static binary per platform and a
checksum file: `tfcapi-lint-linux-amd64`, `tfcapi-lint-linux-arm64`,
`tfcapi-lint-darwin-amd64`, `tfcapi-lint-darwin-arm64`,
`tfcapi-lint-windows-amd64.exe` and `tfcapi-lint-checksums.txt` (SHA-256).
The binary has the same version as the provider release. There is no
Windows ARM64 build, and `go install` does not work because the repository
is a Go workspace.

```sh
curl -fsSLO "https://github.com/captf-io/cluster-api-provider-terraform/releases/download/<version>/tfcapi-lint-<os>-<arch>"
install -m 0755 "tfcapi-lint-<os>-<arch>" /usr/local/bin/tfcapi-lint
tfcapi-lint version
```

- `<version>` is the provider release, for example `v0.1.0`.
- `<os>` and `<arch>` pick a binary from the list above.

The [tfcapi-lint](../module-author/tfcapi-lint.md#install) guide shows
how to verify the checksum.

## Synopsis

```text
tfcapi-lint image  --role=<role> [flags] <image-ref>
tfcapi-lint module --role=<role> [flags] <module-dir>
tfcapi-lint version [--json]
tfcapi-lint --version[=raw]
```

`<role>` is `cluster`, `machine` or `machinepool`. A bare `tfcapi-lint`
prints its usage and exits `3`.

## Global flags

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `--version` | `version` | `false` | Print version information and exit. `--version=raw` prints the full build information. `--version=vX.Y.Z` sets the reported version. |

## module

```text
tfcapi-lint module --role=<role> [flags] <module-dir>
```

Lints a module directory against the contract. It reads the `.tf`,
`.tf.json`, `.tofu` and `.tofu.json` files in `<module-dir>` and in the
local modules it calls, and runs the [module checks](#module-checks) for
the role.

A module call is followed only when its `source` is a local path: `.`,
`..`, or a path starting with `./` or `../`. A registry, git, HTTP or other
remote module is never fetched or linted, so a `backend` or `cloud` block,
or a provider credential literal, inside one goes unseen.

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `--role` | `string` | | The module role: `cluster`, `machine` or `machinepool`. Required. |
| `--contract` | `string` | `v1alpha1` | The contract version to lint against. |
| `--json` | `bool` | `false` | Print a JSON report instead of text. |
| `--strict` | `bool` | `false` | Count warnings as errors for the exit code. |
| `--allow-warning` | `stringSlice` | | Downgrade this check ID's warnings to info. Repeatable, or a comma-separated list. Errors cannot be allowed. |

```sh
tfcapi-lint module --role cluster --strict ./modules/cluster
```

## image

```text
tfcapi-lint image --role=<role> [flags] <image-ref>
```

Lints a built source image against the image contract. It pulls the
manifest and layers without running the image, runs the [image
checks](#image-checks), and runs the module checks on the module in
`/captf/module`.

`<image-ref>` is a registry reference such as
`registry.example.com/acme/machine:v1.0.0`, or `oci:<dir>` for a local OCI
image layout. It authenticates with the same credential files as `docker`
and `podman`.

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `--role` | `string` | | The module role. Required. |
| `--contract` | `string` | `v1alpha1` | The contract version to lint against. |
| `--json` | `bool` | `false` | Print a JSON report instead of text. |
| `--strict` | `bool` | `false` | Count warnings as errors for the exit code. |
| `--allow-warning` | `stringSlice` | | Downgrade this check ID's warnings to info. Repeatable. Errors cannot be allowed. |
| `--platform` | `string` | `linux/amd64` | The platform to check in a multi-platform image. The default applies only to an index; a single-platform image is checked as it is unless you set `--platform` explicitly. |
| `--all-platforms` | `bool` | `false` | Check every platform the image publishes. |
| `--insecure` | `bool` | `false` | Allow a plain-HTTP registry. |

```sh
tfcapi-lint image --role machine --strict registry.example.com/acme/machine:v1.0.0
```

Lint a local image without a registry by saving it as an OCI layout first:

```sh
podman save --format oci-dir -o ./image <image>
tfcapi-lint image --role machine --strict oci:./image
```

- `<image>` is the local image name, for example `localhost/acme/machine:dev`.

If you set `--platform` explicitly and a single-platform image is for a
different platform, the result is an `image/platform` error. Without an
explicit `--platform`, a single-platform image is checked whatever its
platform. A multi-platform index with no manifest for the requested
platform (`linux/amd64` by default) gets the same error.

### Size cap

The linter caps how much of an image it reads. It keeps at most 512 MiB
of content: the module's files, the provider mirror's JSON indexes, and
512 bytes for every tar entry's header. It also scans, without keeping, the
rest of the filesystem (the runtime binary, provider archives and so on) up
to 32 times that, which is 16 GiB. An image over either cap is rejected
and the run exits `2`. There is no flag to raise the caps.

### Output

The text format prints one line per finding, then a summary:

```text
error input/required -:0 contract input bootstrap_data is not declared as a variable
0 error(s), 1 warning(s), 0 info (read terraform files)
```

A finding that concerns the whole module or image shows `-` as its file.
With `--json`, the report has a `findings` array and a `summary`. Each
finding has `id`, `severity` (`error`, `warning` or `info`), `file`, `line`
and `message`. `summary` counts `error`, `warning` and `info`. An image
report also describes the image it checked.

Findings are ordered by file, line and ID, so output is stable between
runs. `--allow-warning` changes a warning to `info` and says so in its
message.

## version

```text
tfcapi-lint version [--json]
```

Prints the program name and version, then exits `0`.

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `--json` | `bool` | `false` | Print JSON with `version`, `commit`, `date` and `contract`, the list of contract versions this build can lint against. |

```sh
tfcapi-lint version --json
```

## Exit codes

| Code | Name | Meaning |
| --- | --- | --- |
| `0` | `ExitOK` | No errors, and with `--strict`, no warnings. Info findings never fail a run. |
| `1` | `ExitFindings` | At least one error, or a warning under `--strict`. |
| `2` | `ExitUnparsable` | The module could not be read or parsed, or the image could not be pulled or extracted, including an image over the [size cap](#size-cap). |
| `3` | `ExitUsage` | A bad command line: a missing `--role`, an unknown role or contract version, a wrong number of arguments, or an invalid image reference. |

In CI, treat any non-zero code as a failed step. Use `--strict` to fail on
warnings, which is the recommended default.

## Checks

Every check has an ID of the form `<group>/<name>`, a severity and a fix.
Run `--json` to see IDs in a report. A finding's severity decides the exit
code:

| Severity | Effect |
| --- | --- |
| `error` | Fails the run. Cannot be allowed. |
| `warning` | Fails the run only with `--strict`. `--allow-warning <id>` downgrades it to `info`. |
| `info` | Never fails the run. |

The `module` command runs the module checks. The `image` command runs the
image checks and the module checks on the image's module. All module
checks apply to every role unless a row says otherwise.

### Module checks

#### Inputs

The contract's inputs are the variables the controller passes to your
module. See the [common contract](../module-author/contract/v1alpha1/common.md#inputs)
and the role pages for the full lists.

| ID | Severity | What it checks | How to fix |
| --- | --- | --- | --- |
| `input/required` | error | A contract input is not declared as a variable. | Declare a `variable` for it. |
| `input/type` | error | A contract input's type does not accept what the generated root passes. A missing type, or a type the linter cannot read, is a warning. | Declare a type that accepts the contract's type. |
| `input/default` | warning | An input the controller always sets to a non-null value has a default, which would hide a controller mistake. Nullable inputs may default to `null`. | Remove the `default`. |
| `input/sensitive` | warning | `bootstrap_data` is declared without `sensitive = true`, though it carries the bootstrap payload. | Add `sensitive = true`. |
| `input/reserved` | error | A variable uses the reserved `captf_` prefix but is not a contract input. The one exception is `captf_cluster_outputs`, which is allowed only when it has a default. | Rename the variable, or give `captf_cluster_outputs` a default. |
| `input/tags-declared` | error | The module does not declare `captf_tags`, the common input every module must accept. | Declare `captf_tags`. |
| `input/tags-unused` | warning | `captf_tags` is declared but never used, directly or through a local module that uses it. | Apply `var.captf_tags` to every resource that can carry tags. Allow the warning if the provider cannot tag anything. |
| `input/user-variable-default` | warning | A variable outside the contract has no default, so an object that does not set it in `spec.variables` or `variablesFrom` fails to apply. | Give it a `default`. |

#### Outputs

| ID | Severity | What it checks | How to fix |
| --- | --- | --- | --- |
| `output/required` | error | A contract output is not declared. | Declare an `output` for it. |
| `output/health` | error | The `health` output is not declared. Every module must report its health. | Declare `health` as the contract describes. |
| `output/reserved` | warning | An output uses the reserved `captf_` prefix. | Rename the output. |
| `output/endpoint-never-set` | warning | Cluster role only. `control_plane_endpoint` is a literal `null`, so a `KubeadmControlPlane` cluster with no user-set endpoint waits forever. | Output the endpoint your infrastructure creates. |
| `output/provider-id-list-shape` | error or warning | Machinepool role only. It is an error when `provider_id_list` is not declared. It is a warning when the expression filters on health or state, or is not sorted with `sort()`. | Declare it, list every non-terminated member, and wrap the list in `sort()`. |
| `pool/autoscaling-ignore-changes` | warning | Machinepool role only. The module uses `var.autoscaling`, but no resource ignores changes to its desired capacity, so each apply resets the cloud autoscaler. | Add the desired-capacity argument to `lifecycle { ignore_changes }`. |

#### Module source

CAPTF owns the backend and the credentials of a run, so a module must not
configure them.

| ID | Severity | What it checks | How to fix |
| --- | --- | --- | --- |
| `module/backend` | error | The root or a nested module declares a `terraform { backend }` block. | Remove it. The generated root owns the backend. |
| `module/cloud` | error | The root or a nested module declares a `terraform { cloud }` block. | Remove it, for the same reason. |
| `module/provider-config` | warning | A provider block sets a credential argument to a non-empty string literal, at the top level or inside a nested block or object. Names are matched case-insensitively against a fixed list (below). A reference such as `var.token`, and an empty string, are fine. | Take credentials from the identity, not from the module source. |
| `module/source-escape` | error | A local module call resolves outside the root module directory, directly or through a symlink, or does not resolve. A module file that is a symlink out of the root is also reported. Such code is never linted. | Keep every local module inside the root directory. |
| `module/tofu-shadow` | warning | A `.tofu` file shadows a `.tf` file, and OpenTofu loads different declarations than Terraform does. | Make the two files agree, or ship only one. |
| `module/version` | info | The module declares no `required_version`. | Declare the runtime versions you tested with. |

The `module/provider-config` list is `access_key`, `secret_key`,
`secret_access_key`, `session_token`, `token`, `access_token`,
`auth_token`, `bearer_token`, `api_token`, `api_key`, `apikey`, `password`,
`passphrase`, `client_secret`, `client_certificate`,
`client_certificate_password`, `client_key`, `private_key`,
`private_key_password`, `ssh_private_key` and `secret`. An argument with
any other name is not checked.

### Image checks

The image checks read the image's files and config. They apply to every
role. The [image contract](../module-author/image-contract.md) describes
the paths and labels they enforce.

#### Content

| ID | Severity | What it checks | How to fix |
| --- | --- | --- | --- |
| `image/module-present` | error | `/captf/module` has no `.tf`, `.tf.json`, `.tofu` or `.tofu.json` file at its top level. | Copy the module into `/captf/module`. |
| `image/module-link` | error | A link under `/captf/module` does not end at a regular file inside it. | Replace the link with the file. |
| `image/module-readable` | warning | With a numeric non-root user, a path under the module or provider mirror is not readable or traversable. The finding lists up to five paths. | Fix the file modes or ownership. |
| `image/runtime-present` | error | `/captf/runtime` is missing, is not a regular file, or is not executable by the image user. | Install the runtime there, executable. |
| `image/runtime-version` | warning | The runtime's file or link name looks like a different runtime than `io.captf.runtime` says. | Correct the label or the runtime. |
| `image/reserved-paths` | error | Files exist under `/captf/work`, `/captf/bin`, `/captf/config` or `/var/run/captf/credentials`, which the Job mounts over. The check covers only these four paths; the Job also mounts `/captf/plan-key` (when the object has a plan key) and `/tmp`, which it does not check. | Remove them. |
| `image/entrypoint` | info | `ENTRYPOINT` or `CMD` is set. The runner replaces both. | None needed. |
| `image/platform` | error | The image is not for the requested platform, or the index has no manifest for it. | Build for the platform, or pass `--platform`. |

#### Provider mirror

The mirror at `/captf/providers` is optional. Without it, `init` needs
registry access when the Job runs.

| ID | Severity | What it checks | How to fix |
| --- | --- | --- | --- |
| `image/providers-absent` | info | The image has no provider mirror. | Add a mirror to run without registry access. |
| `image/providers-layout` | error | An entry is neither a packed (`HOST/NS/TYPE/*.zip` with `*.json`) nor an unpacked (`HOST/NS/TYPE/VERSION/TARGET/`) mirror entry. | Use the mirror layout. |
| `image/providers-complete` | error | A mirror link is broken, or the mirror has no package for the checked platform for a provider the module requires. Built-in providers are exempt. | Mirror every required provider for the platform. |

#### Labels and user

| ID | Severity | What it checks | How to fix |
| --- | --- | --- | --- |
| `image/label-role` | info or error | `io.captf.role` is not set (info), or names a different role than `--role` (error). | Set the label to the role. |
| `image/label-contract` | info or warning | `io.captf.contract` is not set (info), or names a different version than `--contract` (warning). | Set the label to the contract version. |
| `image/label-capacity` | info or error | Machine role. `io.captf.capacity` and `io.captf.node-info` do not parse. Missing labels are info: no scale-from-zero capacity. Other roles get info only. | Make the labels valid JSON of the documented shape. |
| `image/user-root` | warning | The image runs as root, so the Job cannot run under the restricted Pod Security Standard. | Set a numeric non-root `USER`. |
| `image/user-unresolved` | warning | The image user is a name the linter cannot resolve, so permission checks are approximated. | Use a numeric uid. |

!!! tip "Allow a warning only with a reason"

    `--allow-warning` hides a warning from `--strict` but not from the
    report, where it shows as `info`. Pass one flag per ID you have
    decided to accept, and keep the list in the CI file so a reviewer sees
    each exception.

!!! related "See also"

    - [tfcapi-lint](../module-author/tfcapi-lint.md) for installing, strict
      mode and CI.
    - [Module Contract](../module-author/contract/README.md) and
      [Image Contract](../module-author/image-contract.md) for what the
      checks enforce.
