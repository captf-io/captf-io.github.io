---
description: "Compare how Terraform and OpenTofu store state in Secrets: Terraform chunks past 1 MiB, OpenTofu is capped at one Secret."
authors:
  - "The CAPTF Authors"
icon: lucide/scale
subtitle: "Chunked state vs one Secret"
---

# State Storage: Terraform and OpenTofu

CAPTF does not write state itself. The runtime inside the module image,
Terraform or OpenTofu, writes it through its own `kubernetes` backend, so
how much state an object can hold depends on which runtime its image
carries. The two backends share one origin and one Secret format, with one
difference that matters: **Terraform splits a large state across several
Secrets, and OpenTofu never does.** An OpenTofu state is therefore capped
at what one Secret holds, about 1 MiB compressed, while a Terraform state
is limited only by CAPTF's own reader.

This page compares the two backends, explains what happens when an
OpenTofu state reaches the cap, and covers choosing and switching
runtimes. For the naming, labels and read path that both runtimes share,
see [Terraform State Secrets](state.md).

## What both runtimes share

Both backends descend from the same Terraform code, and below the size
limit they write state in exactly the same shape:

| Item | Both runtimes |
| --- | --- |
| Base Secret | `tfstate-default-<suffix>`, in the object's namespace |
| Payload | The state JSON, gzip-compressed, raw bytes under the data key `tfstate` |
| Annotation | `encoding: gzip` |
| Backend labels | `tfstate=true`, `tfstateSecretSuffix=<suffix>`, `tfstateWorkspace=default` and `app.kubernetes.io/managed-by=terraform` (OpenTofu keeps the value `terraform`), plus CAPTF's [labels](state.md#labels) |
| Lock | A `coordination.k8s.io/v1` Lease, `lock-tfstate-default-<suffix>`, with the lock info in the `app.terraform.io/lock-info` annotation |

A state that fits in one Secret can therefore be read, locked and written
by either runtime. Once it no longer fits, they diverge.

## Terraform: chunked across Secrets

