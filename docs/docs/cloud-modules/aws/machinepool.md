---
description: "Look up what the AWS machinepool module creates, its inputs, outputs, health, lifecycle and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/boxes
subtitle: "Auto Scaling group of nodes"
---

# MachinePool

The `ghcr.io/captf-io/aws-machinepool` image implements the
[machinepool role](../../module-author/contract/v1alpha1/machinepool.md):
one Auto Scaling group of worker instances per `MachinePool`. It takes the
subnets, the worker security group and instance profile, and the bootstrap
bucket from the [cluster](cluster.md) role's exports.

The module's source is
[`captf-io/terraform-aws-machinepool`](https://github.com/captf-io/terraform-aws-machinepool),
published on the Terraform Registry as
[`captf-io/machinepool/aws`](https://registry.terraform.io/modules/captf-io/machinepool/aws).

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `aws_autoscaling_group.pool_autoscaling_group` | The group across the pool's zones, launching the newest launch template version | Always |
| `aws_launch_template.pool_launch_template` | Image, instance type, worker identity and security groups, IMDSv2, encrypted root volume, tags, and the user-data stub | Always; replaced only to roll |
| `aws_autoscaling_policy.pool_scaling_policy` | Target tracking on average CPU | With autoscaling enabled |
| `aws_s3_object.bootstrap_object` | The bootstrap data as `pool/<machinepool_name>`, rewritten in place on every rotation | With complete exports |
| `terraform_data.kubernetes_version_roll` | The Kubernetes version and an explicit `machine_image.id`; replacing it replaces the launch template | Always |
| `terraform_data.inherited_zones` | The cluster's zones at the pool's first apply | Always; used without `failure_domains` |

It reads the members with one `aws_instances` listing per cluster zone and
two group-wide listings for their states, and looks up the image like the
[machine role](machine.md).

## Inputs

Contract inputs it uses: `captf_object` (the namespace in the group's name),
`captf_cluster_outputs`, `captf_tags`, `machinepool_name`, `replicas`,
`bootstrap_data`, `bootstrap_format`, `failure_domains`,
`cluster_failure_domains`, `kubernetes_version`, `node_labels` and
`autoscaling`.

User variables, from
[variables.tf](https://github.com/captf-io/terraform-aws-machinepool/blob/main/variables.tf):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_security_group_ids` | `list(string)` | `[]` | Extra security groups for the instances. |
| `additional_tags` | `map(string)` | `{}` | Extra tags for every taggable resource; at most 40; keys 1 to 128 characters, values at most 256; letters, numbers, spaces and `_ . : / = + - @` only; no `aws:`, `captf.io/` or `kubernetes.io/cluster/` keys. |
| `autoscaling_target_cpu_percent` | `number` | `60` | Average CPU the scaling policy holds the group at while autoscaling is enabled; greater than 0 and at most 100. |
| `external_cluster_exports` | `any` | `null` | The exports of an externally managed `TerraformCluster`, used when `captf_cluster_outputs` is empty. |
| `instance_metadata_hop_limit` | `number` | `1` | IMDSv2 hop limit, a whole number from 1 to 64; 2 lets pods without host networking reach the metadata service. |
| `instance_type` | `string` | `"m6i.large"` | EC2 instance type; applies to instances launched afterwards. |
| `machine_image` | `object({ id = optional(string), owner = optional(string, "819546954734"), name_format = optional(string, "capa-ami-ubuntu-24.04-?{semver}-*"), architecture = optional(string, "x86_64"), root_device_name = optional(string, "/dev/sda1") })` | `{}` | `id` pins the AMI, and changing it rolls the instances; without it, the newest AMI from `owner` named `name_format`. `root_device_name` is the image's root device: `/dev/sda1` for Ubuntu, `/dev/xvda` for Amazon Linux and Flatcar. |
| `public_ip` | `bool` | `false` | Give the instances public IPv4 addresses. |
| `rollout_instance_warmup_seconds` | `number` | `300` | Seconds a roll waits after each new instance is in service; a whole number, 0 or more. |
| `root_volume_kms_key_id` | `string` | `null` | KMS key ARN for the root volumes; a customer managed key must grant `AWSServiceRoleForAutoScaling`. |
| `root_volume_size_gib` | `number` | `40` | Root volume size in GiB; a whole number from 8 to 16384. |
| `root_volume_type` | `string` | `"gp3"` | `gp3` or `gp2`. |
| `spot` | `bool` | `false` | Launch Spot Instances, with capacity rebalancing. |
| `ssh_key_name` | `string` | `null` | EC2 key pair; the cluster's `ssh_allowed_cidrs` decides who reaches SSH. |

## Outputs

| Output | Value |
| --- | --- |
| `provider_id` | The Auto Scaling group's ARN |
| `provider_id_list` | `aws:///<zone>/<instance-id>` of every pending, running, stopping or stopped instance tagged with the group's name, sorted |
| `replicas` | The group's desired capacity as last observed |
| `instances` | Per member: provider ID, instance ID, `InternalIP` address, zone and state |
| `health` | See below |
| `autoscaling_group_name` (extra) | The group's name |
| `dropped_node_labels` (extra) | The labels left out of the kubelet's registration |
| `launch_template_id` (extra) | The current launch template; it changes only when the instances roll |

## Health

| AWS state | Contract state | Reason |
| --- | --- | --- |
| The group was deleted out of band | `terminated` | `GroupNotFound` |
| Desired capacity 0 | `running`, healthy | none |
| No member yet | `pending` | `NoMembers` |
| A member `stopping` or `stopped` | `stopped` | `InstanceStopped:<instance-id>` per member |
| Every member running, as many as desired | `running`, healthy | none |
| Members still `pending`, or fewer or more than desired | `running`, unhealthy | `InstancePending:<instance-id>` per member, `ScalingInProgress` |

## Lifecycle

| Change | Launch template | Running instances |
| --- | --- | --- |
| `bootstrap_data` (about every 7.5 minutes) | Unchanged; only the S3 object is rewritten | Kept |
| `node_labels`, `instance_type`, a looked-up image, `spot`, root volume, security groups | New version under `$Latest` | Kept; new instances get it |
| `kubernetes_version`, its `+rke2rN` suffix included, or an explicit `machine_image.id` | Replaced, create before destroy | Replaced by a rolling instance refresh that launches each replacement first |
| `replicas`, with autoscaling off | Unchanged | The group grows or shrinks |
| A zone the cluster adds or removes, for a pool without `failure_domains` | Unchanged | Kept: the pool keeps the cluster's zones of its first apply |
| A zone added to `failure_domains` | Unchanged | Kept: new instances go there over time (zone rebalancing is suspended) |
| A zone removed from `failure_domains` | Unchanged | The instances in it are replaced elsewhere, undrained |

With autoscaling enabled, the group's minimum and maximum come from the
`MachinePool` annotations and an apply never resets the desired capacity;
with it off, the minimum and maximum equal `replicas`.

## Bootstrap

The bootstrap data is staged in S3 as `pool/<machinepool_name>`, readable
by the worker role, and rewritten in place on every rotation, so the launch
template never changes with it. The user data is a `#cloud-boothook` that
writes the node labels on every boot and, once per instance, fetches the
data and installs it in `/etc/cloud/cloud.cfg.d`, as
[Shared Behavior](../shared-behavior.md#bootstrap-data) describes. The stub
must stay within EC2's 16 KiB of user data, which only many node labels can
exceed. Pools have no inline delivery. With Ignition the stub is a config
that replaces itself with the object, and node labels are refused.

## Limitations

!!! warning "Scale-in, a roll and Spot rebalancing do not drain nodes"

    Scale-in, a roll and Spot rebalancing terminate instances without
    draining their nodes. Run a termination handler such as
    aws-node-termination-handler with an Auto Scaling lifecycle hook if your
    workloads need it.

- CPU target tracking is a proxy: pods waiting for capacity do not raise
  CPU. The Kubernetes Cluster Autoscaler cannot drive these pools.
- Running members keep the labels they registered with until they are
  replaced.
- Membership is read in every cluster zone on every refresh: one
  `DescribeInstances` call per zone, plus two for member states.
- The staged data stays in the Terraform state.

## Exceptions

- A change of an explicit `machine_image.id` rolls the instances: the
  pinned image carries the kubelet, and with ClusterClass it can render in a
  later apply than the version.
- Removing a zone from `failure_domains` replaces the instances in it: the
  group cannot keep instances in a zone it no longer spans.

## Example

```yaml title="terraformmachinepool.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformMachinePool
metadata:
  name: demo-pool-0
  labels:
    cluster.x-k8s.io/cluster-name: demo
spec:
  source:
    image: ghcr.io/captf-io/aws-machinepool:v0.1.0-opentofu
  variables:
    instance_type: m6i.large
```
