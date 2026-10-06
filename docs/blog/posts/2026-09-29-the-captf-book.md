---
date: 2026-09-29
slug: the-captf-book
title: The CAPTF book is online
description: "The CAPTF documentation is published at captf.io/docs: concepts, guides, the module contract, runbooks and generated reference."
authors:
  - maintainers
categories:
  - Documentation
---

# The CAPTF book is online

The documentation for Cluster API Provider Terraform now has a home of its
own at [captf.io/docs](../../docs/index.md). It covers what CAPTF is and how
it works, how to run clusters with it, how to write a module for it, and how
to operate the manager.

<!-- more -->

## What is in it

- **Getting started.** A [Quick Start](../../docs/getting-started/quick-start.md)
  that installs the provider and brings up a cluster with the no-op modules,
  on any Kubernetes cluster and with no cloud account, and a tutorial that
  takes you through [your first module](../../docs/getting-started/first-module.md).
- **Concepts.** The [architecture](../../docs/concepts/architecture.md), the
  kinds, Terraform state, secrets, approvals, jobs and deletion, each
  explained from the controller's side.
- **Guides.** How to provide credentials, pass module variables, use
  ClusterClass templates, run machine pools, and handle drift and plan
  approval.
- **The module contract.** The [`v1alpha1` contract](../../docs/module-author/contract/v1alpha1/README.md)
  every module is written to, with its changelog, and integration guides
  for the kubeadm and RKE2 control planes.
- **Operations and runbooks.** Installation, configuration, observability,
  upgrades and recovery, and [runbooks](../../docs/operator-guide/runbooks/README.md)
  for failing Jobs, stuck destroys, stale locks and more.
- **Reference.** The API, conditions, events, metrics, alerts and flags,
  generated from the provider's source so they stay in step with it.

## Status

Every kind and the module contract are `v1alpha1` and pre-release: the
contract is frozen for implementation but may still change. CAPTF has no
end-to-end tests yet. The [Known Limitations](../../docs/operator-guide/limitations.md)
page lists everything it does not do.

*Update, 2026-10-06: v0.1.0 and v0.1.1 have since been released, and
end-to-end suites now run on a kind cluster, including the no-op modules.
Nothing has been applied to a real cloud, and the project is still
pre-alpha.*
