---
title: "Production Readiness Checklist for CAPTF"
description: "Check the CAPTF manager and its namespaces before go-live: availability, sizing, certificates, secrets, alerts, approvals, network policy and Jobs."
git_creation_date_localized: "October 1, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-10-01"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/badge-check
subtitle: "Checklist before you go live"
---

# Production Readiness

This page is a go-live checklist for the CAPTF manager and the namespaces it
serves. Each item says what to check and why, and links to the page that
has the detail. It also says plainly what CAPTF does **not** do for you,
because several things a production cluster needs are the operator's to
provide.

!!! warning "Pre-alpha: treat this as a minimum, not a certification"

    CAPTF is pre-alpha: v0.1.0 and v0.1.1 are released, but it has run only in the
    opt-in end-to-end suites on a local kind cluster, with the noop modules
    and no real cloud; `clusterctl upgrade` and `move` have not run (see
    [Compatibility](compatibility.md#what-is-tested) and [Project
    status](../index.md#project-status)). Treat the checklist as the
    minimum for a trial you intend to keep, not as a certification.

## The checklist

| Area | Check | Detail |
| --- | --- | --- |
| Availability | Leader election is on and you know what failover costs | [Manager availability](#manager-availability) |
| Sizing | Requests and limits fit your object count; concurrency is deliberate | [Sizing](#sizing) |
| Webhooks | cert-manager is healthy and the serving certificate renews | [Webhook certificates](#webhook-certificates) |
| Environment | `POD_NAMESPACE` and `SERVICE_ACCOUNT_NAME` are set | [Required environment](#required-environment) |
| Secrets | etcd encryption is on; backups and DR are planned | [Secrets at rest](#secrets-at-rest) |
| Monitoring | The eleven alerts are installed and routed | [Alerts and metrics](#alerts-and-metrics) |
| Access | Who may write specs and who may approve is decided | [Approver and writer split](#approver-and-writer-split) |
| Network | The manager and the Job pods have egress policies | [Network policy](#network-policy) |
| Jobs | Pod Security level, Job policy defaults and quotas fit | [Runner Jobs](#runner-jobs) |
| Supply chain | You know what is scanned, signed and rebuilt, and how you pin images | [Supply chain](#supply-chain) |
| Manager pod | The shipped pod security settings suit your policy | [Manager pod security](#manager-pod-security) |
| Reporting | You know how to report a vulnerability and what is supported | [Vulnerability reporting](#vulnerability-reporting-and-supported-versions) |
| After go-live | You know what to watch in the first week | [First week](#the-first-week) |

## Manager availability

- [ ] **Replicas.** The shipped Deployment runs **two** replicas, with the
  leader election flag set: the leader reconciles and both serve the webhooks,
  so a restart or a node drain of one pod does not block writes. A rolling
  update keeps both available (`maxUnavailable: 0`, `maxSurge: 1`), a
  `PodDisruptionBudget` allows one voluntary disruption at a time, and a
  topology spread prefers separate nodes without requiring them. On a
  single-node cluster both replicas share the node, so a node loss still
  takes the webhooks down. Patching `replicas` to 1 is valid and stays
  drainable: while the manager restarts, running Jobs continue and it picks
  them up again.
- [ ] **Leader election.** The binary's `--leader-elect` defaults to `false`;
  the shipped manifest passes it. If you build your own manifest, enable it
  before you run more than one replica, or two managers reconcile the same
  objects. See [Configuration: leader
  election](configuration.md#leader-election).
- [ ] **Failover time.** A leader that shuts down on SIGTERM releases the
  election lease, so the standby takes over at once. After a crash or a node
  loss the standby waits for the lease to expire: up to 15 seconds with the
  defaults (lease 15s, renew 10s, retry 2s). A failover loses
  nothing: Jobs are Kubernetes objects, and the names, the leases and the
  cache-lag checks make the resumed work idempotent. The webhooks run on
  every replica, so writes keep working while no manager leads. See
  [Leader election and failover](../concepts/jobs/leader-election.md).
- [ ] **The webhook is on the write path.** All webhooks fail closed. If every
  manager pod is down, creating or updating a `Terraform*` object fails,
  including Cluster API's own writes. See [Webhook
  Unavailable](runbooks/webhook-unavailable.md).

## Sizing

- [ ] **Manager resources.** The shipped requests are 10m CPU and 128Mi of
  memory, with limits of 500m and 512Mi, and `GOMEMLIMIT` follows the memory
  limit. The sizes are an estimate, not yet measured: the informers hold
  Secrets without their data, so the steady state is small, and the limit
  leaves room for a reconcile that reads a large state (up to 64Mi
  decompressed) with several others in flight. Memory still grows with the
  number of objects and Jobs. Watch the manager's working set and raise the
  limit before it reaches it.
- [ ] **Concurrency.** `--terraformcluster-concurrency` and its machine, pool and
  template counterparts default to 10 each. They cap reconciles in flight
  per kind, not Jobs. A reconcile starts a Job and returns, so no flag caps
  the number of Jobs running at once; the bounds are one Job per object and
  your namespace quotas. Raise a concurrency flag when objects queue behind
  each other. See [Configuration: per-kind
  concurrency](configuration.md#per-kind-concurrency).
- [ ] **Resync.** `--sync-period` (10 minutes) is a safety net, not a schedule.
  Drift runs every `--drift-default-interval` (30 minutes) unless an object
  sets its own. A large fleet with the default drift interval starts a
  burst of Jobs every half hour. The jitter spreads it by up to a tenth of
  the interval; set longer intervals if that is too much. See [Requeue
  intervals and schedules](../concepts/jobs/schedules.md).
- [ ] **Job pods.** The runner's default request is 250m CPU and 512Mi, with a
  2Gi memory limit and no CPU limit. A large plan needs more: set
  `spec.jobs.resources`. See [Tuning Jobs](../user-guide/job-tuning.md).

## Webhook certificates

The validating webhooks are served with a certificate cert-manager issues
from a self-signed Issuer and injects into the webhook configuration. The
certificate Secret is mounted into the manager pod, and the volume is not
optional.

- [ ] **cert-manager must be installed** (`cert-manager.io/v1`). Without it the
  certificate Secret is never created and the manager pod stays in
  `ContainerCreating`.
- [ ] **Watch the certificate.** Check that the `Certificate` is `Ready` and its
  renewal works; an expired certificate stops all writes to `Terraform*`
  objects.
- [ ] **Bring your own.** `--webhook-cert-dir`, `--webhook-cert-name` and
  `--webhook-key-name` point the server at another certificate source if you
  do not use cert-manager. You then own CA injection too.

See [Installation](installation.md) and [Webhook
Unavailable](runbooks/webhook-unavailable.md).

## Required environment

The manager needs `POD_NAMESPACE` and `SERVICE_ACCOUNT_NAME`, which the
shipped Deployment sets from the downward API. From them it computes its
own username. The `TerraformMachine` webhook lets only that user set
`spec.providerID`.

!!! warning "A missing environment variable only logs a warning"

    If either is unset the manager only **logs a warning** and starts. Then the
    webhook rejects the manager's own `providerID` write, and no machine
    finishes provisioning. If you template your own manifest, check the
    variables are present; look for the warning in the manager's log at start.
`CAPTF_MANAGER_IMAGE` supplies the runner image unless `--runner-image` is
set.

## Secrets at rest

!!! warning "CAPTF adds no encryption of its own"

    Terraform state, state backups, rendered inputs and credential mirrors are
    Kubernetes Secrets. CAPTF adds **no encryption of its own**.

- [ ] **Enable etcd encryption at rest** (an `EncryptionConfiguration`, or your
  platform's equivalent) on the management cluster, and protect etcd
  snapshots as you would the state. See [No encryption at rest of its
  own](../concepts/secret-management/security.md#no-encryption-at-rest-of-its-own).
- [ ] **State backups.** `--state-backups` (default 5) keeps that many copies per
  object in the same namespace. They protect against a bad apply or a
  deleted state Secret, **not** against losing the namespace or the cluster.
  Plan external backups; see [Disaster Recovery](disaster-recovery.md).
- [ ] **Size.** A state near 1 MiB per Secret, or rendered inputs near 1,000,000
  bytes, need attention before they fail: see [Size
  Limits](runbooks/size-limits.md).

## Alerts and metrics

The Prometheus component is opt-in and **not** part of the release manifest.
Build it from a checkout of the tag you installed, and apply it again after
each upgrade. It adds a `ServiceMonitor` and a `PrometheusRule` named
`captf-alerts` with eleven alerts. CAPTF ships rules, not routing: connect
them to your Alertmanager.

| Alert | Severity | Fires when |
| --- | --- | --- |
| [`CAPTFJobFailing`](../reference/alerts.md#captfjobfailing) | warning | More than 2 failed or deadline-killed Jobs of a kind and op in 30 minutes |
| [`CAPTFDestroyStuck`](../reference/alerts.md#captfdestroystuck) | critical | A destroy failed in the last 30 minutes, for 30 minutes |
| [`CAPTFStateUnreadable`](../reference/alerts.md#captfstateunreadable) | critical | A state read error in 15 minutes |
| [`CAPTFClusterDrift`](../reference/alerts.md#captfclusterdrift) | warning | A cluster reports drift for an hour |
| [`CAPTFForceUnlocks`](../reference/alerts.md#captfforceunlocks) | warning | A stale lock was force-unlocked in the last hour |
| [`CAPTFReconcileErrors`](../reference/alerts.md#captfreconcileerrors) | warning | A controller errors at more than 0.1 per second for 10 minutes |
| [`CAPTFJobSlow`](../reference/alerts.md#captfjobslow) | info | p90 Job duration above 30 minutes |
| [`CAPTFJobQueueSlow`](../reference/alerts.md#captfjobqueueslow) | warning | p90 time from Job creation to start above 5 minutes |
| [`CAPTFStateNearSecretLimit`](../reference/alerts.md#captfstatenearsecretlimit) | warning | A state above 900 KiB |
| [`CAPTFInputsNearLimit`](../reference/alerts.md#captfinputsnearlimit) | warning | Rendered inputs above 900,000 bytes |
| [`CAPTFNoRecentSuccess`](../reference/alerts.md#captfnorecentsuccess) | warning | No successful refresh or drift for 6 hours |

Route `CAPTFDestroyStuck` and `CAPTFStateUnreadable` to someone who can act:
both mean infrastructure the controller can no longer manage safely. The
ServiceMonitor scrapes over HTTPS with the Prometheus ServiceAccount
`prometheus-k8s` in `monitoring`; edit the shipped RBAC if yours differs.
See [Observability](observability.md#enabling-the-prometheus-component).

Three metrics have no alert and are worth a dashboard: `captf_jobs_active`
(Jobs in flight), `captf_ready` (objects by readiness) and
`captf_identity_denied_total` (denied identity use). Also watch
`captf_lease_waits_total` for contention and `captf_state_backups_total` for
backups being taken. See [Metrics](../reference/metrics.md).

## Approver and writer split

!!! warning "Approval is Kubernetes RBAC, by design"

    **Approval is Kubernetes RBAC, by design.** Whoever may `patch` a
    `TerraformPlan` approves it, and needs nothing on the target. `create` on
    `terraformplans` equals approve, so only the manager and the
    `clusterctl move` identity get it. Whoever may `patch` a `TerraformCluster`
    may set its manual action (`captf.io/restore-state`) and
    `spec.deletionPolicy`, and the webhooks do not restrict them.
    Decide who holds each: approvers get `patch` on `terraformplans`, and
    everyone else's spec changes come through a reviewed path such as GitOps.
    See [Who can
    approve](../concepts/approvals/operating.md#who-can-approve) for example Roles
    and [Multi-Tenancy](multi-tenancy.md).

Gates also bind only the cluster: machines and pools are never gated, and a
change of the cluster's exports re-applies pools without approval. See
[Limits](../concepts/approvals/limits.md).

## Network policy

- [ ] **The manager.** `config/network-policy` is an opt-in component. It allows
  inbound TCP 9443 (webhook), 8443 (metrics) and 9440 (probes) and outbound
  DNS, 6443 and 443; everything else is denied. It needs a CNI that enforces
  `NetworkPolicy`. Check that your API server's address and port are
  covered by those rules, since the policy allows 6443 and 443 to any
  destination.
- [ ] **Job pods.** The component does **not** cover them. A sample
  (`job-egress-sample.yaml`, not applied) is a starting point to copy into
  each tenant namespace. Its cloud-provider egress is deliberately left out:
  add what your modules need, which depends on the cloud and the registry.
  Jobs hold cloud credentials, so egress is the control that limits where
  they can go. See [Network
  exposure](../concepts/security-model.md#network-exposure).

## Runner Jobs

- [ ] **Pod Security.** The Job pod defaults satisfy the `baseline` profile.
  `restricted` needs an image that runs as non-root, set through
  `jobs.podSecurityContext`, because `runAsNonRoot` is not defaulted.
  Label the tenant namespace with the level you enforce and test a Job in
  it. See [Pod security](../concepts/security-model.md#pod-security).
- [ ] **Job policy defaults.** Defaults are a one-hour deadline, a five-minute
  lock timeout, three retained successful and three failed Jobs per op, and
  the resources above. Set cluster-wide values in `spec.defaults.jobs` on the
  `TerraformCluster` so that machines and pools inherit them. See [Tuning
  Jobs](../user-guide/job-tuning.md) and [Deadlines and lock
  timeouts](../concepts/jobs/deadlines.md).
- [ ] **ResourceQuota.** Quotas can block what CAPTF creates, and **no
  quota-specific condition, event or metric exists**. A rejected Job create
  is returned as a reconcile error and gives its leases back. A pod the
  quota refuses stays attached to a Job that never starts, which would show up as
  `CAPTFJobQueueSlow`. Per Job, the namespace holds a Job and a pod, a
  per-run Secret, the state, durable-inputs and backup Secrets, and a few
  Leases; each namespace also holds a `captf-runner` ServiceAccount and
  RoleBinding. Size object-count quotas for retained Jobs: finished Jobs
  stay until pruned. See [Reconcile
  Errors](runbooks/reconcile-errors.md).

## Manager pod security

The shipped Deployment in `config/manager/manager.yaml` sets:

- **Pod:** `runAsNonRoot: true`, user and group `65532`, and seccomp
  `RuntimeDefault`.
- **Container:** `readOnlyRootFilesystem: true`,
  `allowPrivilegeEscalation: false`, `privileged: false`, and all
  capabilities dropped.
- **Scheduling:** a toleration for the `node-role.kubernetes.io/control-plane`
  `NoSchedule` taint, so it may run on control-plane nodes. There is no
  node selector or affinity. Two replicas are spread over nodes with a
  `ScheduleAnyway` topology spread constraint on the hostname, and a
  `PodDisruptionBudget` (`maxUnavailable: 1`) covers voluntary disruptions.
- **Probes:** liveness on `/healthz` (15s initial delay, 20s period) and
  readiness on `/readyz` (5s, 10s), both on port 9440.
- **Other:** two replicas, a 30 second termination grace period (a 5 second
  `preStop` sleep, which needs Kubernetes 1.30 or later, then a 20 second
  graceful shutdown), and resources as in [Sizing](#sizing).

This satisfies the `restricted` Pod Security profile for the manager's
namespace; the Job pods are a separate matter, covered under
[Runner Jobs](#runner-jobs).

## Supply chain

CAPTF publishes scanning results, signed images with attestations, and
signed-provenance release assets. It does not verify module images; plan your
own verification on top.

**Scanning.** The provider's `security` workflow runs on pushes to `main`,
on pull requests and weekly (Monday 05:17 UTC). The scanners below fail
their job on a finding, except CodeQL, which reports to code scanning:

| Scan | What it checks | Notes |
| --- | --- | --- |
| CodeQL | Go code, `security-and-quality` queries | Runs only when the repository variable `ADVANCED_SECURITY` is `true`; alerts go to code scanning |
| govulncheck | Reachable known vulnerabilities in the root and `api` modules | |
| osv-scanner | Dependencies, recursively | A pull-request variant scans the change |
| gitleaks | The full git history for secrets | |
| gosec | Go source, with SARIF upload | |
| Trivy, manifests | Misconfigurations in the rendered release manifest | Fails on HIGH and CRITICAL |
| Trivy, repository | Vulnerabilities and secrets in the tree | Fails on HIGH and CRITICAL, ignoring unfixed |
| Trivy, image | The `linux/amd64` manager image | Fails on HIGH and CRITICAL, ignoring unfixed |
| hadolint, zizmor, actionlint | The Dockerfile and the workflows | |

A separate `scorecard` workflow runs OpenSSF Scorecard on pushes to `main`
and weekly, only when the repository variable `SCORECARD` is `true`.

**The manager image.** It is built `FROM gcr.io/distroless/static:nonroot`,
pinned by digest, and runs as `65532:65532` with `/manager` as the
entrypoint. The same image is the runner. Pin the image you install by
digest as well.

**Signatures and attestations.** The `publish` workflow pushes the manager
image for every commit on `main` whose CI passed (`:edge`, `:sha-<commit>`)
and on every release tag whose commit passed CI (`:vX.Y.Z`), for `linux/amd64` and `linux/arm64`. Every pushed image
digest gets a keyless cosign signature (GitHub OIDC), a SLSA build-provenance
attestation and an SPDX SBOM attestation, stored in the registry and in
GitHub attestations. Every release asset gets a provenance attestation, and
the bundle is also attached as `provenance.intoto.jsonl`. Verify a release by
its version tag, and deploy the digest:

```sh
cosign verify ghcr.io/captf-io/cluster-api-provider-terraform:vX.Y.Z \
  --certificate-identity https://github.com/captf-io/cluster-api-provider-terraform/.github/workflows/publish.yaml@refs/tags/vX.Y.Z \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify oci://ghcr.io/captf-io/cluster-api-provider-terraform:vX.Y.Z \
  -R captf-io/cluster-api-provider-terraform
gh attestation verify infrastructure-components.yaml \
  -R captf-io/cluster-api-provider-terraform
```

`:edge` and `:sha-<commit>` images are signed on `refs/heads/main`: verify
those with
`--certificate-identity-regexp '^https://github.com/captf-io/cluster-api-provider-terraform/'`.

Add `--predicate-type https://spdx.dev/Document/v2.3` to the `gh` image
command to verify the SBOM. `tfcapi-lint` also has a checksum file. An image
pushed by the manual `make release` fallback is not signed. See
[Releasing](../developer-guide/releasing.md#signatures-and-attestations).

**SBOM.** The `security` workflow also produces an SPDX SBOM of the manager
image as a CI workflow artifact (`manager-image.spdx.json`); the signed SBOM
attestation above is the one published with the image. The base images
publish an SBOM and a maximum-mode provenance attestation with each build.

**Module images.** Nothing in CAPTF verifies a module image's signature;
see [Module image signatures](../concepts/security-model.md#pod-security).
Verify by digest, and admit images through your own policy controller if you
need signatures.

**Base image rebuilds.** The base images, `terraform-base` and
`opentofu-base`, are rebuilt weekly (Monday 05:17 UTC) with `apt-get
upgrade`, so a current base tag carries recent Ubuntu fixes. A module image
that pins a base by digest does not move with it: it gets OS fixes only
when its pin is bumped (Dependabot proposes this) and the module image is
rebuilt and re-published. Track both, and rebuild your own module images
on the same schedule.

## Vulnerability reporting and supported versions

Report vulnerabilities privately through GitHub's private vulnerability
reporting, on the Security tab of the affected repository. Do not open a
public issue. The team aims to acknowledge a report within seven days, with no
guaranteed response time. CAPTF is pre-1.0: fixes land on `main` and in the
next release, with no backports to earlier releases, and the base images are
rebuilt weekly, so use a current tag. The full policy is in
[`SECURITY.md`](https://github.com/captf-io/cluster-api-provider-terraform/blob/main/SECURITY.md).

## The first week

| Watch | Why | Where |
| --- | --- | --- |
| Manager restarts and the start-up log | A missing environment variable or certificate shows here | `kubectl logs`; [Required environment](#required-environment) |
| `Ready` on every object | The first sign that something is not provisioning | [Troubleshooting by Condition](troubleshooting/README.md) |
| Failed and slow Jobs | A new module's first applies fail and run long | [Failing Jobs](runbooks/job-failures.md), [Slow Jobs](runbooks/slow-jobs.md) |
| `DestructivePlanBlocked` and `PlanAwaitingApproval` | Your approval path must work | [Approvals and Gates](../concepts/approvals/README.md) |
| The first drift report | Drift settings, and whether the module's first plan is clean | [Drift](../user-guide/drift.md) |
| State size and backup counts | Growth, and that backups are taken | [Size Limits](runbooks/size-limits.md) |
| Webhook certificate and cert-manager | An expired certificate blocks writes | [Webhook Unavailable](runbooks/webhook-unavailable.md) |
| One restore and one delete rehearsal | You find the gaps before an incident | [State Restore](runbooks/state-restore.md), [Disaster Recovery](disaster-recovery.md) |

!!! related "See also"

    - [Installation](installation.md), [Configuration](configuration.md) and
      [Upgrades](upgrades.md).
    - [Known Limitations](limitations.md) and [Compatibility](compatibility.md).
    - [Security Model](../concepts/security-model.md).
