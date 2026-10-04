---
description: "Look up what the AWS cluster module creates, its inputs, outputs, health reporting and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "Steven Crothers"
icon: lucide/network
subtitle: "VPC, load balancer, IAM"
---

# Cluster

The `ghcr.io/captf-io/aws-cluster` image implements the
[cluster role](../../module-author/contract/v1alpha1/cluster.md). In the
VPC and subnets you bring, it creates the API endpoint (a Network Load
Balancer), the security groups, the node identities and the S3 bucket the
nodes fetch their bootstrap data from, and publishes them in its `exports`
for the [machine](machine.md) and [machinepool](machinepool.md) roles.

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `aws_lb.api_load_balancer` | Network Load Balancer for the Kubernetes API | Without a user-supplied endpoint |
| `aws_lb_target_group.api_target_groups` | TCP target groups on the backend ports: the API port with kubeadm, 6443 for RKE2's kube-apiserver, 9345 for the RKE2 supervisor | One per API port, with the load balancer |
| `aws_lb_listener.api_listeners` | TCP listeners on the endpoint ports, forwarding to the target groups | One per API port, with the load balancer |
| `terraform_data.api_endpoint_guard` | Records the scheme, port and subnets; fails any plan that would change them | With the load balancer |
| `aws_security_group.api_load_balancer_security_group` | The load balancer's security group, given at creation | With the load balancer |
| `aws_security_group.control_plane_security_group` | Control-plane nodes: the API backend ports | Always |
| `aws_security_group.node_security_group` | Every node; the only group tagged for the cloud controller manager | Always |
| `aws_vpc_security_group_ingress_rule.node_ingress_rules` | All traffic between the cluster's nodes; SSH from `ssh_allowed_cidrs` | Always; SSH rules per CIDR |
| `aws_vpc_security_group_egress_rule.node_egress_rules` | All outbound traffic from the nodes | Always |
| `aws_vpc_security_group_ingress_rule.control_plane_ingress_rules` | API backend ports from the load balancer and the IPv4 pod CIDRs, or from `api_allowed_cidrs` with a user-supplied endpoint | Per port and source |
| `aws_vpc_security_group_ingress_rule.api_load_balancer_ingress_rules` | Endpoint ports from the nodes and `api_allowed_cidrs` | With the load balancer |
| `aws_vpc_security_group_egress_rule.api_load_balancer_egress_rules` | Traffic and health checks to the control-plane nodes | With the load balancer |
| `aws_iam_role.node_roles` | Control-plane and worker roles under `/captf/` | Each unless its instance profile is brought |
| `aws_iam_role_policy.node_role_policies` | The cloud-provider-aws policies: the Node Policy for workers, the Control Plane and Node Policies for control-plane nodes | With each role |
| `aws_iam_role_policy_attachment.node_role_policy_attachments` | The managed policies in `node_role_policy_arns` | Per policy, with each role |
| `aws_iam_instance_profile.node_instance_profiles` | The instance profiles machines and pools launch with | With each role |
| `aws_s3_bucket.bootstrap_bucket` | Holds the staged bootstrap data | Always |
| `aws_s3_bucket_public_access_block.bootstrap_bucket_public_access` | Blocks every form of public access | Always |
| `aws_s3_bucket_server_side_encryption_configuration.bootstrap_bucket_encryption` | SSE-S3 encryption | Always |
| `aws_s3_bucket_policy.bootstrap_bucket_policy` | TLS only; each node role reads only its own key prefixes; workers denied the control-plane payloads | Always |

It reads the VPC, the node subnets and the load balancer's own subnets with
listings that return nothing rather than fail, so a destroy still runs after
your network is gone; it reads the VPC's CIDR only when the VPC exists and
an internal endpoint defaults to it.

## Inputs

Contract inputs it uses: `captf_cluster` (the names), `captf_tags`,
`control_plane_endpoint` (non-null skips the load balancer) and
`cluster_network` (`api_server_port`, default 6443, and the `pods` CIDRs).
It declares `captf_object`, `kubernetes_version` and
`control_plane_initialized` without using them.

