---
title: "Quick Start with the No-op Modules"
description: Install CAPTF on a management cluster and bring up a TerraformCluster and control-plane TerraformMachine with the no-op modules.
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "September 29, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-09-29"
authors:
  - "The CAPTF Authors"
icon: lucide/rocket
subtitle: "No cloud account needed"
---

# Quick Start

This tutorial takes CAPTF from an empty management cluster to a
`TerraformCluster` and a control-plane `TerraformMachine` that both report
`Ready`, using the no-op modules that ship with CAPTF: they create no real
infrastructure, so the tutorial needs no cloud account and no credentials.

!!! warning "This flow has not been run end to end"

    This tutorial has not been run end to end against a live management
    cluster.

Because the no-op modules provision nothing real, nothing ever boots a
kubelet: no `Node` ever joins, so `KubeadmControlPlane` never initializes
and the `Machine` never reaches its `Running` phase. What you watch come up
in this tutorial is CAPTF's own objects finishing their applies, not a
usable Kubernetes cluster. See [Your First Module](first-module.md) for
writing a module that does create something, and the [module
contract](../module-author/contract/README.md) for turning one into a real
cloud provider.

!!! info "Before you begin"

    - A Kubernetes cluster to use as the management cluster, and `kubectl`
      pointed at it.
    - `clusterctl` (v1.14 or later) and a clone of
      [`cluster-api-provider-terraform`](https://github.com/captf-io/cluster-api-provider-terraform):
      the `templates/...` paths below are relative to it. Check out the
      release tag you install, for example `git checkout v0.1.1`.
    - A management cluster that can pull from `ghcr.io`, where the manager
      image and the no-op module images are published.

Run every command below from the root of that clone.

## 1. Install the provider

CAPTF is not one of `clusterctl`'s built-in providers, so point a
`clusterctl` config at its release manifest; the config entry's `name` is
`terraform`, CAPTF's registered provider name:

```yaml title="clusterctl.yaml"
providers:
- name: terraform
  type: InfrastructureProvider
  url: https://github.com/captf-io/cluster-api-provider-terraform/releases/download/v0.1.1/infrastructure-components.yaml
```

Install that release:

```sh
clusterctl init --config clusterctl.yaml --infrastructure terraform:v0.1.1
```

This also installs Cluster API's core, bootstrap and control-plane
providers, and `cert-manager` itself if a compatible version is not already
present, since CAPTF's webhooks need it. See
[Installation](../operator-guide/installation.md) for what this creates
and how to confirm it, and [Installing from a local
repository](../developer-guide/releasing.md#installing-from-a-local-repository)
for the general form of the local-repository steps.

??? note "Install an unreleased change from a local build"

    To try a change that is not in a release, build the manager image from
    your clone, push it to a registry the management cluster can pull from,
    and render a local repository against it:

    ```sh
    export IMG=registry.example.com/you/cluster-api-provider-terraform:dev
    make docker-build docker-push IMG="${IMG}"
    make manifests-release RELEASE_DIR="${HOME}/local-repository/infrastructure-terraform/v0.1.1" \
      RELEASE_IMG="${IMG}" VERSION=v0.1.1
    ```

    Then use the `file://` form of the `url` in `clusterctl.yaml`, with
    `<you>` your user name, the absolute path of the directory
    `manifests-release` just wrote:

    ```yaml title="clusterctl.yaml"
    providers:
    - name: terraform
      type: InfrastructureProvider
      url: file:///home/<you>/local-repository/infrastructure-terraform/v0.1.1/infrastructure-components.yaml
    ```

## 2. Apply an identity

Cloud credentials come from a cluster-scoped `TerraformClusterIdentity`. An
admin applies one per set of credentials, naming the namespaces allowed to
use it:

```sh
export TERRAFORM_IDENTITY_NAME=aws-prod NAMESPACE=team-a
clusterctl generate yaml --from templates/identity.yaml | kubectl apply -f -
```

The no-op modules read no credentials, so the generated Secret's
placeholder keys can stay as they are; a module that calls a real cloud
provider reads its credentials from the same Secret. `kubectl get
terraformclusteridentity aws-prod` shows `Ready=True` once the Secret
exists and whoever applied the identity was allowed to `get` it — the
admission webhook checks. See [Identities and
Credentials](../user-guide/identities.md) for creating, rotating and
revoking credentials, and how they reach a Job.

## 3. Choose the no-op module images

The no-op modules are published as images by
[`captf-io/module-images`](https://github.com/captf-io/module-images), so
there is nothing to build. The module code is also on the Terraform Registry
as `captf-io/<role>/noop`. The cluster and machine roles are:

```sh
export NOOP_CLUSTER_IMAGE=ghcr.io/captf-io/module-images/noop-cluster:terraform
export NOOP_MACHINE_IMAGE=ghcr.io/captf-io/module-images/noop-machine:terraform
```

Each image comes in two tags, one per [base
image](../module-author/base-images.md):
`<version>-terraform` and `<version>-opentofu`, such as `vX.Y.Z-terraform`. Either satisfies the
[image contract](../module-author/image-contract.md). The bare `terraform`
and `opentofu` tags move to the newest release, and every tag is rebuilt if
the image changes without a module release; pin a release tag, or a
digest, in anything you keep. This tutorial uses the `terraform` tag. See
[No-op](../cloud-modules/noop/README.md) for what the modules return.

## 4. Generate and apply a cluster

`Cluster` objects and everything they own live in a namespace `clusterctl`
does not create:

```sh
kubectl create namespace team-a
```

Generate the default flavor and apply it. This tutorial asks for one
control-plane machine and no workers, since a worker never gets bootstrap
data until a real control plane initializes, which the no-op modules never
do:

```sh
export TERRAFORM_CLUSTER_IMAGE="${NOOP_CLUSTER_IMAGE}"
export TERRAFORM_MACHINE_IMAGE="${NOOP_MACHINE_IMAGE}"
export TERRAFORM_IDENTITY_NAME=aws-prod

clusterctl generate cluster my-cluster --from templates/cluster-template.yaml \
  --target-namespace team-a \
  --kubernetes-version v1.36.4 \
  --control-plane-machine-count 1 --worker-machine-count 0 \
  | kubectl apply -f -
```

`--from` renders the template file directly, so this command needs no
provider registration.
A ClusterClass-based flavor is also available; see [Templates and
ClusterClass](../user-guide/clusterclass.md), which also covers every
variable this template accepts, and [clusterctl
variables](../reference/clusterctl-variables.md) for their defaults and
built-in safeguards.

## 5. Watch it come up

```sh
kubectl get clusters,machines,machinepools,terraformclusters,terraformmachines,terraformmachinepools -n team-a
```

`machinepools` returns nothing: the default flavor creates none. See [Add
an autoscaled pool to a generated
cluster](../user-guide/machine-pools.md#add-an-autoscaled-pool-to-a-generated-cluster)
to add one to this cluster.

Each `Terraform*` kind reports a `Ready` condition, the only one Cluster
API reads (it is mirrored into the owning `Cluster`'s or `Machine`'s
`InfrastructureReady`). `Ready` is `Unknown` while an object waits on
dependencies or on its apply to finish, and `True` once the module's apply
succeeds:

```sh
kubectl get terraformcluster -n team-a my-cluster \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")]}'
```

Expect `TerraformCluster my-cluster` and the control-plane
`TerraformMachine` to both reach `Ready=True`, and their `PHASE` columns to
reach `Provisioned` on `Cluster my-cluster` and its control-plane `Machine`
too, since the no-op modules do return a control-plane endpoint and a
provider ID. What you will not see, because nothing real ever boots: the
`Machine` reaching phase `Running` (no `Node` ever registers), and
`KubeadmControlPlane` reporting itself initialized. That gap is expected
here and is exactly what a module that creates real infrastructure closes.

!!! warning "Watch within about 30 minutes"

    Past that, the control-plane `MachineHealthCheck`'s node-startup
    timeout fires because no `Node` ever registers, and
    `KubeadmControlPlane` starts remediating the `Machine` (see
    [Remediation](../user-guide/remediation.md)).

For what each condition type and reason means, see
[Conditions](../reference/conditions.md); for the reconcile flow behind
these states, see [The Reconcile Lifecycle](../concepts/lifecycle.md).

## 6. Clean up

!!! danger "Delete the Cluster first, not the namespace"

    Delete the `Cluster` first, and wait for it to be gone, rather than
    deleting the namespace outright: once a namespace starts terminating,
    the API server refuses to create the destroy Jobs each `Terraform*`
    object still needs to run before its own finalizer clears.

```sh
kubectl delete cluster my-cluster -n team-a
kubectl wait --for=delete cluster/my-cluster -n team-a --timeout=10m
```

That wait only returns once every descendant — `KubeadmControlPlane`, the
`MachineDeployment`, and both `TerraformCluster` and the control-plane
`TerraformMachine` — is gone too, the latter two only after their own
destroy Job finished.

An identity cannot be deleted while a `TerraformCluster`, `TerraformMachine`
or `TerraformMachinePool` still references it, so delete it only once the
wait above returns, then the now-empty namespace:

```sh
clusterctl generate yaml --from templates/identity.yaml | kubectl delete -f -
kubectl delete namespace team-a
```

To remove the provider itself as well:

```sh
clusterctl delete --config clusterctl.yaml --infrastructure terraform
```

!!! related "See also"

    - [Your First Module](first-module.md) to write a module that provisions
      something real.
    - [Installation](../operator-guide/installation.md) for what `clusterctl
      init` installs and how to verify it.
    - [Security Model](../concepts/security-model.md) for the trust boundary a
      `Terraform*` object's Job operates inside.
    - [The Kinds](../concepts/kinds.md) for how CAPTF's objects relate to
      Cluster API's.
