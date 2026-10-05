---
description: "Every variable the CAPTF clusterctl templates read, with required and default values, grouped by flavor, plus the ClusterClass topology variables."
hide:
  - toc
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/variable
subtitle: "Variables for clusterctl templates"
---

# clusterctl Variables

clusterctl replaces shell-style `${NAME}` and `${NAME:=default}` references
in the CAPTF templates with environment variables. A variable with no
default and no value makes `clusterctl generate` fail, so a missing name
never deploys something you did not ask for.

The provider ships three templates:

| Template | Flavor | What it creates |
| --- | --- | --- |
| `cluster-template.yaml` | Default (no `--flavor`) | A `Cluster`, `TerraformCluster`, control plane, `MachineDeployment` and `MachineHealthCheck`s |
| `cluster-template-clusterclass.yaml` | `clusterclass` | A `Cluster` that references the `noop` `ClusterClass` through `spec.topology` |
| `identity.yaml` | None. Applied by an admin | A `TerraformClusterIdentity` and its credentials `Secret` |

Both cluster flavors read the same variables, so the first table covers
them. The identity template reads two. See [Templates and
ClusterClass](../user-guide/clusterclass.md#the-shipped-flavors) for what
each flavor creates and [Quick Start](../getting-started/quick-start.md) for
a full walkthrough.

## Cluster flavors: default and `clusterclass`

Both templates read every variable below. Variables marked as set by a
`clusterctl generate cluster` option need no `export`.

### Identity and module images

| Variable | Required | Default | Sets |
| --- | --- | --- | --- |
| `TERRAFORM_IDENTITY_NAME` | Yes | None | The `TerraformClusterIdentity` the cluster uses, and by default its machines. Default flavor: `TerraformCluster.spec.identityRef.name` and `spec.defaults.identityRef.name`. `clusterclass` flavor: the `identityName` topology variable |
| `TERRAFORM_CLUSTER_IMAGE` | Yes | None | The cluster module image: `TerraformCluster.spec.source.image`, or the `clusterImage` topology variable |
| `TERRAFORM_MACHINE_IMAGE` | Yes | None | The machine module image for control-plane and worker machines: `spec.template.spec.source.image` of both `TerraformMachineTemplate`s, or the `machineImage` topology variable |

### Cluster shape

| Variable | Required | Default | Sets |
| --- | --- | --- | --- |
| `CLUSTER_NAME` | Yes | None | The name of every object. Set by the name you pass to `clusterctl generate cluster` |
| `KUBERNETES_VERSION` | Yes | None | The version of the `KubeadmControlPlane` and `MachineDeployment`, or of the topology. Set by `--kubernetes-version` |
| `CONTROL_PLANE_MACHINE_COUNT` | Yes | None | Control-plane replicas. Set by `--control-plane-machine-count`. An odd number of at least 3 keeps a rollout with `maxSurge: 0` available |
| `WORKER_MACHINE_COUNT` | Yes | None | `MachineDeployment` replicas. Set by `--worker-machine-count` |
| `POD_CIDR` | No | `192.168.0.0/16` | `Cluster.spec.clusterNetwork.pods` |
| `SERVICE_CIDR` | No | `10.128.0.0/12` | `Cluster.spec.clusterNetwork.services` |

### Health check timeouts

Each timeout is in seconds. They tune the two `MachineHealthCheck`s: one
for the control plane and one for workers. In the `clusterclass` flavor
they set the same fields on the `Cluster` topology.

| Variable | Required | Default | Sets |
| --- | --- | --- | --- |
| `TERRAFORM_NODE_STARTUP_TIMEOUT` | No | `1200` | Worker `nodeStartupTimeoutSeconds` |
| `TERRAFORM_UNHEALTHY_TIMEOUT` | No | `1800` | Worker: seconds of `InfrastructureReady=False` before remediation |
| `TERRAFORM_CP_NODE_STARTUP_TIMEOUT` | No | `1800` | Control-plane `nodeStartupTimeoutSeconds`. Longer than the worker value because kubeadm init or join plus kube-vip does more work than a worker join |
| `TERRAFORM_CP_UNHEALTHY_TIMEOUT` | No | `3600` | Control-plane unhealthy timeout. Longer because replacing a control-plane machine costs more |

!!! warning "The unhealthy timeout must exceed one apply plus one drift interval"

    The unhealthy window starts when an apply starts, so set
    `TERRAFORM_UNHEALTHY_TIMEOUT` above your longest apply time plus one
    drift interval (30 minutes by default). Below that, Cluster API can
    replace a machine whose apply is still running.

## Identity template

`identity.yaml` is not a flavor. An admin applies it once per set of
credentials, with `clusterctl generate yaml`:

| Variable | Required | Default | Sets |
| --- | --- | --- | --- |
| `TERRAFORM_IDENTITY_NAME` | Yes | None | The name of the `TerraformClusterIdentity` and of its credentials `Secret` |
| `NAMESPACE` | Yes | None | The namespace allowed to use the identity (`spec.allowedNamespaces.list`) |

The generated `Secret` holds placeholder keys. Replace them with the
environment variables your module's providers read. See [Identities and
Credentials](../user-guide/identities.md).

