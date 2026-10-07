---
title: "Installing the CAPTF Provider"
description: "Install the CAPTF provider into a management cluster with clusterctl, set the runner image, add optional components and verify the install."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 1, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-01"
authors:
  - "The CAPTF Authors"
icon: lucide/download
subtitle: "Install the manager"
---

# Installation

This page covers installing the CAPTF provider into a management cluster
with `clusterctl`: what to have ready first, how to register the provider,
what the install creates, how the runner image is set, the optional
components, and how to confirm the install worked. It is for whoever
administers the management cluster, not for cluster tenants.

!!! info "Before you begin"

    - A management cluster and a `kubectl` context pointing at it. On a
      fresh cluster, `clusterctl init --infrastructure terraform` also
      installs Cluster API's core, bootstrap (kubeadm) and control-plane
      providers (see the [Quick start](../getting-started/quick-start.md)). On
      a cluster where Cluster API is already initialized, it adds only CAPTF.
    - `clusterctl`, matching the version documented for the Cluster API release
      you run.
    - `cert-manager`, with the `cert-manager.io/v1` API available. `clusterctl
      init` installs a compatible `cert-manager` release itself when one is not
      already present, so a separate install step is only needed to pin a
      specific `cert-manager` version or to install it ahead of time.
    - Cluster API installed at a release that implements the same contract
      CAPTF does. CAPTF's own `metadata.yaml` lists one release series so far,
      contract `v1beta2`; CAPTF is built and tested against Cluster API
      v1.14.2.

## Register the provider

CAPTF is not one of `clusterctl`'s built-in providers, so `clusterctl` needs
a config file naming its release manifest. The config entry's `name` is
`terraform`:

```yaml title="clusterctl.yaml"
providers:
- name: terraform
  type: InfrastructureProvider
  url: https://github.com/captf-io/cluster-api-provider-terraform/releases/latest/infrastructure-components.yaml
```

