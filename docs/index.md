---
title: CAPTF
description: "Cluster API Provider Terraform: turn the Terraform and OpenTofu modules you already trust into Kubernetes clusters, on any platform."
template: home.html
hide:
  - navigation
  - toc
# The drawer's list on this page (overrides/partials/nav.html): the landing
# sections, in page order, by the id of each section's heading in
# home.html. Subtitles at most 34 characters, as in the docs nav.
anchors:
  - { id: solves, title: "Why CAPTF", subtitle: "Providers can't always keep up", icon: lucide/lightbulb }
  - { id: how, title: "How It Works", subtitle: "Packaged, run and reconciled", icon: lucide/workflow }
  - { id: features, title: "Features", subtitle: "What you get out of the box", icon: lucide/sparkles }
  - { id: hood, title: "Under the Hood", subtitle: "Simple parts, stated plainly", icon: lucide/cog }
  - { id: moves, title: "Three Steps", subtitle: "From module to cluster", icon: lucide/footprints }
  - { id: faq, title: "FAQ", subtitle: "Questions you're probably asking", icon: lucide/circle-help }
  - { id: early, title: "Get Involved", subtitle: "Get in early", icon: lucide/rocket }
# The landing page (overrides/home.html). The page has no Markdown body; its
# copy is in the template, mirrored from the org profile in captf-io/.github.
# The feature grid is data, in display order. `icon` names a glyph in the
# template; the tile colour follows the column, purple to blue to yellow.
# `href` is a page of this site (or an external URL), `more` the link text.
# `body` may use <code>. Every claim here should be one the docs back up.
features:
  - title: Any platform
    href: docs/getting-started/first-module/
    more: Write your first module
    icon: globe
    body: >-
      Public cloud, private cloud, bare metal, even the box under your
      desk. Terraform and OpenTofu already know how to build on all of them,
      so CAPTF does too.
  - title: Zero Go
    href: docs/module-author/contract/v1alpha1/
    more: The module contract
    icon: module
    body: >-
      You don't write a controller. You bring the module; CAPTF runs it, reads
      what it outputs, and keeps your <code>Cluster</code>, <code>Machine</code>
      and <code>MachinePool</code> objects in line with it.
  - title: The whole Cluster API
    href: docs/module-author/control-planes/
    more: Control-plane integration
    icon: cluster
    body: >-
      CAPTF is built for all of it: clusters, machines and autoscaling machine
      pools, ClusterClass and <code>clusterctl move</code>, with integration
      guides for kubeadm and RKE2 control planes.
  - title: State that lives with the cluster
    href: docs/concepts/state/
    more: Terraform state
    icon: lock
    body: >-
      Your Terraform state sits in a Kubernetes Secret right next to the object
      it describes, with backup copies you can restore from. No bucket to
      create, no backend to wire up.
  - title: Drift, caught
    href: docs/concepts/drift-and-health/
    more: Drift and health
    icon: pulse
    body: >-
      CAPTF checks for drift on a schedule and listens to your module's own
      health outputs. When something's off, Cluster API's conditions and
      machine remediation hear about it, and so do you.
  - title: Guardrails built in
    href: docs/concepts/approvals/
    more: Approvals and gates
    icon: shield
    body: >-
      Cluster changes can wait for your approval before they're applied.
      Credentials only reach the namespaces you name, and Jobs run locked down,
      with privilege escalation turned away at admission.
  - title: Lint before you ship
    href: docs/module-author/tfcapi-lint/
    more: tfcapi-lint
    icon: checks
    body: >-
      Run <code>tfcapi-lint</code> and it checks your module and its image
      against the contract, so you find the problems long before a cluster
      does.
  - title: Operable on day one
    href: docs/operator-guide/runbooks/
    more: Runbooks
    icon: chart
    body: >-
      Prometheus metrics and alert rules ship with it, the conditions and
      events are documented, and there are runbooks for the bad days: failing
      Jobs, stuck destroys, stale locks and more.
  - title: A supply chain you can audit
    href: https://github.com/captf-io/terraform-base
    more: The base images
    icon: layers
    body: >-
      The OpenTofu and Terraform base images are multi-arch and rebuilt every
      week, and each one ships with an SBOM and provenance attestations, so you
      know exactly what you're running.
---