User variables, from
[variables.tf](https://github.com/captf-io/aws-modules/blob/main/cluster/variables.tf):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_tags` | `map(string)` | `{}` | Extra tags for every taggable resource; at most 40, no `aws:`, `captf.io/` or `kubernetes.io/cluster/` keys. |
| `api_allowed_cidrs` | `list(string)` | `[]` | IPv4 networks allowed to reach the endpoint besides the nodes. Empty: the VPC's primary CIDR for an internal endpoint. Required for a public one, and must then include the nodes' NAT gateway Elastic IPs. |
| `api_load_balancer_public` | `bool` | `false` | Make the load balancer internet-facing. |
| `api_load_balancer_subnets` | `map(string)` | `{}` | Zone to subnet ID for the load balancer; empty means `subnets`. Must cover every zone of `subnets`; required (public subnets) for a public endpoint. |
| `control_plane_instance_profile` | `object({ name = string, role_arn = string })` | `null` | An existing instance profile for control-plane nodes, with its role's ARN, instead of creating one. |
| `distribution` | `string` | `"kubeadm"` | `kubeadm` or `rke2`; `rke2` adds the supervisor listener on 9345. |
| `node_role_permissions_boundary` | `string` | `null` | Permissions boundary ARN for the roles the module creates; it must allow `s3:GetObject` on the bootstrap bucket. |
| `node_role_policy_arns` | `object({ control_plane = optional(list(string), []), worker = optional(list(string), []) })` | `{}` | Managed policies to attach to the roles the module creates, for example `AmazonEBSCSIDriverPolicy`. |
| `region` | `string` | `null` | The region; null uses `AWS_REGION` from the identity Secret. |
| `ssh_allowed_cidrs` | `list(string)` | `[]` | IPv4 networks allowed to reach the nodes on SSH; none by default. |
| `subnets` | `map(string)` | `null` | Required. Zone to node subnet ID, one subnet per zone; each zone is a failure domain. |
| `vpc_id` | `string` | `null` | Required. The VPC of the subnets. |
| `worker_instance_profile` | `object({ name = string, role_arn = string })` | `null` | An existing instance profile for workers, with its role's ARN; its role must differ from the control-plane one. |

## Outputs

| Output | Value |
| --- | --- |
| `control_plane_endpoint` | The load balancer's DNS name and `api_server_port`, or the input passed through |
| `failure_domains` | One per subnet zone, sorted, each eligible for the control plane, with the `subnet_id` attribute |
| `exports` | `captf.io/aws-cluster/v1`; see [AWS](README.md#exports) |
| `health` | See below |
| `api_load_balancer_id` (extra) | The load balancer's ARN |

## Health

| AWS state | Contract state | Reason |
| --- | --- | --- |
| The load balancer was deleted out of band (when the module owns the endpoint) | `terminated` | `LoadBalancerNotFound` |
| The bootstrap bucket was deleted out of band | `degraded` | `BootstrapBucketNotFound` |
| Both exist | `running`, healthy | none |

Target health is never consulted; see [Shared Behavior](../shared-behavior.md#health).

## Limitations

!!! danger "Service load balancers outlive the cluster"

    `Service` load balancers created by cloud-provider-aws are not deleted
    with the cluster; delete the `Service` objects first.

- The endpoint is fixed once the load balancer exists: the scheme, the port
  and the subnets present at creation cannot change. Removing a subnet
  added later replaces the load balancer, which only CAPTF's
  destructive-plan guard stops.
- Nodes accept all traffic from each other, so a worker can reach
  control-plane ports such as etcd.
- Any principal of the account with broad S3 read access, other than the
  worker role, can read the control-plane payloads.
- The node roles have fixed names derived from the cluster's namespace and
  name, so two management clusters cannot create the same cluster in one
  account.
- Nodes egress everywhere (`0.0.0.0/0`); restrict egress in the network you
  bring.

## Exceptions

None: the role follows the conventions as written.

## Example

```yaml title="terraformcluster.yaml"
apiVersion: infrastructure.cluster.x-k8s.io/v1alpha1
kind: TerraformCluster
metadata:
  name: demo
spec:
  source:
    image: ghcr.io/captf-io/aws-cluster:v0.1.0-opentofu
  identityRef:
    name: aws
  defaults:
    identityRef:
      name: aws
  variables:
    region: us-east-1
    vpc_id: vpc-0123456789abcdef0
    subnets:
      us-east-1a: subnet-0aaa0000000000001
      us-east-1b: subnet-0bbb0000000000002
      us-east-1c: subnet-0ccc0000000000003
```
