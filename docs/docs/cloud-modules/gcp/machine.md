---
description: "Look up what the Google Cloud machine module creates, its inputs, outputs, health, lifecycle and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "Steven Crothers"
icon: lucide/server
subtitle: "One Compute Engine VM"
---

# Machine

The `ghcr.io/captf-io/gcp-machine` image implements the
[machine role](../../module-author/contract/v1alpha1/machine.md) for a
`TerraformMachine`, cloned from a `TerraformMachineTemplate`. It creates one
Compute Engine instance per `Machine`, control plane or worker, and joins
control-plane instances to the API load balancer.

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `google_compute_instance.node_instance` | A Shielded VM with no external address, running as the cluster's control-plane or worker service account | Always |
| `google_compute_instance_group_membership.api_instance_group_membership` | Joins the API instance group of the instance's zone, in the machine's own state, so destroying the machine leaves the group | Control-plane machines of a cluster with a module-owned endpoint |
| `google_secret_manager_secret.bootstrap_secret` | Holds the bootstrap data, replicated in the cluster's region and labeled | Control-plane machines with `cloud-config` data and `bootstrap_delivery = "secret-manager"` |
| `google_secret_manager_secret_version.bootstrap_secret_version` | The bootstrap data itself | Same |
| `google_secret_manager_secret_iam_member.bootstrap_secret_accessor` | `roles/secretmanager.secretAccessor` for the control-plane service account on that one secret | Same |

The instance runs `machine_type` from `image`, with a `boot_disk_size_gib`
GiB boot disk of `boot_disk_type`, optionally encrypted with
`boot_disk_kms_key_id`. It has Shielded VM with vTPM and integrity
monitoring, Secure Boot unless `secure_boot` is off, OS Login on,
project-wide SSH keys blocked and the serial console off. It runs with the
`cloud-platform` scope, so the service account's IAM roles alone decide its
access, and carries the cluster's node tag, its role tag and
`additional_network_tags`.

The instance name is the Node name, because cloud-provider-gcp looks
instances up by Node name: `machine_name` when it is a valid Compute Engine
name, else `machine_name` with invalid characters replaced, `m-` in front
when it starts with a digit, cut to 54 characters, then `-` and 8 hex
characters of its sha256.

## Inputs

Contract inputs it uses:

- `machine_name`: the instance name.
- `bootstrap_data`, `bootstrap_format`: the instance's user data or the
  staged secret.
- `failure_domain`: the zone. Without one, the module picks a zone from the
  sha256 of `machine_name`.
- `kubernetes_version`: fills the image placeholders.
- `control_plane`: the service account, the network tag, staging and the
  API registration.
- `captf_cluster_outputs`: the cluster's exports.
- `captf_cluster`, `captf_object`, `captf_tags`: descriptions and labels.

