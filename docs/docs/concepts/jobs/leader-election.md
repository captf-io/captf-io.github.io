---
description: Configure leader election and see what a manager failover does to Jobs in flight.
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/vote
subtitle: "What happens on leader change"
---

# Leader Election and Failover

Only one manager reconciles at a time. This page covers how the election is
configured, what runs only on the leader, and what a failover looks like to
the Jobs that were in flight, which is where the leases, the deterministic
names and the cache-lag checks pay off.

## Configuration

| Flag | Default | Meaning |
| --- | --- | --- |
| `--leader-elect` | `false` | Turn the election on |
| `--leader-elect-lease-duration` | `15s` | How long non-leaders wait before they force-acquire |
| `--leader-elect-renew-deadline` | `10s` | How long the leader retries a renewal before it gives up |
| `--leader-elect-retry-period` | `2s` | How often a candidate tries |

The default is off, but the shipped Deployment sets `--leader-elect` and
runs two replicas: one leads, and the other serves the webhooks and stands
by.

!!! warning "Run more than one replica only with leader election on"

    Turn the election on whenever you run more than one replica.

The lock is a `coordination.k8s.io` Lease named
`controller-leader-election-captf` in the manager's namespace; the manager
needs the [leader-election Role](../../operator-guide/rbac.md#the-leader-election-role)
for it. The leader releases the lease when it shuts down cleanly on SIGTERM
(`LeaderElectionReleaseOnCancel`), so the standby takes over at once. After a
crash or a node loss the lease is not released, and the standby waits for it
to expire, up to 15 seconds by default. See [Configuration](../../operator-guide/configuration.md#leader-election).

## What runs only on the leader

| Component | On every replica | Leader only |
| --- | --- | --- |
| The `TerraformCluster`, `TerraformMachine`, `TerraformMachinePool`, template and identity controllers | | Yes |
| The orphan sweep (start, then every `--sync-period`) | | Yes |
| The admission webhooks | Yes | |
| Health and readiness endpoints | Yes | |

A replica that is not the leader serves webhooks and idles. Per-kind
concurrency (`--terraformcluster-concurrency` and its machine, template and
pool counterparts, default 10 each) is the number of reconciles in flight on
the leader. One reconcile never runs two Jobs for one object, so
concurrency affects throughput across objects, not safety.

## What a failover does to a Job

A Job is a Kubernetes object. It keeps running when the manager goes away,
and the new leader finds it. Everything the old leader knew is in the API
server:

| Where the old leader stopped | What the new leader sees | What resolves it |
| --- | --- | --- |
| Before taking the run lease | Nothing | The decision is made again |
| After taking the lease, before creating the Job | A lease whose holder Job does not exist | The same Job name is derived and acquired, or the lease is free after the one-minute [grace](leases.md#grace-and-backstop) |
| After creating the Job, before its per-run Secret | A Job whose pod waits for a missing volume | The next pass creates the Secret (the Job exists: `AlreadyExists` is adopted); after a minute a Job that cannot start is deleted and recreated |
| After creating the Job, before the status patch | A Job and a block-move annotation, no `status.activeJob` | The Job is in the list or [the lease shows it](cache-lag.md) |
| While the Job runs | A running Job | Watched to the end |
| After the Job finished, before bookkeeping | A finished Job, not bookkept | Bookkeeping reads its pod, once |
| After bookkeeping, before the status patch persisted | The Job is not marked bookkept | The marker is written only after the patch, so the Job is read again |

The last row is by design: the controller marks a Job bookkept only after
the status patch that records its result succeeded, and counts it once
(its per-run Secret is deleted once). A failure to mark is logged and
retried.

The new leader reconciles every object once as its caches fill, then on
events and requeues. Nothing is lost by a failover. What it costs is time:
up to the lease duration after a crash (almost none after a clean shutdown,
which releases the lease), plus a reconcile of every object.

## Two leaders

Election failure modes (a long pause, a partitioned leader) can briefly give
two managers the idea they lead. The run lease is the answer: whichever
creates or updates the lease first, using a `resourceVersion` it just read
from the API server, wins; the other waits as `WaitingForRunLease` with the
message "another manager took it first". See [Leases](leases.md).

!!! related "See also"

    - [Leases and the operation gate](leases.md).
    - [Requeue intervals and schedules](schedules.md).
    - [Reconcile Errors](../../operator-guide/runbooks/reconcile-errors.md).
