# Page style for the Zensical docs

This site is captf.io: the landing page at `/` (`docs/index.md`, rendered
by `overrides/home.html`), the documentation at `/docs/` (`docs/docs/`,
forked from the mdBook book in `../docs`) and the blog at `/blog/`
(`docs/blog/posts/`), built with Zensical (config: `zensical.toml`). This
file is the house style for the documentation pages.
Worked examples: `docs/docs/index.md` (a landing page) and
`docs/docs/user-guide/drift.md` (a how-to page). Read both before editing.

After adding, moving or re-describing a page, run `make gen`: it rewrites
the redirect stubs for the old mdBook URLs (`tools/gen_redirects.py`) and
the llms.txt sections (`tools/gen_llms.py`), which lists every page with
its `description:`. Blog posts need `date`, `slug`, `title`,
`description`, `authors: [maintainers]`, one category and a
`<!-- more -->` excerpt break, and must state only what the docs or the
project history back up.

## The rule

Change the presentation, not the content. Keep every fact, link, example
and caveat. Rewording is limited to what a pattern below needs, such as
moving a caveat into an admonition or giving it a title. Prose stays in the
house voice: plain, direct, present tense, no marketing, no exclamation
marks, no decorative emoji.

## Anchors

Over 800 links point at heading anchors (`page.md#some-heading`). Never
rename or remove a heading unless nothing links to its anchor. Check with
`grep -rn '#<slug>' docs/`, where the slug is the lowercase heading with
spaces as hyphens and punctuation dropped. The strict build reports any
broken anchor, so run it (see "Check your work").

Already checked: nothing links to `#before-you-begin`, `#see-also`,
`#not-yet-verified` or `#design-notes`, so those headings may become
admonitions. `#confirm-it-worked` and `#prerequisites` have inbound links:
keep those headings.

## Patterns

Indent the body of an admonition or tab by 4 spaces, including code blocks
and lists inside it. Leave a blank line after the `!!!` or `===` line.

**Front matter.** Give every page a `description:`, one sentence of at most
160 characters, saying what the reader gets from the page:

```yaml
---
description: "Set how often CAPTF checks for drift, whether it reports or remediates, and read the results."
---
```

Always double-quote the value. An unquoted description that contains
`": "` is invalid YAML, and the page's front matter then breaks silently.

**Sidebar icon and subtitle.** Every page also has an `icon:` (a Lucide
icon, `lucide/<name>`) and a `subtitle:` (at most 34 characters, no
final period, and not a restatement of the nav title) that the sidebar
shows. Don't edit these in the page: set them in `tools/nav_meta.json`
and run `tools/apply_nav_meta.py --write`, which checks every page has an
entry, every icon exists and every subtitle fits. Cluster, Machine and
MachinePool pages use `lucide/network`, `lucide/server` and
`lucide/boxes` throughout.

**Before you begin.** Replace the `## Before you begin` heading and its
list with:

```markdown
!!! info "Before you begin"

    - item
```

**Confirm it worked.** Keep the `## Confirm it worked` heading and put its
body in an untitled success box: `!!! success ""`.

**See also.** Replace the closing `## See also` heading and its list with
`!!! related "See also"` and the list indented under it. `related` is a
custom admonition (brand blue, link icon); use it only for this block.

**Caveats.** Pull a caveat buried in prose into an admonition when a reader
who skims would otherwise miss it. Give it a title that states the point
("Disabling drift checks also stops health sampling"), not just "Warning".

| Type | Use for |
| --- | --- |
| `danger` | Data loss, irreversible or destructive actions, orphaned cloud resources, security exposure. |
| `warning` | Surprising behavior, limits, things that fail or block. |
| `note` | A side fact that qualifies the text around it. |
| `tip` | A recommended practice or shortcut. |
| `example` | A worked example set apart from the explanation. |
| `info` | Prerequisites and context (also "Before you begin"). |
| `??? note "Title"` | Collapsed deep detail most readers skip. Use sparingly. |