```sh
export TERRAFORM_IDENTITY_NAME=<identity-name> NAMESPACE=<namespace>
clusterctl generate yaml --from templates/identity.yaml | kubectl apply -f -
```

Replace `<identity-name>` with the name clusters reference, and
`<namespace>` with the namespace they live in.

## Generate a cluster

Export the required variables that no option sets, then generate. This
example uses the default flavor and overrides two optional values:

```sh
export TERRAFORM_IDENTITY_NAME=<identity-name> \
  TERRAFORM_CLUSTER_IMAGE=<cluster-module-image> \
  TERRAFORM_MACHINE_IMAGE=<machine-module-image> \
  POD_CIDR=<pod-cidr> \
  TERRAFORM_UNHEALTHY_TIMEOUT=<seconds>

clusterctl generate cluster <cluster-name> --infrastructure terraform \
  --target-namespace <namespace> \
  --kubernetes-version <version> \
  --control-plane-machine-count 3 --worker-machine-count 2 \
  | kubectl apply -f -
```

Placeholders:

- `<identity-name>`: an existing `TerraformClusterIdentity` that allows
  `<namespace>`.
- `<cluster-module-image>` and `<machine-module-image>`: the module images,
  for example a tag you built for the cluster and machine roles.
- `<pod-cidr>` and `<seconds>`: optional. Leave them out to use the
  defaults in the tables above.
- `<cluster-name>`, `<namespace>` and `<version>`: the name, the target
  namespace and the Kubernetes version, such as `v1.36.3`.

`--infrastructure terraform` needs the provider registered with clusterctl.
To render a template file directly instead, replace it with `--from
templates/cluster-template.yaml`.

To use the `clusterclass` flavor, apply the class to the namespace once,
enable the `ClusterTopology` feature gate when you register the provider,
and add `--flavor clusterclass`:

```sh
kubectl apply -n <namespace> -f templates/clusterclass-noop.yaml
clusterctl generate cluster <cluster-name> --infrastructure terraform \
  --flavor clusterclass --target-namespace <namespace> \
  --kubernetes-version <version> \
  --control-plane-machine-count 3 --worker-machine-count 2 \
  | kubectl apply -f -
```

`clusterclass-noop.yaml` has no clusterctl variables and no namespace, so
apply it to every namespace that generates clusters from it.

## ClusterClass topology variables

The `noop` `ClusterClass` declares three topology variables. The
`clusterclass` flavor fills them from the clusterctl variables above, in
`Cluster.spec.topology.variables`. To change one later, edit the value on
the `Cluster`; you do not edit the class or its templates.

| Variable | Required | Type | Filled from | Description |
| --- | --- | --- | --- | --- |
| `identityName` | Yes | `string` | `TERRAFORM_IDENTITY_NAME` | Name of the `TerraformClusterIdentity` the cluster and, by default, its machines use |
| `clusterImage` | Yes | `string` | `TERRAFORM_CLUSTER_IMAGE` | Source image of the cluster module (`TerraformCluster.spec.source.image`) |
| `machineImage` | Yes | `string` | `TERRAFORM_MACHINE_IMAGE` | Source image of the machine module, for control-plane and worker machines. Changing it rolls the machines out |

```yaml
spec:
  topology:
    classRef:
      name: noop
    variables:
    - name: identityName
      value: <identity-name>
    - name: clusterImage
      value: <cluster-module-image>
    - name: machineImage
      value: <machine-module-image>
```

A `*Template` kind is immutable once created, so the topology controller
rolls a new `machineImage` out by creating a new `TerraformMachineTemplate`.
See [Template immutability and rolling out a
change](../user-guide/clusterclass.md#template-immutability-and-rolling-out-a-change)
and [The noop
ClusterClass](../user-guide/clusterclass.md#the-noop-clusterclass).
