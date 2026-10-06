---
description: "Look up what the AWS machine module creates, its inputs, outputs, health, lifecycle and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/server
subtitle: "One EC2 instance"
---

# Machine

The `ghcr.io/captf-io/module-images/aws-machine` image implements the
[machine role](../../module-author/contract/v1alpha1/machine.md): one EC2
instance per `Machine`, control plane or worker. It takes the subnets,
security groups, instance profiles, API target groups and bootstrap bucket
from the [cluster](cluster.md) role's exports.

The module's source is
[`captf-io/terraform-aws-machine`](https://github.com/captf-io/terraform-aws-machine),
published on the Terraform Registry as
[`captf-io/machine/aws`](https://registry.terraform.io/modules/captf-io/machine/aws).

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `aws_instance.node_instance` | The node, in its zone's subnet, with IMDSv2 and an encrypted root volume | Always |
| `aws_s3_object.bootstrap_object` | The bootstrap data, staged as `control-plane/<machine>` or `worker/<machine>` in the cluster's bucket | `bootstrap_delivery = "s3"` (the default) |
| `aws_lb_target_group_attachment.api_target_attachments` | Registers the instance behind the API endpoint, so destroying the machine deregisters it | Control-plane machines, one per API port |

Without `machine_image.id` it looks up the image with a listing that returns
nothing rather than fails.

## Inputs

Contract inputs it uses: `captf_cluster_outputs`, `captf_tags`,
`machine_name` (the `Name` tag and the object key), `bootstrap_data`,
`bootstrap_format`, `failure_domain`, `kubernetes_version` (the image
lookup) and `control_plane`. With no `failure_domain` it picks a zone from
the hash of `machine_name`.

User variables, from
[variables.tf](https://github.com/captf-io/terraform-aws-machine/blob/main/variables.tf):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_security_group_ids` | `list(string)` | `[]` | Extra security groups for the instance. |
| `additional_tags` | `map(string)` | `{}` | Extra tags for every taggable resource; at most 40; keys 1 to 128 characters, values at most 256; letters, numbers, spaces and `_ . : / = + - @` only; no `aws:`, `captf.io/` or `kubernetes.io/cluster/` keys. |
| `bootstrap_delivery` | `string` | `"s3"` | `s3` stages the bootstrap data behind a small stub; `inline` sends it as user data, 16 KiB at most. |
| `external_cluster_exports` | `any` | `null` | The exports of an externally managed `TerraformCluster`, used when `captf_cluster_outputs` is empty. |
| `instance_metadata_hop_limit` | `number` | `1` | IMDSv2 hop limit, a whole number from 1 to 64; 2 lets pods without host networking reach the metadata service. |
| `instance_type` | `string` | `"m6i.large"` | EC2 instance type; matches the image's capacity labels (2 CPUs, 8 GiB, amd64). |
| `machine_image` | `object({ id = optional(string), owner = optional(string, "819546954734"), name_format = optional(string, "capa-ami-ubuntu-24.04-?{semver}-*"), architecture = optional(string, "x86_64") })` | `{}` | `id` pins the AMI; without it, the newest AMI from `owner` named `name_format`, with `{semver}` or `{version}` filled in. |
| `public_ip` | `bool` | `false` | Give the instance a public IPv4 address. |
| `root_volume_kms_key_id` | `string` | `null` | KMS key ARN for the root volume; null uses the account's default EBS key. |
| `root_volume_size_gib` | `number` | `40` | Root volume size in GiB; a whole number from 8 to 16384. |
| `root_volume_type` | `string` | `"gp3"` | `gp3` or `gp2`. |
| `spot` | `bool` | `false` | Run a one-time Spot Instance; refused for control-plane machines. |
| `ssh_key_name` | `string` | `null` | EC2 key pair; the cluster's `ssh_allowed_cidrs` decides who reaches SSH. |

## Outputs

| Output | Value |
| --- | --- |
| `provider_id` | `aws:///<zone>/<instance-id>`, the format cloud-provider-aws writes to the `Node` |
| `addresses` | `InternalIP`, `InternalDNS` and `Hostname` from the private IP and DNS name; `ExternalIP` and `ExternalDNS` with a public address |
| `failure_domain` | The zone the instance runs in |
| `interruptible` | `true` for a Spot Instance |
| `health` | See below |

## Health

| EC2 instance state | Contract state | Reason |
| --- | --- | --- |
| `pending` | `pending` | `InstancePending` |
| `running` | `running`, healthy | none |
| `stopping` | `stopped` | `InstanceStopping` |
| `stopped` | `stopped` | `InstanceStopped` |
| `shutting-down` | `terminated` | `InstanceShuttingDown` |
| `terminated` | `terminated` | `InstanceTerminated` |
| Gone from state | `terminated` | `InstanceNotFound` |
| Anything else | `unknown` | `UnknownState` |

The provider drops a terminated instance from state on refresh, so a
terminated machine usually reads `InstanceNotFound`.

## Lifecycle

A machine is immutable. Changes to the looked-up image and to the user-data
stub (a newer module release) are ignored on an existing instance instead
of stopping and starting it; they reach the cluster through new machines.

## Bootstrap

- **Staged (the default).** The bootstrap data goes to the cluster's S3
  bucket, readable only by the matching node role: control-plane nodes read
  `control-plane/*`, workers `worker/*`. The user data is a small
  `#cloud-boothook` that fetches it once and installs it in
  `/etc/cloud/cloud.cfg.d`, as [Shared Behavior](../shared-behavior.md#bootstrap-data)
  describes. With Ignition, the user data is a config that replaces itself
  with the object; gzipped Ignition is refused.
- **Inline.** `bootstrap_delivery = "inline"` sends the data as user data,
  a plain cloud-config gzipped, anything else as it is, up to 16 KiB. Anyone
  who can call `ec2:DescribeInstanceAttribute` or reach the instance
  metadata service can then read it, control-plane CA keys included.

## Limitations

!!! warning "Nodes must register under their private DNS names"

    Nodes must register under their private DNS names, which
    cloud-provider-aws looks them up by.

- Spot interruptions are not drained beyond what a termination handler in
  the cluster does.
- The staged data stays on the node as
  `/etc/cloud/cloud.cfg.d/99-captf-bootstrap.cfg`, root only, and in the
  Terraform state.
- With a customer managed `root_volume_kms_key_id`, the identity needs
  `kms:CreateGrant`, `kms:Decrypt`, `kms:GenerateDataKeyWithoutPlaintext`,
  `kms:ReEncrypt*` and `kms:DescribeKey` on the key.

## Exceptions

None: the role follows the conventions as written.

## Example

```yaml title="terraformmachinetemplate.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachineTemplate
metadata:
  name: demo-md-0
spec:
  template:
    spec:
      source:
        image: ghcr.io/captf-io/module-images/aws-machine:v0.1.0-opentofu
      variables:
        instance_type: m6i.large
```
