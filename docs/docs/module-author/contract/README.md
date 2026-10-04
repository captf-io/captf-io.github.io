---
description: "The interface between the CAPTF controller and the Terraform or OpenTofu modules it runs, by contract version."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "September 29, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-09-29"
authors:
  - "Steven Crothers"
icon: lucide/files
subtitle: "Contract versions in one table"
---

# Module Contract

The interface between the CAPTF controller and the Terraform/OpenTofu
modules it runs. A module targets exactly one contract version; the image
contract is in [Image Contract](../image-contract.md).

| Version | Status | Documents |
| --- | --- | --- |
| `v1alpha1` | Provisional: frozen for implementation, and may still change until the first real module has provisioned a cluster | [v1alpha1](v1alpha1/README.md) ([changelog](v1alpha1/CHANGELOG.md)) |