Since Terraform 1.6.0
([hashicorp/terraform#29678](https://github.com/hashicorp/terraform/pull/29678)),
the backend compresses the state, then cuts the compressed bytes into
pieces of exactly 1 MiB. The size is fixed in the backend's code, and no
setting changes it:

- The first piece goes in the base Secret. Each further piece goes in
  `tfstate-default-<suffix>-part-N`, numbered from 1, with the same labels
  and data key.
- To read, the backend lists every Secret matching its labels, orders them
  by the number after the last hyphen, concatenates the pieces and
  decompresses the result. This is why a `secret_suffix` must never end in
  `-<digits>`, a rule CAPTF's [suffix](state.md#names-and-the-suffix)
  keeps.
- Each piece is written with its own API call, so a write is not atomic
  across Secrets; the Lease is what keeps two writers apart. When the
  state shrinks, the backend writes the lower pieces first and then
  deletes the surplus `-part-N` Secrets. CAPTF's reader tolerates a
  surplus piece left behind if one of those deletes fails. See
  [Chunking and compression](state.md#chunking-and-compression).

The backend sets no upper bound on the number of pieces. CAPTF does: its
reader accepts at most 32 Secrets and 16 MiB of decompressed state (see
[Chunking and size caps](../state.md#chunking-and-size-caps)), and reports
anything larger as `StateCorrupt`. With real state compressing 10-20x, the
16 MiB decompressed cap is the one a Terraform state reaches first.

## OpenTofu: one Secret

OpenTofu forked from Terraform before chunking landed and has not added it.
Its backend (checked at v1.12.7) writes the whole compressed state into the
base Secret with a single create or update, and reads only that Secret. It
has no chunking code and no size setting. As of October 2026 we found no
OpenTofu issue or pull request that proposes chunking for this backend.

Kubernetes caps a Secret's data at 1 MiB (1,048,576 bytes), so that is the
ceiling for an OpenTofu state's compressed size. Below it, OpenTofu behaves
exactly like Terraform. The backend never checks the size itself: a write
past the cap reaches the API server and is rejected there, with the API
server's own validation error.

!!! danger "An OpenTofu apply that crosses 1 MiB loses the state it just wrote"

    When the backend rejects the final state write, OpenTofu saves the new
    state to `errored.tfstate` in its working directory and fails. In a
    CAPTF Job that directory is in the `/captf/work` emptyDir, and the runner does
    not collect the file, so it is deleted with the pod. The resources the
    apply created exist in the cloud, but the state Secret still holds the
    previous serial, which does not record them. The next apply then tries
    to create them again. Act on
    [`CAPTFStateNearSecretLimit`](../../operator-guide/observability.md#captfstatenearsecretlimit)
    before an apply crosses the cap, not after.

## Side by side

| | Terraform | OpenTofu |
| --- | --- | --- |
| Chunks state | Yes, since 1.6.0 | No (through 1.12.7) |
| Secrets per state | 1 + one `-part-N` per further MiB, compressed | Always 1 |
| Compressed-size ceiling | None in the backend; CAPTF reads up to 32 Secrets | 1 MiB |
| Decompressed ceiling under CAPTF | 16 MiB | About 1 MiB times the compression ratio |
| At the ceiling | CAPTF reports `StateCorrupt` and does not read the state | The apply fails to save state (see above) |
| `CAPTFStateNearSecretLimit` means | The state is about to need another Secret | The state is about to stop fitting |
| Base images | `terraform-base` (Terraform 1.16.5) | `opentofu-base` (OpenTofu 1.12.7) |

Terraform 1.5 and older wrote a single Secret, like OpenTofu. The
reference modules still validate against Terraform 1.5.7 as their floor,
but every image CAPTF publishes carries a current runtime. Only a custom
image built on a Terraform older than 1.6 has the OpenTofu limit.

## Choosing a runtime

Choose the runtime when you choose the module image (see
[Base Images](../../module-author/base-images.md)). For state size alone:

- **Machine state** is small: one instance and what it needs. Either
  runtime fits with a wide margin.
- **Cluster and machine pool state** grows with the module: networks,
  load balancers, certificates, rendered templates and one entry per pool
  instance. If a module's state might approach 1 MiB compressed, run it on
  Terraform, or split the module across more objects so each state stays
  small. The [size limits runbook](../../operator-guide/runbooks/size-limits.md#captfstatenearsecretlimit-the-state-is-approaching-a-secrets-size-cap)
  covers what makes a state large and how to shrink it.
- **Other OpenTofu features** may matter more for a given module. State
  encryption, the main one, is not readable by CAPTF either way (see
  [OpenTofu state encryption](../state.md#opentofu-state-encryption)).

To see how close an object is, read `captf_state_bytes` (the compressed
size summed over its Secrets) and `captf_state_resources` from
[the metrics](../../reference/metrics.md), or count its state Secrets:

```sh
kubectl get secret -n <ns> -l tfstate=true,tfstateSecretSuffix=<suffix> -o name
```

More than one result means Terraform has already chunked the state.

## Switching an existing object's runtime

A `TerraformMachine`'s `spec.source` is immutable, so its runtime never
changes. A `TerraformCluster` or `TerraformMachinePool` can move to an
image with the other runtime, and the new runtime then takes over the
existing state Secrets. Whether that works depends on the state's shape:

| Switch | Unchunked state (one Secret) | Chunked state (`-part-N` Secrets present) |
| --- | --- | --- |
| OpenTofu to Terraform | Works: the format is identical | Cannot occur: OpenTofu never writes chunks |
| Terraform to OpenTofu | Works: the format is identical | Fails: OpenTofu reads only the base Secret, a truncated gzip stream, and cannot load the state |

Before moving a Terraform object to OpenTofu, check that the state is a
single Secret with the command above, and that `captf_state_bytes` is
comfortably below 1 MiB: the first OpenTofu apply that grows it past the
cap hits the failure described in the danger box above. A state that
Terraform has already chunked must shrink below 1 MiB compressed, and
Terraform must have removed its `-part-N` Secrets, before OpenTofu can
take it over.

!!! related "See also"

    - [Terraform State](../state.md) for the caps, locks and what CAPTF
      reads.
    - [Terraform State Secrets](state.md) for naming, labels and the read
      path.
    - [Size limits runbook](../../operator-guide/runbooks/size-limits.md).
    - [Base Images](../../module-author/base-images.md) for the two
      runtimes' images.
    - [Compatibility](../../operator-guide/compatibility.md) for the
      supported runtime versions.
