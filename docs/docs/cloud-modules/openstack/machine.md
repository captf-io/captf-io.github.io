---
description: "Look up what the OpenStack machine module creates, its inputs, outputs, health, lifecycle and limits, with an example."
git_creation_date_localized: "October 2, 2026"
git_revision_date_localized: "October 2, 2026"
git_creation_date_iso: "2026-10-02"
git_revision_date_iso: "2026-10-02"
authors:
  - "The CAPTF Authors"
icon: lucide/server
subtitle: "One Nova server"
---

# Machine

The `ghcr.io/captf-io/module-images/openstack-machine` image implements the
[machine role](../../module-author/contract/v1alpha1/machine.md) for a
`TerraformMachine` on OpenStack. It creates one Nova server on a Neutron
port of the cluster's subnet and boots it with the bootstrap payload; for a
control-plane machine it first adds the port's address to the cluster's API
pools. Everything about the cluster comes from `captf_cluster_outputs`, the
[cluster role's exports](README.md#exports).

The module's source is
[`captf-io/terraform-openstack-machine`](https://github.com/captf-io/terraform-openstack-machine),
published on the Terraform Registry as
[`captf-io/machine/openstack`](https://registry.terraform.io/modules/captf-io/machine/openstack).

!!! warning "Control-plane bootstrap data is readable from the metadata service"

    A control-plane payload holds the cluster's CA private keys and is
    delivered as Nova user data. OpenStack has no instance identity to stage
    it behind, so there is no `bootstrap_delivery`: anything that reaches the
    metadata service (169.254.169.254) on the node, and anyone who can read
    the server through the Nova API, can read it. A config drive does not
    turn the service off. Deny `169.254.169.254/32` to pods with a CNI
    NetworkPolicy, and limit who can read servers in the project. See
    [Bootstrap](#bootstrap).

## What it creates

| Resource | Purpose | When |
| --- | --- | --- |
| `openstack_networking_port_v2.node_port` | Port on the cluster subnet, with the security groups and allowed address pairs | Always |
| `openstack_lb_member_v2.api_members` | Membership in each API pool, removed by this machine's destroy | One per exported pool, on a control-plane machine |
| `openstack_compute_instance_v2.node_instance` | The Nova server, named `machine_name` | Always, after the port and the members |

The server waits for the pool members, so a control-plane machine is in the
API pools before it boots, as `kubeadm init` and RKE2 joins require (see
[Control-plane machines](../../module-author/contract/v1alpha1/machine.md#control-plane-machines)).
It reads the server's status for health, except while the server is in
`BUILD`.

## Inputs

Contract inputs used:

- `captf_contract` (validated), `captf_object` (the port name),
  `captf_tags`;
- `captf_cluster_outputs`: network, subnet, groups, server group, pools,
  zones and region, validated to schema `captf.io/openstack-cluster/v1` or
  `{}`;
- `machine_name`: the server name, member names, the `Hostname` address
  and the default zone pick;
- `bootstrap_data` and `bootstrap_format` (see [Bootstrap](#bootstrap));
- `failure_domain`: the server's availability zone, one of the cluster's;
- `kubernetes_version`: fills `{version}` and `{semver}` in `image_name`,
  without its `+rke2rN` suffix;
- `control_plane`: pool membership, the control-plane group and the server
  group.

`captf_cluster` is declared and unused.

User variables, set in the `TerraformMachineTemplate`'s
`spec.template.spec.variables`
([Module Variables](../../user-guide/variables.md); source:
[variables.tf](https://github.com/captf-io/terraform-openstack-machine/blob/main/variables.tf)):

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `additional_security_group_ids` | `list(string)` | `[]` | Extra Neutron security group UUIDs for the port |
| `additional_tags` | `map(string)` | `{}` | Extra tags, with the cluster role's rules: at most 44 entries; keys 1 to 255 characters of letters, digits, `-`, `_`, `:`, `.` and space, not starting with `captf.io:`; each `<key>=<value>` fits in 255 characters |
| `config_drive` | `bool` | `false` | Attach a config drive with the user data and metadata; it does not turn the metadata service off |
| `external_cluster_exports` | `any` | `null` | The exports of an externally managed `TerraformCluster`, schema `captf.io/openstack-cluster/v1` |
| `flavor_name` | `string` | `null` | **Required.** Nova flavor |
| `image_id` | `string` | `null` | Glance image UUID. Set exactly one of `image_id` and `image_name`; boot from volume needs `image_id` |
| `image_name` | `string` | `null` | Glance image name, resolved to an ID by the provider through Glance at create; must match exactly one image. `{version}` (`v1.31.4`) and `{semver}` (`1.31.4`) stand for `kubernetes_version` |
| `key_pair` | `string` | `null` | Nova key pair for SSH |
| `root_volume_size_gib` | `number` | `null` | Boot from a new Cinder volume of this size, deleted with the server; a whole number of GiB, at least 1; `null` boots from the flavor's disk |
| `root_volume_type` | `string` | `null` | Cinder volume type of the root volume |

## Outputs

| Output | Value |
| --- | --- |
| `provider_id` | `openstack:///<server-uuid>`, or `openstack://<region>/<server-uuid>` with the cluster's `provider_id_format = "regional"`; `null` once the server is gone |
| `addresses` | `InternalIP` for each fixed IP of the port, then `Hostname`, `machine_name` |
| `failure_domain` | The availability zone: the requested one, or the module's pick |
| `interruptible` | Always `false`: Nova has no spot servers |
| `health` | See below |
| `api_member_ids` | Not a contract output: Octavia member UUIDs keyed by pool, `{}` on a worker |
| `node_port_id` | Not a contract output: the Neutron port's UUID, `null` once it is gone |

`provider_id` is what the OpenStack cloud controller manager writes to the
Node: `makeInstanceID` in
[cloud-provider-openstack v1.34.1](https://github.com/kubernetes/cloud-provider-openstack/blob/v1.34.1/pkg/openstack/instances.go)
returns `openstack:///<id>`, or `openstack://<region>/<id>` when
`OS_CCM_REGIONAL=true`. The addresses mirror what it reports for a server
without floating IPs. Without a requested failure domain, the module picks
a zone from the sha256 of `machine_name`, the same way in every
repository.

## Health

From the server's Nova status, re-read on every refresh.

| Nova status | Contract state | Reason |
| --- | --- | --- |
| `ACTIVE`, `MIGRATING`, `PASSWORD` | `running`, healthy | none |
| `BUILD` | `pending` | `ServerBuilding` |
| `REBOOT`, `HARD_REBOOT` | `pending` | `ServerRebooting` |
| `REBUILD` | `pending` | `ServerRebuilding` |
| `RESIZE`, `VERIFY_RESIZE`, `REVERT_RESIZE` | `pending` | `ServerResizing` |
| `SHUTOFF` | `stopped` | `ServerShutOff` |
| `SUSPENDED` | `stopped` | `ServerSuspended` |
| `PAUSED` | `stopped` | `ServerPaused` |
| `SHELVED`, `SHELVED_OFFLOADED` | `stopped` | `ServerShelved` |
| `RESCUE`, `ERROR` | `degraded` | `ServerRescued`, `ServerError` |
| `SOFT_DELETED`, `DELETED` | `terminated` | `ServerDeleted` |
| deleted outside Terraform | `terminated` | `ServerNotFound` |
| `UNKNOWN`, anything else | `unknown` | `ServerStatusUnknown` |

Provider 3.4.0 reads only some of these. The server resource reads
`ACTIVE`, `BUILD`, `SHUTOFF`, `PAUSED`, `SHELVED`, `SHELVED_OFFLOADED`,
`MIGRATING` and `ERROR`; in any other status its refresh fails, and so does
every drift Job and destroy until the server leaves that status. The status
read is skipped while the server is in `BUILD`, where it would fail, so
health then comes from the server itself and a server stuck building can
still be destroyed.

## Lifecycle

Machines are immutable: the module applies once, then refreshes for health
and destroys on delete. Its inputs, `captf_cluster_outputs` included, are
pinned at the first apply, so a later change to the cluster's zones or
exports never reaches a running machine. Changes outside Terraform show up
in drift reports only:

- The server's image is ignored after creation, so a rotated or deleted
  image never shows as drift (the provider would rebuild the server in
  place).
- A deleted flavor shows as a planned replacement; a renamed or resized one
  as an in-place resize.
- On destroy, the server goes before its pool members; Cluster API has
  drained the node by then, and the load balancer's monitor takes the
  backend out.

## Bootstrap

- `bootstrap_data` goes to Nova as user data unchanged: valid base64 passes
  through as is, so gzipped cloud-config works, and state keeps only a SHA1
  of it. Gzipped Ignition fails a precondition.
- Nova accepts at most 65,535 bytes of base64 user data; a larger payload
  fails a precondition. Compress it (CAPRKE2 `gzipUserData`) if needed.
- **Who can read it.** OpenStack has no instance identity to fetch a staged
  payload with, so there is no `bootstrap_delivery`: the control-plane
  payload, with the cluster CA keys, sits in user data, and anything that
  reaches the metadata service (169.254.169.254) on the node can read it. A
  config drive does not turn the metadata service off. Deny
  169.254.169.254/32 to pods with a CNI `NetworkPolicy`. Cluster API
  Provider OpenStack has the same exposure.

## Limitations

!!! warning "Keep machine_name within 63 characters and DNS-safe"

    Nova derives the hostname from the server name, cut to 63
    characters. Keep `machine_name` within 63 characters and DNS-safe, or the
    Node name does not match the server and the cloud controller manager
    cannot find it.

- **No spot.** `interruptible` is always `false`.
- **Port security groups.** Keep the cloud controller manager's
  `manage-security-groups` off: groups it adds to the port show as drift.

## Exceptions

- The server is named `machine_name`, not the conventions' prefixed name,
  because the cloud controller manager finds servers by Node name.
- The boot-from-volume root volume carries no tags: Nova creates it from
  the block device mapping, which takes no metadata, and a separately
  created, tagged volume would need a Cinder availability zone named like
  the Nova one.
- Bootstrap payloads are readable from the metadata service (see
  [Bootstrap](#bootstrap)), a deviation from the contract's checklist.
- There is no `rejects_spot_control_plane` test: Nova has no spot servers.
- No capacity labels on the image: there is no default flavor to describe.

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
        image: ghcr.io/captf-io/module-images/openstack-machine:v0.1.0-opentofu
      variables:
        flavor_name: m1.large
        image_name: ubuntu-2404-kube-{version}
```