Aim for about one admonition per 300 words at most. Never box a whole
section, never nest admonitions, and never put two in a row.

**Content tabs.** Use `=== "Label"` when a page shows the same thing in
alternatives a reader picks one of: Terraform or OpenTofu, one YAML per
kind, kubectl or clusterctl, one block per cloud. Never tab steps a reader
must do in sequence.

**Code blocks.**

- Give every fence a language: `sh`, `yaml`, `hcl`, `json`, `text`,
  `promql` or `dockerfile`.
- Add `title="main.tf"` when the block is a whole file with a known name.
- Use annotations (`# (1)!` in the code, then a numbered list after the
  block) to explain one or two specific lines. Don't annotate every line.
- Use `hl_lines="3 4"` to mark the line a long block is about.

**Lists.** Python-Markdown needs 4 spaces per nesting level: a nested
item 4 columns right of its parent's marker, and a code block or second
paragraph inside an item at the marker + 4 column. CommonMark's 2 or 3
spaces render flat, and a numbered list restarts after a code block that
falls out of its step. `tools/reindent_lists.py` fixes this (dry run
prints a diff; `--write` applies it).

**Diagrams.** The theme draws Mermaid inside a closed shadow root, so
page CSS cannot size it. The site's type size and spacing are set once,
in `overrides/assets/javascripts/mermaid.js`; don't add a `%%{init}%%`
line to a diagram. Each diagram sits in a panel and fits the column; one
the column shrinks gets an expand button that opens it full size. Keep
diagrams near the column's width (about 690px) so they read without it,
and vertical: use `flowchart TD`, never `LR` or `RL`. A horizontal flow
outgrows the column after three or four boxes, and a phone's column is
about 320px. Where a TD diagram still spreads sideways, give it fewer
side-by-side boxes: break long labels with `<br/>`, chain steps instead
of fanning them out, and stack groups with an invisible link (`A ~~~ B`).

**Wide tables.** A page built around tables of five or more columns with
sentence-length cells (inventories, reference lookups) hides the
right-hand table of contents with `hide: [toc]` in its front matter, so the
tables get about 930px instead of 690px at 1440px. Give such a page a
"Jump to" line instead if its outline matters. `tools/layout_audit.py`
lists tables that are still squeezed.

**Tables.** Turn a list into a table when it has three or more parallel
items with the same fields, such as status, reason and meaning, or flag,
default and effect.

**Section landing pages.** A `README.md` that opens a nav section gets
grid cards for its child pages, after the intro and in nav order. Use the
format in `docs/docs/index.md`:

```markdown
<div class="grid cards" markdown>

-   :material-icon-name:{ .lg .middle } __Page title__

    ---

    One line on what the page covers.

    [:octicons-arrow-right-24: Page title](child.md)

</div>
```

Pick icons from Material Design Icons (`:material-...:`) that fit the page.
If the README already lists or tables its children, replace that with the
cards only when nothing is lost.

**Reference pages** (`reference/`) are written by hand and describe what
the provider repository defines: every field, condition, event, alert,
metric, flag, variable, annotation, target and check. Keep every name exact,
in a code span, and keep the headings other pages link to. After editing one,
run `tools/check_resources.py` and `tools/check_reference.py`: they fail on
any name the provider defines that the page no longer mentions.

**Tooltips.** `includes/abbreviations.md` turns acronyms such as CAPI, KCP
and RBAC into hover tooltips on every page. Don't expand acronyms inline
just for that; suggest additions instead.

## Boundaries

Edit only the pages you are assigned. Don't edit `zensical.toml`,
`overrides/`, `includes/` or this file; report suggested changes to them
instead.

## Check your work

From the repository root:

```sh
make build                                         # strict: links, anchors
uv run --with playwright python tools/layout_audit.py   # needs `make serve`
```

Fix every warning that names one of your files. Other people edit other
pages at the same time, so ignore warnings about pages you don't own and
re-run. The audit lists squeezed tables and font sizes per viewport.