User variables, set with `spec.template.spec.variables` on the
`TerraformMachineTemplate`
([variables.tf](https://github.com/captf-io/gcp-modules/blob/main/machine/variables.tf)):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_network_tags` | `list(string)` | `[]` | Extra network tags for the instance, on top of the cluster's node and role tags. |
| `additional_tags` | `map(string)` | `{}` | Extra GCP labels for the instance and its boot disk. Keys and values must already be valid GCP labels; the `captf-io_` keys are reserved for `captf_tags`, which win. |
| `boot_disk_kms_key_id` | `string` | `null` | Cloud KMS key (`projects/.../cryptoKeys/...`) that encrypts the boot disk. Null uses Google-managed encryption; the Compute Engine service agent needs encrypt and decrypt on the key. |
| `boot_disk_size_gib` | `number` | `50` | Boot disk size in GiB: room for the image, container images and logs. |
| `boot_disk_type` | `string` | `"pd-balanced"` | Boot disk type. `pd-balanced` suits the default N2 machine type; C3, N4 and newer series need `hyperdisk-balanced`. |
| `bootstrap_delivery` | `string` | `"secret-manager"` | How a control-plane machine's `cloud-config` data reaches it: `secret-manager` stages it in a per-machine secret behind a small user-data script, which needs `curl`, `sed`, `base64` and `gzip` in the image; `inline` puts it in instance metadata. Workers and Ignition are always inline. |
| `can_ip_forward` | `bool` | `false` | Let the instance send and receive packets for other addresses, as CNIs that route pod CIDRs through GCP routes need. |
| `external_cluster_exports` | `any` | `null` | Exports (schema `captf.io/gcp-cluster/v1`) to use when the `TerraformCluster` is externally managed and `captf_cluster_outputs` is `{}`. Ignored otherwise. |
| `image` | `string` | `null` | Boot image: a name, `family/<family>`, `projects/<p>/global/images/<image>` or a self link, with optional placeholders (below). Required. |
| `machine_type` | `string` | `"n2-standard-4"` | Machine type of the instance. The default matches the image's capacity labels (4 vCPU, 16 GiB). |
| `secure_boot` | `bool` | `true` | Shielded VM Secure Boot. Turn it off only for images whose kernel modules are unsigned (some GPU drivers). |
| `spot` | `bool` | `false` | Run as a Spot VM: cheaper, preemptible at any time; a preempted instance stops and reports `stopped`. Refused for control-plane machines. |

The `image` placeholders take `kubernetes_version`: `{version}` gives
`v1.33.4`, `{semver}` `1.33.4` and `{slug}` `v1-33-4`, all without an RKE2
`+rke2rN` suffix; `{fullslug}` keeps it, `v1-33-4-rke2r1`. Image names allow
no dots or `+`.

## Outputs

| Output | Value |
| --- | --- |
| `provider_id` | `gce://<project>/<zone>/<instance name>`, what cloud-provider-gcp writes and parses ([`gce_util.go`](https://github.com/kubernetes/cloud-provider-gcp/blob/v37.1.1/providers/gce/gce_util.go) `providerIDRE`) |
| `addresses` | The NIC's `InternalIP`, and an `ExternalIP` when an access config exists (never, as created): what cloud-provider-gcp reports ([`gce_instances.go`](https://github.com/kubernetes/cloud-provider-gcp/blob/v37.1.1/providers/gce/gce_instances.go)) |
| `failure_domain` | The instance's zone: the requested `failure_domain`, or the module's pick |
| `interruptible` | `true` for a Spot VM |
| `health` | Below |

Extra outputs: `api_instance_group_membership_id`, `instance_id` (the
numeric ID, which changes only when the instance is replaced) and
`instance_self_link`.

## Health

From the instance's `current_status`, read on every refresh:

| Instance status | Contract state | Reason |
| --- | --- | --- |
| `RUNNING` | `running`, healthy | none |
| `PENDING`, `PROVISIONING`, `STAGING` | `pending` | `InstancePending`, `InstanceProvisioning`, `InstanceStaging` |
| `REPAIRING` | `degraded` | `InstanceRepairing` |
| `PENDING_STOP`, `STOPPING`, `STOPPED`, `SUSPENDING`, `SUSPENDED`, `TERMINATED` | `stopped` | `InstancePendingStop`, `InstanceStopping`, `InstanceStopped`, `InstanceSuspending`, `InstanceSuspended`, `InstanceTerminated` |
| `DEPROVISIONING` | `terminated` | `InstanceNotFound` |
| any other | `unknown` | `UnknownState` |
| The instance no longer exists | `terminated` | `InstanceNotFound` |

`TERMINATED` is Compute Engine's word for stopped: the instance and its disk
still exist. A preempted Spot VM is `TERMINATED`, so it reports `stopped`
and a MachineHealthCheck can replace it.

## Lifecycle

A machine is immutable: CAPTF applies it once. The image is a create-time
property: changes to `image` are ignored on an existing instance, so a drift
check never reports an image family's newer image as a replacement. Roll a
new image through a new `TerraformMachineTemplate`. The instance group
membership is replaced with the instance, since a replaced instance keeps
its self link but leaves the group.

## Bootstrap

| Machine | Format | Delivery |
| --- | --- | --- |
| Control plane, `bootstrap_delivery = "secret-manager"` (default) | `cloud-config`, plain or gzipped | Staged in Secret Manager; the instance metadata `user-data` holds a small `#cloud-boothook` script |
| Worker, or `bootstrap_delivery = "inline"` | `cloud-config`, plain or gzipped | The base64 data in `user-data` with `user-data-encoding=base64`, which cloud-init's GCE data source decodes |
| Any | Ignition | Decoded into `user-data`, which Ignition reads as it is; gzipped Ignition is refused |

The staging script takes the instance's access token from the metadata
server, reads the secret version over the Secret Manager REST API with
`curl`, and installs the data as
`/etc/cloud/cloud.cfg.d/99-captf-bootstrap.cfg` (see
[Shared Behavior](../shared-behavior.md#bootstrap-data)). It retries for
five minutes, which covers the access binding's IAM propagation. Destroying
the machine deletes the secret.

Size limits: a secret version holds at most 64 KiB, and an instance
metadata value 256 KB. A larger payload fails a precondition; gzip it.

Who can read the data:

- Staged: the control-plane service account, and anything on the node that
  can take its token from the metadata server, pods included. Block pod
  egress to `169.254.169.254` with a NetworkPolicy, except for the system
  components that need it.
- Inline: anyone with `compute.instances.get` in the project, which
  `roles/viewer` and `roles/compute.viewer` include, and anything on the
  node that reaches the metadata server. Worker data holds only a
  short-lived join token.

## Limitations

!!! warning "Instance names collide across namespaces in a shared project"

    Instance names are unique per project and zone, so two `Machine`s of the
    same name in different namespaces collide in a shared project.

- A failure domain must be one of the cluster's zones, and a control-plane
  machine's zone must have an API instance group.
- Control-plane machines refuse `spot`: a preempted control-plane node takes
  an etcd member with it.
- The staged script needs `curl`, `sed`, `base64` and `gzip` in the image;
  set `bootstrap_delivery = "inline"` for images without them.

## Exceptions

- **Ignition control-plane data stays in instance metadata.** Ignition
  cannot run the staging script's authenticated fetch, so Ignition data
  goes inline, readable through `compute.instances.get` and the metadata
  server. `bootstrap_delivery = "inline"` makes the same trade for
  `cloud-config`.

## Example

```yaml title="terraformmachinetemplate.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachineTemplate
metadata:
  name: demo-md-0
  namespace: team-a
spec:
  template:
    spec:
      source:
        image: ghcr.io/captf-io/gcp-machine:v0.1.0-opentofu
      variables:
        image: projects/my-images/global/images/capi-ubuntu-2404-{slug}
        machine_type: n2-standard-4
```
