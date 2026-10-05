---
description: "Build a workload cluster in an AWS VPC you bring: the images, prerequisites, identity Secret, quick start, API endpoint, exports and tags."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/cloud
subtitle: "NLB, EC2, Auto Scaling groups"
---

# AWS

The AWS modules build a workload cluster's infrastructure inside a VPC you
bring. The cluster role creates the API server's Network Load Balancer, the
security groups, IAM roles and instance profiles for the nodes, and an S3
bucket the nodes fetch their bootstrap data from. The machine role creates
one EC2 instance per `Machine`, and the machinepool role one Auto Scaling
group per `MachinePool`. The code lives in one repository per role:
[`terraform-aws-cluster`](https://github.com/captf-io/terraform-aws-cluster),
[`terraform-aws-machine`](https://github.com/captf-io/terraform-aws-machine) and
[`terraform-aws-machinepool`](https://github.com/captf-io/terraform-aws-machinepool),
published on the Terraform Registry as
[`captf-io/cluster/aws`](https://registry.terraform.io/modules/captf-io/cluster/aws),
[`captf-io/machine/aws`](https://registry.terraform.io/modules/captf-io/machine/aws) and
[`captf-io/machinepool/aws`](https://registry.terraform.io/modules/captf-io/machinepool/aws).
The images are built by
[`captf-io/module-images`](https://github.com/captf-io/module-images),
which pins a release of these modules for each image. Like
every set, these modules are pre-release; see the status note in
[Cloud Modules](../README.md).

<div class="grid cards" markdown>

-   :material-lan:{ .lg .middle } __Cluster__

    ---

    The API endpoint, security rules, node identities and exports of one workload cluster.

    [:octicons-arrow-right-24: Cluster](cluster.md)

-   :material-server:{ .lg .middle } __Machine__

    ---

    One instance per `Machine`, registered with the API load balancer.

    [:octicons-arrow-right-24: Machine](machine.md)

-   :material-server-network:{ .lg .middle } __MachinePool__

    ---

    One native scaling group per `MachinePool`.

    [:octicons-arrow-right-24: MachinePool](machinepool.md)

</div>

## Images

| Role | Image | Page |
| --- | --- | --- |
| cluster | `ghcr.io/captf-io/aws-cluster` | [Cluster](cluster.md) |
| machine | `ghcr.io/captf-io/aws-machine` | [Machine](machine.md) |
| machinepool | `ghcr.io/captf-io/aws-machinepool` | [MachinePool](machinepool.md) |

The images pin the `hashicorp/aws` provider at 6.67.0.

## Prerequisites

- **A VPC and one subnet per availability zone** for the nodes. Each zone
  becomes a failure domain. The subnets need a route to everything the nodes
  pull from: the internet through a NAT gateway, or VPC endpoints for S3,
  ECR, EC2 and STS plus a registry mirror. An internet-facing API endpoint
  needs public subnets of its own in the same zones. For `Service` load
  balancers, the cloud controller manager finds subnets by the
  `kubernetes.io/role/elb` and `kubernetes.io/role/internal-elb` tags,
  which you set.
- **Permissions for the identity.** The credentials create and delete
  everything the three roles manage. The cluster repository's
  [`examples/identity-policy.json`](https://github.com/captf-io/terraform-aws-cluster/blob/main/examples/identity-policy.json)
  covers all three roles; it scopes IAM changes to roles under `/captf/` and
  S3 to `captf-bootstrap-*` buckets. Its
  [README](https://github.com/captf-io/terraform-aws-cluster/blob/main/examples/README.md)
  explains what it lets the holder do and how to narrow it.
- **Node images.** cloud-init, the AWS CLI v2 on the `PATH` (for the staged
  bootstrap data), and the Kubernetes binaries for the version.
  [image-builder](https://github.com/kubernetes-sigs/image-builder)'s AWS
  images have all of it. Without an image ID the modules look up the newest
  [Cluster API Provider AWS image](https://cluster-api-aws.sigs.k8s.io/topics/images/amis.html)
  for the version, which that project builds for testing, not production.
- **In the workload cluster**:
  [cloud-provider-aws](https://github.com/kubernetes/cloud-provider-aws),
  the cloud controller manager that initializes the nodes and sets their
  provider IDs, and a CNI. For persistent volumes, the
  [Amazon EBS CSI driver](https://github.com/kubernetes-sigs/aws-ebs-csi-driver);
  the node roles carry no EBS permissions by default, so attach
  `AmazonEBSCSIDriverPolicy` with the cluster's `node_role_policy_arns`.

## Identity Secret

The provider block sets only the region; the AWS SDK's default chain reads
every credential from the identity's Secret, as environment variables or as
files under `/var/run/captf/credentials/`.

| Key | Purpose |
| --- | --- |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Static keys |
| `AWS_REGION` | The region, when the cluster's `region` variable is unset |
| `AWS_CONFIG_FILE`, `AWS_SHARED_CREDENTIALS_FILE`, `AWS_PROFILE` | A role to assume through shared config files |
| `config`, `credentials` | The shared config files themselves |

=== "Static keys"

    ```yaml title="identity.yaml"
    apiVersion: v1
    kind: Secret
    metadata:
      name: aws
      namespace: captf-system
    type: Opaque
    stringData:
      AWS_ACCESS_KEY_ID: REPLACE_WITH_ACCESS_KEY_ID
      AWS_SECRET_ACCESS_KEY: REPLACE_WITH_SECRET_ACCESS_KEY
      AWS_REGION: us-east-1
    ```

=== "Role to assume"

    A role to assume, which you should prefer over long-lived keys:

    ```yaml title="identity.yaml"
    apiVersion: v1
    kind: Secret
    metadata:
      name: aws-assume-role
      namespace: captf-system
    type: Opaque
    stringData:
      AWS_CONFIG_FILE: /var/run/captf/credentials/config
      AWS_SHARED_CREDENTIALS_FILE: /var/run/captf/credentials/credentials
      AWS_PROFILE: captf
      AWS_REGION: us-east-1
      config: |
        [profile captf]
        role_arn = arn:aws:iam::123456789012:role/captf-provisioner
        source_profile = base
        role_session_name = captf
      credentials: |
        [base]
        aws_access_key_id = REPLACE_WITH_ACCESS_KEY_ID
        aws_secret_access_key = REPLACE_WITH_SECRET_ACCESS_KEY
    ```

The Job's `HOME` is `/captf/work`, so `~/.aws` never exists and the paths
are explicit. IRSA and EKS Pod Identity do not apply: the Job mounts no
projected service account token. See
[Identities and Credentials](../../user-guide/identities.md) for the
`TerraformClusterIdentity` that names the Secret.

## Quick start

1. Create the identity. Edit the placeholder values in
   [`examples/identity.yaml`](https://github.com/captf-io/terraform-aws-cluster/blob/main/examples/identity.yaml),
   then apply it:

    ```sh
    export TERRAFORM_IDENTITY_NAME=aws NAMESPACE=team-a AWS_REGION=us-east-1
    clusterctl generate yaml --from examples/identity.yaml | kubectl apply -f -
    ```

2. Create the cluster from
   [`examples/cluster-kubeadm.yaml`](https://github.com/captf-io/terraform-aws-cluster/blob/main/examples/cluster-kubeadm.yaml):
   a `TerraformCluster`, a `KubeadmControlPlane`, a `MachineDeployment` and
   an autoscaled `MachinePool`. The only variables a cluster needs are the
   VPC and the zone-to-subnet map:

    ```sh
    export CLUSTER_NAME=demo KUBERNETES_VERSION=v1.34.1
    export CONTROL_PLANE_MACHINE_COUNT=3 WORKER_MACHINE_COUNT=2
    export AWS_VPC_ID=vpc-0123456789abcdef0
    export AWS_SUBNETS='{"us-east-1a": "subnet-0aaa0000000000001", "us-east-1b": "subnet-0bbb0000000000002", "us-east-1c": "subnet-0ccc0000000000003"}'
    clusterctl generate yaml --from examples/cluster-kubeadm.yaml | kubectl apply -n team-a -f -
    ```

3. Once the workload cluster's API server answers, install
   cloud-provider-aws and a CNI in it. The example's kubeadm configuration
   names each node after its private DNS name and sets its provider ID, as
   cloud-provider-aws expects.

## API endpoint

- **Internal by default.** The Network Load Balancer sits in the node
  subnets, or in `api_load_balancer_subnets`, which must cover every node
  zone: a Network Load Balancer sends no traffic to targets in a zone it
  is not in. An internal endpoint admits the VPC's primary CIDR unless you
  set `api_allowed_cidrs`; add the management cluster's network there when
  it is outside the VPC.
- **Public.** With `api_load_balancer_public = true` you must name public
  subnets in `api_load_balancer_subnets`, and `api_allowed_cidrs` must list
  the nodes' public egress addresses (the NAT gateways' Elastic IPs, as
  `/32`s) besides the clients: the endpoint's DNS name resolves to public
  addresses, so the nodes' own traffic arrives from those.
- **Hairpin.** The target groups turn client IP preservation off, because
  a Network Load Balancer does not hairpin a target's traffic back to
  itself while it preserves client IPs. The load balancer then connects to
  the control-plane nodes from its own addresses, which its security group
  stands for in the control-plane rules.
- **The endpoint guard** records the scheme
  (`api_load_balancer_public`), the port
  (`cluster_network.api_server_port`) and the load balancer's subnets.
  Subnets can be added later, in place; a subnet present at creation can
  never be removed. Removing a subnet added later is not caught by the
  guard and replaces the load balancer, which only CAPTF's
  [destructive-plan guard](../../concepts/approvals/destructive-guard.md)
  stops.

[Shared Behavior](../shared-behavior.md) covers the rest: your own
endpoint, the port, and RKE2's supervisor port.

## Exports

The cluster role's `exports` carry the schema `captf.io/aws-cluster/v1`.

| Key | Value |
| --- | --- |
| `schema` | `captf.io/aws-cluster/v1` |
| `region` | The region the provider resolved |
| `vpc_id` | The VPC |
| `kubernetes_cluster_id` | The cluster ID the cloud controller manager reads from the `kubernetes.io/cluster/<id>` tag |
| `failure_domains` | Zone name to `{ subnet_id }` |
| `security_group_ids` | `{ control_plane = [<control-plane group>, <node group>], worker = [<node group>] }` |
| `instance_profiles` | `{ control_plane = <name>, worker = <name> }` |
| `api` | `{ host, port, target_groups = { kube_apiserver = { arn, port }, rke2_supervisor = ... } }`: the endpoint and, per target group, the backend port to register; null with a user-supplied endpoint |
| `bootstrap_bucket` | The S3 bucket machines and pools stage bootstrap data in |

## Tags

AWS accepts the `captf.io/<key>` tag keys unchanged. Every taggable
resource carries `captf_tags` merged over `additional_tags`, so yours cannot
override them; `additional_tags` takes at most 40 tags, from the AWS tag
character set, and no `aws:`, `captf.io/` or `kubernetes.io/cluster/` keys.
Instances, their volumes, the node security group and the Auto Scaling
group also carry `kubernetes.io/cluster/<id> = owned`, which
cloud-provider-aws needs on exactly one security group per instance.

Cannot carry tags: `aws_iam_role_policy`, `aws_iam_role_policy_attachment`,
the bucket's public access block, encryption configuration and policy,
target group attachments, and scaling policies. S3 objects take at most 10
tags, so the bootstrap objects carry only `captf_tags`.

??? note "Design notes"

    - **Bootstrap data is staged in S3.** A pool's bootstrap data rotates about
      every 7.5 minutes, and each user-data change would add a launch template
      version, of which AWS allows 10,000: about 52 days. Staging also keeps
      the control-plane CA keys out of instance metadata.
    - **Workers cannot read control-plane payloads.** The bucket policy grants
      each node role its own key prefix and explicitly denies the worker role
      `control-plane/*`, whatever its own policies allow.
    - **The bucket policy grants the node roles, not inline role policies,** so
      brought instance profiles need no S3 permission of their own; their role
      ARNs are inputs, never read, so deleting them first never blocks a
      destroy.
    - **The AMI lookup returns nothing rather than failing** once an image is
      deregistered, so a refresh never fails on it; a precondition reports a
      missing image when one is needed.
    - **One security group carries the cluster tag.** cloud-provider-aws fails
      when an instance has two security groups tagged for the cluster, so the
      control-plane and load balancer groups go without it.
    - **Pools roll only on a version change**, by replacing the launch
      template, which starts a launch-before-terminate instance refresh; every
      other change adds a version under `$Latest` for new instances only.

Each role's `DESIGN.md` records the evidence and the alternatives rejected:
[cluster](https://github.com/captf-io/terraform-aws-cluster/blob/main/DESIGN.md),
[machine](https://github.com/captf-io/terraform-aws-machine/blob/main/DESIGN.md) and
[machinepool](https://github.com/captf-io/terraform-aws-machinepool/blob/main/DESIGN.md).

!!! warning "Not yet verified"

    - cloud-init merging the staged payload from `cloud.cfg.d` as system
      configuration on a real boot, and the AWS CLI v2 being on the AMIs used.
    - The kubelet merging `--node-labels` with your `kubeletExtraArgs`, and
      RKE2 appending `node-label+` labels.
    - Instance refresh rounding at 100 % and 200 % healthy for very small groups.
    - Deregistering a target whose instance is already terminated, at destroy.
    - `Service` load balancers left by the cloud controller manager blocking
      the node security group's deletion.
    - The Network Load Balancer's 350-second idle timeout with long
      `kubectl logs -f` sessions.
    - The NAT gateways' Elastic IPs being the source of node traffic to a
      public endpoint in every routing setup.
    - `examples/identity-policy.json` being complete for create, update and
      destroy of all three roles.
    - An Ignition 3.0.0 stub replacing itself with a config of a newer spec.
    - An Auto Scaling group launching Spot through the launch template's market
      options.
