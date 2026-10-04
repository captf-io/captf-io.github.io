---
date: 2026-10-02
slug: reference-cloud-modules
title: Reference modules for five clouds
description: "Reference module sets for AWS, Google Cloud, Azure, OCI and OpenStack: what each creates, and their pre-release status."
authors:
  - maintainers
categories:
  - Modules
---

# Reference modules for five clouds

The CAPTF project now maintains reference modules for five clouds: AWS,
Google Cloud, Azure, Oracle Cloud Infrastructure (OCI) and OpenStack. Each
set implements the `v1alpha1` module contract and ships as module images you
reference from a `TerraformCluster`, `TerraformMachineTemplate` or
`TerraformMachinePool`. Use them as they are, or fork them as the starting
point for your own.

<!-- more -->

## The sets

| Cloud | Repository | Roles |
| --- | --- | --- |
| [AWS](../../docs/cloud-modules/aws/README.md) | [`captf-io/aws-modules`](https://github.com/captf-io/aws-modules) | cluster, machine, machinepool |
| [Google Cloud](../../docs/cloud-modules/gcp/README.md) | [`captf-io/gcp-modules`](https://github.com/captf-io/gcp-modules) | cluster, machine, machinepool |
| [Azure](../../docs/cloud-modules/azure/README.md) | [`captf-io/azure-modules`](https://github.com/captf-io/azure-modules) | cluster, machine, machinepool |
| [OCI](../../docs/cloud-modules/oci/README.md) | [`captf-io/oci-modules`](https://github.com/captf-io/oci-modules) | cluster, machine, machinepool |
| [OpenStack](../../docs/cloud-modules/openstack/README.md) | [`captf-io/openstack-modules`](https://github.com/captf-io/openstack-modules) | cluster, machine |

All five follow one set of conventions, so they behave the same way wherever
the cloud allows it: an internal API endpoint by default, the same traffic
rules, node identities, bootstrap delivery and health outputs. The
[Shared Behavior](../../docs/cloud-modules/shared-behavior.md) page describes
them once; each cloud's pages describe only what differs.

## Status

The modules are pre-release. They pass static analysis, mocked unit tests on
Terraform and OpenTofu, and image smoke tests, but none has yet been applied
to a real cloud. Each repository's `DESIGN.md` lists the facts the first
real apply must confirm. Read it before you rely on a module, and pin a
release tag.

Start with the [Cloud Modules overview](../../docs/cloud-modules/README.md).