`url` can also name a specific tag instead of `latest`, for example
`.../releases/download/v0.2.0/infrastructure-components.yaml`, or a `file://` path
into a local repository built from a release's assets; see [Installing from
a local repository](../developer-guide/releasing.md#installing-from-a-local-repository)
for the local repository layout and for pinning a version.

!!! tip "Pin a version"

    `latest` follows the newest release. For anything you keep, pin one:
    `clusterctl init --config clusterctl.yaml --infrastructure terraform:v0.2.0`.

## Install with clusterctl init

```sh
clusterctl init --config clusterctl.yaml --infrastructure terraform
```

`clusterctl init --infrastructure terraform:vX.Y.Z` pins a specific
released version instead of the newest one clusterctl can see.

On a fresh cluster this also installs the Cluster API core and kubeadm
providers. If you plan to use the ClusterClass flavor, enable the
`ClusterTopology` feature gate before running `init` — it is alpha in
Cluster API and off by default:

```sh
CLUSTER_TOPOLOGY=true clusterctl init --config clusterctl.yaml --infrastructure terraform
```

`CLUSTER_TOPOLOGY=true` only takes effect when this `init` installs the
core provider. If Cluster API's core is already installed, the variable
changes nothing: enable the `ClusterTopology` feature gate on the core
controller (`capi-controller-manager`) instead.

## What gets installed

Everything below lands in one namespace, `captf-system`, which the install
creates as a `Namespace` object; `clusterctl init`
also installs `cert-manager` itself when it is missing, in its own
namespace.

- **CRDs** for the eight kinds: `TerraformCluster`,
  `TerraformClusterTemplate`, `TerraformMachine`, `TerraformMachineTemplate`,
  `TerraformMachinePool`, `TerraformMachinePoolTemplate`,
  `TerraformClusterIdentity` and `TerraformPlan` (`TerraformClusterIdentity` is
  cluster-scoped; the rest are namespaced). See [The Kinds](../concepts/kinds.md) for what each one does,
  and [Custom Resources](../reference/resources/README.md) for every field.
- **The manager**, a two-replica `Deployment` named
  `captf-controller-manager`, running as a non-root user, with a
  `ServiceAccount` of the same name. Leader election is on: the leader
  reconciles, and both replicas serve the webhooks. A `PodDisruptionBudget`
  (`maxUnavailable: 1`) keeps one replica serving during a node drain. It serves its webhooks on `:9443`, its
  metrics on `:8443`, and its health and readiness probes on `:9440`.
- **The admission webhook**: a `ValidatingWebhookConfiguration` named
  `captf-validating-webhook-configuration`, one rule per kind, backed by the
  `captf-webhook-service` `Service`. Its serving certificate is a
  `cert-manager` `Certificate` (`captf-serving-cert`, issued by the
  self-signed `Issuer` `captf-selfsigned-issuer`). cert-manager writes it to
  the Secret `captf-webhook-service-cert`, which the manager pod mounts
  read-only at `/tmp/k8s-webhook-server/serving-certs`; CA injection keeps the
  webhook configuration's CA current. The pod cannot start until that Secret
  exists.
- **RBAC** for the manager itself: the `ClusterRole` `captf-manager-role`
  and its `ClusterRoleBinding`, plus a leader-election `Role` and
  `RoleBinding` scoped to `captf-system`. The manager also creates a
  runner `ServiceAccount` and `RoleBinding` in each tenant namespace at
  first use, from the static `ClusterRole` `captf-runner`. See
  [RBAC](rbac.md) for what each role grants and for the per-namespace
  runner setup.

The manager pod tolerates the `node-role.kubernetes.io/control-plane:NoSchedule`
taint, and has liveness (`/healthz`) and readiness (`/readyz`) probes on the
`healthz` port. The replicas prefer separate nodes (a `ScheduleAnyway`
topology spread on the hostname), so a single-node cluster still schedules
both. The container has a `preStop` sleep of 5 seconds, which needs
Kubernetes 1.30 or later, where the sleep lifecycle action is on by default.
For what to tune for production, see
[Production Readiness](production-readiness.md).

None of this installs a `TerraformClusterIdentity` or any Terraform*
object: those come from templates you apply afterward, covered in
[Identities and Credentials](../user-guide/identities.md) and [Templates
and ClusterClass](../user-guide/clusterclass.md).

## The manager image and the runner image

`clusterctl init` sets the manager container's image to the release's
image, pinned by digest:
`ghcr.io/captf-io/cluster-api-provider-terraform@sha256:<digest>`. The same
reference is also set as the `CAPTF_MANAGER_IMAGE` environment variable on
that container: it is the default of `--runner-image`, the image the
manager runs as the init container that injects the runner binary into
every Job it creates. Point `--runner-image` at a different reference
(for example a registry mirror the tenant namespaces' Jobs can reach, or a
build carrying a patched runner binary) when the manager's own image is
not the one you want Jobs to pull; see [`--runner-image`](../reference/manager-flags.md)
for the flag and [Job Environment](../reference/environment.md) for how the
init container uses it. `spec.source.image` on a `Terraform*` object is
unrelated: it names the role image the Job actually runs, never the
runner.

A custom deployment, or an overlay that replaces the manager's `env`, must
keep `POD_NAMESPACE` and `SERVICE_ACCOUNT_NAME`, set from
`metadata.namespace` and `spec.serviceAccountName` through the downward
API. See [Manager environment](configuration.md#manager-environment).

The manager image is signed with keyless cosign and carries provenance and
SBOM attestations, and the release assets carry provenance attestations.
To verify them before installing, see [Supply
chain](production-readiness.md#supply-chain).

## Optional components

`config/prometheus` and `config/network-policy` are kustomize components:
neither is part of `infrastructure-components.yaml`, so `clusterctl init`
never installs them and `clusterctl upgrade` never touches them, and
neither is a release asset — get them from a checkout of the tag you
installed (see [Register the provider](#register-the-provider)), not from
the release URL. A kustomize `Component` builds standalone: point a bare
kustomization at one with no `resources:` of your own, and it emits only
that component's own objects, carrying the `captf-`/`captf-system` names
`config/default` produces:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
components:
- <path-to-checkout>/config/prometheus
```

- **Prometheus** (`config/prometheus`): a metrics `Service`, a
  `ServiceMonitor`, the alerting rules, and the RBAC Prometheus needs to
  scrape the manager's authenticated metrics endpoint. See [Enabling the
  Prometheus component](observability.md#enabling-the-prometheus-component)
  for what it adds and how to wire it up, and how a later upgrade affects
  it.
- **Network policy** (`config/network-policy`): a `NetworkPolicy` that
  restricts the manager pod to webhook, metrics and health-probe traffic
  inbound, and DNS, the API server and container registries outbound. It
  only has an effect on a CNI that enforces `NetworkPolicy`, and it covers
  only the manager pod, not runner Jobs; `config/network-policy/job-egress-sample.yaml`
  is a separate starting point to copy into each tenant namespace for its
  Job pods. See [Network exposure](../concepts/security-model.md#network-exposure)
  for why the manager's and a Job's exposure differ.

Building both at once needs both under `components:` in the same
kustomization. Building either on top of a from-source install of
`config/default` (rather than the one `clusterctl init` already installed)
also works, but is unnecessary for these two components: each one's
objects stand alone and never depend on `config/default`'s own resources
being built alongside them.

## Verifying the install

```sh
kubectl -n captf-system rollout status deployment/captf-controller-manager
kubectl get crds -l cluster.x-k8s.io/provider=infrastructure-terraform
kubectl get validatingwebhookconfigurations captf-validating-webhook-configuration
kubectl -n captf-system get certificate captf-serving-cert
kubectl -n captf-system get secret captf-webhook-service-cert
```

The rollout command returns once the manager pod is ready. The CRD list
should show all eight kinds. The webhook configuration and the certificate
must both exist and the certificate must report `Ready=True`, cert-manager
was able to issue the webhook's serving certificate: without it, webhook
calls from the API server fail closed (`failurePolicy: Fail`) and every
`Terraform*` create or update is rejected.

If the manager pod sits in `ContainerCreating`, check the last command
first: the pod mounts that Secret, and it does not exist until cert-manager
has issued the certificate. `kubectl -n captf-system describe certificate
captf-serving-cert` shows why issuance is stuck.

If you installed the [Prometheus component](observability.md#enabling-the-prometheus-component),
confirm who is allowed to scrape the metrics endpoint:

```sh
kubectl get clusterrolebinding captf-metrics-reader -o yaml
```

The `subjects` list should name your Prometheus ServiceAccount (the shipped
default is `monitoring/prometheus-k8s`).

`clusterctl init` itself prints the components it installed; `clusterctl
describe cluster` (once you have created one) reports whether CAPTF's
objects are ready.

!!! related "See also"

    - [Upgrades](upgrades.md) for upgrading an existing install.
    - [Configuration](configuration.md) for the manager flags you set on top of
      this default install.
    - [RBAC](rbac.md) for the manager's and runner's permissions in full.
    - [Security Model](../concepts/security-model.md) for the trust boundary a
      `Terraform*` object's Job operates inside.
