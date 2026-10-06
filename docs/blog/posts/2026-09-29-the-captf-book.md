---
date: 2026-09-29
slug: the-captf-book
title: The CAPTF book is online
description: "The CAPTF documentation is published at captf.io/docs: a book organized by reader, from the quick start to runbooks and a reference checked against the source."
authors:
  - maintainers
categories:
  - Documentation
---

# The CAPTF book is online

The documentation for Cluster API Provider Terraform now has a home of its
own at [captf.io/docs](../../docs/index.md). It covers what CAPTF is and how
it works, how to run clusters with it, how to write a module for it, and how
to operate the manager, in about 160 pages organized by who is reading and
what they are trying to do.

[Open the book](../../docs/index.md){ .md-button .md-button--primary }
[Quick Start](../../docs/getting-started/quick-start.md){ .md-button }

<!-- more -->

*This post was expanded on October 6, 2026, to describe the book as it
stands now, including the pages added since launch.*

## Organized by reader

The book is split into tabs, one for each kind of reader, rather than one
long table of contents. Start with the tab that matches what you came to
do:

<div class="grid cards" markdown>

-   :material-compass-outline:{ .lg .middle } __Overview__

    ---

    What CAPTF is, the [Quick Start](../../docs/getting-started/quick-start.md)
    with the no-op modules and no cloud account, the
    [architecture](../../docs/concepts/architecture.md), and the pages to
    read before you adopt it: the security model, known limitations and
    compatibility.

-   :material-kubernetes:{ .lg .middle } __User Guide__

    ---

    Running clusters: [identities and credentials](../../docs/user-guide/identities.md),
    module variables, ClusterClass templates,
    [machine pools](../../docs/user-guide/machine-pools.md), drift and
    health, plan approval and deleting clusters.

-   :material-cloud-outline:{ .lg .middle } __Cloud Modules__

    ---

    The [reference modules](../../docs/cloud-modules/README.md) for AWS,
    Google Cloud, Azure, OCI and OpenStack, plus a no-op set: what each
    role creates, its variables and outputs, and the
    [behavior they share](../../docs/cloud-modules/shared-behavior.md).

-   :material-puzzle-outline:{ .lg .middle } __Module Authors__

    ---

    Writing your own: [your first module](../../docs/getting-started/first-module.md),
    the [`v1alpha1` contract](../../docs/module-author/contract/v1alpha1/README.md),
    base images, `tfcapi-lint`, testing, releasing, and integration with the
    kubeadm and RKE2 control planes.

-   :material-server-network:{ .lg .middle } __Operations__

    ---

    Running the manager: installation and configuration, RBAC and
    multi-tenancy, [production readiness](../../docs/operator-guide/production-readiness.md),
    observability, backup and [disaster recovery](../../docs/operator-guide/disaster-recovery.md).

-   :material-lifebuoy:{ .lg .middle } __Troubleshooting__

    ---

    [Runbooks by symptom](../../docs/operator-guide/runbooks/README.md),
    from failing Jobs to stale locks and stuck destroys, and a lookup of
    [every condition](../../docs/operator-guide/troubleshooting/conditions.md)
    with its likely cause and fix.

-   :material-cog-outline:{ .lg .middle } __How It Works__

    ---

    The controller's side of things: one
    [reconcile pass](../../docs/concepts/lifecycle.md),
    [Terraform state](../../docs/concepts/state.md) and the Secrets that
    hold it, and how Jobs are scheduled, retried and leased.

-   :material-book-open-variant:{ .lg .middle } __Reference__

    ---

    Every custom resource field, condition, event, alert, metric and
    manager flag, the `tfcapi-lint` checks, and a
    [map of the repositories](../../docs/reference/repositories.md) and
    images.

-   :material-source-pull:{ .lg .middle } __Contributing__

    ---

    Building and testing CAPTF itself, working across the repositories,
    [cutting a release](../../docs/developer-guide/releasing.md), and
    changing these docs.

</div>

## Added since launch

The book has grown with the project. Pages added since it went online:

| Page | What it covers |
| --- | --- |
| [Base Images](../../docs/module-author/base-images.md) | The OpenTofu and Terraform base images every module image builds from: tags, pinning, updates, signatures |
| [Building on Existing State](../../docs/module-author/existing-state.md) | Clusters on infrastructure and state you already have, exports, and add-on roots that run afterwards |
| [Repository Layout](../../docs/module-author/repository-layout.md) and [Repositories](../../docs/reference/repositories.md) | One module per repository, how `module-images` builds them, and a map of the whole organization |
| [Testing](../../docs/module-author/testing.md) and [Releasing](../../docs/module-author/releasing.md) a module | From format checks to end-to-end on kind, and from a signed tag to the Terraform Registry |
| [tfcapi-lint in CI](../../docs/module-author/tfcapi-lint-ci.md) | The GitHub Action and container image, pinning, private registries, troubleshooting |
| [Terraform vs OpenTofu Storage](../../docs/concepts/secret-management/runtimes.md) | Why Terraform state can grow past 1 MiB and OpenTofu state cannot |
| [The Cluster Autoscaler on pools](../../docs/user-guide/machine-pools.md#autoscale-with-the-kubernetes-cluster-autoscaler) | Which of its providers can drive a CAPTF pool, and how to set it up |

## Kept honest against the code

Documentation drifts the moment nobody checks it, so the book is checked:

- **The reference is checked against the provider's source.** The
  reference pages are written by hand, and two scripts that every edit to
  them runs read the provider repository and fail on any condition, event,
  alert, metric, flag, annotation or custom resource field it defines that
  the pages do not mention.
- **Every link and anchor resolves.** The site builds in strict mode, so a
  broken link or a heading anchor that no longer exists fails the build.
- **Old links still work.** The book started life as an mdBook; every one
  of its old `.html` URLs redirects to the page that replaced it, fragment
  included.

## Made for tools as well as people

- **For LLMs:** [`/llms.txt`](https://captf.io/llms.txt) indexes every page
  with its one-line description, `/llms-full.txt` holds the whole book, and
  every page has a Markdown copy. The copy button at the top of a page puts
  that Markdown on your clipboard.
- **For feed readers:** this blog is at
  [`/feed_rss_created.xml`](https://captf.io/feed_rss_created.xml) and
  `/feed_json_created.json`.
- **For skimmers:** acronyms such as CAPI and KCP explain themselves on
  hover, wide diagrams open full size, and search highlights its matches on the
  page it opens.

## Status

Every kind and the module contract are `v1alpha1` and pre-release: the
contract is frozen for implementation but may still change. Two end-to-end
suites run on a local kind cluster, one of them driving the no-op modules
through real Cluster API objects, but they are opt-in and not yet part of
CI, and nothing has been applied to a real cloud. The
[Known Limitations](../../docs/operator-guide/limitations.md) page lists
everything CAPTF does not do.

*Update, 2026-10-06: v0.1.0 and v0.1.1 have since been released; see
[CAPTF v0.1 is released](2026-10-06-captf-v0-1.md).*

## Help improve it

Every page has an edit button that opens its source on GitHub, in
[`captf-io/captf-io.github.io`](https://github.com/captf-io/captf-io.github.io).
`make serve` previews the site locally with live reload, and
[Contributing to the docs](../../docs/developer-guide/docs-workflow.md)
walks through a change from edit to pull request.
