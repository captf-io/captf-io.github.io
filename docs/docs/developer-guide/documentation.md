---
description: "How the CAPTF docs are organized and written: where pages go, reference pages, page shape, voice, Markdown patterns and the checks to run."
git_creation_date_localized: "September 29, 2026"
git_revision_date_localized: "September 29, 2026"
git_creation_date_iso: "2026-09-29"
git_revision_date_iso: "2026-09-29"
authors:
  - "Steven Crothers"
icon: lucide/pencil-line
subtitle: "Write and check these docs"
---

# Writing Documentation

This page is the house style for the CAPTF documentation, published at
[https://captf.io/docs/](https://captf.io/docs/). The site is built with
[Zensical](https://zensical.org/): the pages are Markdown under `docs/docs/`,
and `zensical.toml` holds the configuration and the navigation. Every page
follows this style, and the strict build enforces the parts a tool can
check.

To preview, check and send a change, see
[Contributing to the Docs](docs-workflow.md). For the landing page, blog
posts, navigation and theme, see [Updating the Website](website.md).

## Where things go

The documentation is split by reader, one navigation tab each. Pick the tab
by who reads the page, then the page type by what they need.

| Tab | Reader | Page types |
| --- | --- | --- |
| Overview | Anyone meeting CAPTF for the first time | The introduction, Quick Start, architecture, glossary and what to know before adopting |
| User Guide | People creating clusters with CAPTF | How-to: one task per page, in steps |
| Cloud Modules | People using the reference cloud modules | What each cloud's modules create and how to use them |
| Module Authors | People writing Terraform or OpenTofu modules for CAPTF | The normative contract, plus how-to pages |
| Operations | People installing and running the CAPTF manager | How-to pages and runbooks |
| Troubleshooting | Anyone with something not working | Diagnosis by symptom, then the fix |
| How It Works | Anyone who needs to understand how CAPTF works | Explanation: how and why, no step lists |
| Reference | Everyone | Every resource field by field, and lookups: conditions, events, alerts, metrics, flags, keys |
| Contributing | People changing CAPTF itself | How-to and conventions |

The navigation in `zensical.toml` decides where a page appears, not its
path: pages keep the paths they were first published under, so links and
anchors keep working.

Every fact lives on exactly one page.
Other pages link to it instead of restating it.
The page that owns a topic is the one whose title names it; when two pages
could own a fact, the more specific one does.

## Reference pages

Every page under `reference/` is written by hand: the
[custom resources](../reference/resources/README.md), field by field, and
the conditions, events, alerts, metrics, manager flags, Job environment,
the runner and `tfcapi-lint` command lines, annotations, labels and
finalizers, clusterctl variables and make targets. They explain each item
(what it means, its default, what to do about it), not only list it.

What they describe is defined in the provider repository
([cluster-api-provider-terraform](https://github.com/captf-io/cluster-api-provider-terraform)),
so a change there that adds, removes or renames one of these items needs
the page updated in the same change. Two checks catch a page that falls
behind; run them from this repository with a provider checkout:

- `tools/check_resources.py` reads the provider's CRDs and fails on any
  field of any kind that its page under `reference/resources/` does not
  name.
- `tools/check_reference.py` reads the provider's source (condition and
  event constants, alert rules, metric names, the commands' flags, the
  Job's environment, lint check IDs, `captf.io/` keys and finalizers,
  template variables and make targets) and fails on any name its page
  does not mention. Flags that come from libraries (logging, feature
  gates) are not in the provider's source, so it does not check those.

Both print each missing name. Neither can tell that a default or a meaning
changed, so read the provider change and check the page's wording too.

Other pages link to the reference pages for field lists, flags, reasons,
events, metrics and keys, and never copy those tables.

A few files are copies of provider files rather than pages: the contract
schemas under `module-author/contract/v1alpha1/schemas/`, the no-op
machine module under `getting-started/examples/noop/machine/` and the
Containerfiles under `module-author/examples/`. Refresh them from the
provider when its versions change.

## Page shape

- One H1, the page title, matching its entry in the `nav` of
  `zensical.toml`.
- Front matter with a `description:`: one sentence of at most 160
  characters saying what the reader gets from the page, always in double
  quotes. It feeds search results, link previews and `llms.txt`.
- An `icon:` (a Lucide icon, `lucide/<name>`) and a `subtitle:` (at most 34
  characters) for the sidebar. Set these in `tools/nav_meta.json` and run
  `tools/apply_nav_meta.py --write`, not in the page.
- A first paragraph that says what the page covers and who it is for.
- For how-to pages and runbooks: a "Before you begin" box of
  prerequisites, then numbered steps, then how to confirm it worked.
- A closing "See also" box when related pages exist.
- Headings in sentence case: "Rotate the credentials", not
  "Rotate The Credentials". Navigation entries use title case.
- Heading text stays stable once published, since links and alert
  `runbook_url`s point at the anchors derived from it.

A how-to page, start to finish:

````markdown title="docs/docs/user-guide/rotate-credentials.md"
---
description: "Rotate the cloud credentials a TerraformClusterIdentity points at, without touching the clusters that use it."
---

# Rotate Credentials

Replace the credentials behind an identity. For operators who manage the
credentials Secret.

!!! info "Before you begin"

    - `kubectl` access to the identity's namespace.

## Replace the Secret

1. Write the new credentials to the Secret:

    ```sh
    kubectl create secret generic <name> --from-file=<file> \
      --dry-run=client -o yaml | kubectl apply -f -
    ```

    `<name>` is the Secret the identity references, and `<file>` holds the
    new credentials.

## Confirm it worked

!!! success ""

    The next Job for each cluster that uses the identity succeeds.

!!! related "See also"

    - [Identities and Credentials](identities.md)
````

The title in the H1 is the page's name; its navigation entry in
`zensical.toml` uses the same words. The page's tags come from its
directory's `.meta.yml`, not from the page.

## Voice and wording

- Address the reader as "you". Use the present tense and the active voice.
- Say what happens, not what "should" happen. Reserve MUST, MUST NOT,
  SHOULD and MAY (RFC 2119, in capitals) for the normative module contract.
- American English: behavior, labeled, license, canceled.
- "CAPTF" is the project. Spell out "Cluster API Provider Terraform (CAPTF)"
  on the introduction page only.
- "Terraform or OpenTofu" in prose; `terraform` and `tofu` in code for the
  command-line tools. "OpenTofu" is always written with a capital O and T.
- Kinds use their exact names in code spans on first mention in a section:
  `TerraformCluster`, `TerraformMachine`, `TerraformMachinePool`, their
  `*Template` kinds, and `TerraformClusterIdentity`. In running prose,
  "machine pool" is fine.
- Expand an abbreviation on first use on each page: KubeadmControlPlane
  (KCP). Common ones (CAPI, KCP, RBAC and others in
  `includes/abbreviations.md`) also get a hover tooltip on every page.
- No references to source files, functions or line numbers on Overview,
  User Guide or Operations pages. Describe the behavior. Module Author and
  Contributing pages may name source files when the reader needs them.
- No `§` section references. Link to the heading instead.
- No dates, review notes, "TODO", "pending" or "planned" statements.
  State what is true now. If something does not exist yet, say that it does
  not exist.

## Markdown

- Wrap prose at 80 columns. Tables, code blocks and headings are exempt.
- Indent nested lists, and code blocks or paragraphs inside a list item,
  by 4 spaces: with 2 or 3, Python-Markdown renders them flat.
- Fence every code block with a language: `sh`, `yaml`, `hcl`, `json`,
  `text`, `promql` or `dockerfile`. Add `title="main.tf"` when the block is
  a whole file with a known name.
- Shell examples show commands only, without a `$` prompt, and use
  `<angle-bracket>` placeholders the reader replaces. Explain each
  placeholder below the block.
- Outside fenced code blocks, a placeholder always goes in a code span:
  `` `<namespace>` ``. A bare `<name>` in prose or a table cell is read as
  an HTML tag and disappears from the page.
- Tables use the compact style: `| a | b |` with a `| --- |` separator row.
- Link to other pages with relative links to the `.md` file, including the
  anchor when you mean a section:
  `[drift](../concepts/drift-and-health.md#drift)`. Relative links stay
  inside `docs/`.
- Link to files in the provider repository with a full
  `https://github.com/captf-io/cluster-api-provider-terraform/blob/main/...`
  URL.
- Include real files instead of pasting them, with a snippet line whose
  path is relative to `docs/docs/`:
  `--8<-- "module-author/examples/Containerfile.opentofu"` inside a fenced
  block.
- Boxes are admonitions: `!!! info "Before you begin"`, `!!! success ""`
  for the body of "Confirm it worked", `!!! related "See also"`, and
  `danger`, `warning`, `note`, `tip` or `example` for caveats, each with a
  title that states the point. Indent the body by 4 spaces. Never nest
  them or put two in a row.
- Show alternatives a reader picks one of (Terraform or OpenTofu, one YAML
  per kind) as content tabs, `=== "Label"`. Never tab steps a reader must
  do in sequence.
- Diagrams are Mermaid code blocks (a `mermaid` fence).

## Checks

From the root of the documentation's source:

| Command | Checks |
| --- | --- |
| `make build` | The site builds in strict mode: any warning fails it, including a broken link or anchor and a missing snippet file |
| `make gen` | Rewrites the generated parts of the configuration: the redirects from the original page URLs, the `llms.txt` sections and the recent posts; run it after adding, moving or describing a page or post |
| `tools/layout_audit.py` | Tables squeezed too narrow and font sizes, per window size |
| `tools/mobile_audit.py` | The header, tabs and navigation drawer at every phone and tablet size |
| `tools/check_resources.py` | Every field of every CAPTF kind is named on its page under `reference/resources/`; reads the CRDs from a provider checkout (`--provider <path>`) |
| `tools/check_reference.py` | Every condition, event, alert, metric, flag, variable, annotation, target and check in the provider's source is mentioned on its reference page; reads a provider checkout (`--provider <path>`) |

Both audits run against `make serve` with
`uv run --with playwright python tools/<audit>.py`.

The provider repository's code, messages and Markdown link to pages here
by `https://captf.io/docs/` URL, some with a heading's anchor. Nothing
checks those links from this side, so keep page paths and headings stable,
and search the provider for a page's URL before moving it.

Preview the site with `make serve`; it serves on <http://127.0.0.1:8001/>
with live reload. Set `ADDR` (on the command line, or in an uncommitted
`local.mk`) to listen on another address.
