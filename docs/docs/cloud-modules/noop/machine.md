---
description: "The no-op machine role: the stand-in instance it records, the contract inputs it reads, its provider ID, address and image labels."
icon: lucide/server
subtitle: "A stand-in instance per Machine"
---

# Machine

The no-op machine module stands in for one instance per `Machine`. Its
image is `ghcr.io/captf-io/module-images/noop-machine`.

The module's source is
[`captf-io/terraform-noop-machine`](https://github.com/captf-io/terraform-noop-machine),
published on the Terraform Registry as
[`captf-io/machine/noop`](https://registry.terraform.io/modules/captf-io/machine/noop).

## What it creates

One `terraform_data` resource, `instance`, holding the inputs below. It
decodes `bootstrap_data` the way a module that passes a plain user-data
argument would, which shows the controller's base64 encoding round-trips;
the decoded value stays sensitive in the plan.

## Inputs

The module declares the contract inputs only; it has no variables of its
own, so `spec.variables` has nothing to set.

| Input | Use |
| --- | --- |
| `captf_contract` | Declared, as the contract requires |
| `captf_cluster`, `captf_object`, `captf_tags` | Recorded |
| `captf_cluster_outputs` | Its `backend_id` is recorded |
| `machine_name` | Names the provider ID |
| `bootstrap_data` | Decoded and recorded, as user data would be |
| `bootstrap_format`, `kubernetes_version`, `control_plane` | Recorded |
| `failure_domain` | Recorded and returned |

## Outputs

| Output | Value |
| --- | --- |
| `provider_id` | `noop:///<namespace>/<machine>`, stable per `Machine` |
| `addresses` | One `InternalIP`, `10.0.0.1` |
| `failure_domain` | The requested failure domain |
| `interruptible` | `false` |
| `health` | Always running and healthy |

No `Node` carries the provider ID, so the `Machine` never gets a
`nodeRef`. A real module returns the ID in the format its cloud controller
manager or kubelet sets.

## Image labels

The image carries the scale-from-zero labels a cluster autoscaler reads
through `TerraformMachineTemplate.status`: `io.captf.capacity`
(`{"cpu":"2","memory":"4Gi"}`) and `io.captf.node-info`
(`{"architecture":"<arch>","operatingSystem":"linux"}`, with the image's own
architecture). See
[OCI labels](../../module-author/image-contract.md#oci-labels).

## Health

The module always reports `running` and healthy.

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
        image: ghcr.io/captf-io/module-images/noop-machine:opentofu
```
