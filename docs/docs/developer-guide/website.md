---
description: "Change captf.io beyond the docs pages: the landing page, blog posts, navigation and tabs, header, footer and banner, generated files and the theme."
icon: lucide/layout-template
subtitle: "Landing page, blog, nav and theme"
---

# Updating the Website

captf.io is one site, built from one source by [Zensical](https://zensical.org/):
the landing page at `/`, the documentation at `/docs/` and the blog at
`/blog/`. This page covers the parts that are not documentation pages: the
landing page, blog posts, the navigation, the header and footer, the
generated files, and the theme. For the change workflow and the checks, see
[Contributing to the Docs](docs-workflow.md).

The site has one look, dark only: there is no light theme or theme switch.

## The landing page

The landing page is `docs/index.md`, rendered by the `overrides/home.html`
template with `overrides/assets/stylesheets/landing.css` and
`overrides/assets/javascripts/landing.js`. The Markdown file has no body:

- the page's copy (hero, sections, questions) is in `home.html`. It is
  mirrored word for word from the organization profile in
  [captf-io/.github](https://github.com/captf-io/.github), so change the
  two together;
- the feature grid is data, in the `features:` list of `docs/index.md`'s
  front matter, in display order. Each entry has a `title`, a `body` (which
  may use `<code>`), an `href` (a page of this site, or an external URL),
  the link text `more`, and an `icon`, one of the line icons `home.html`
  defines: `globe`, `module`, `cluster`, `lock`, `pulse`, `shield`,
  `checks`, `chart`, `layers`, `link`, `inbox`, `scale`, `home`, `job`,
  `book`, `bolt`, `github`, `terraform`, `opentofu` or `kubernetes`;
- the `anchors:` list in the same front matter is what the navigation
  drawer shows on this page: one entry per landing section, with the `id`
  of the section's heading in `home.html`, a `title`, a `subtitle` and a
  Lucide `icon`. Add an entry when you add a section to `home.html`.

Every claim on the landing page must be one the documentation backs up.
The diagram and social card are `docs/assets/landing/how-it-works.svg` and
`og.jpg`, also shared with the organization profile.

## Blog posts

A post is a Markdown file in `docs/blog/posts/`, named
`<YYYY-MM-DD>-<slug>.md`:

```markdown title="docs/blog/posts/2026-10-02-reference-cloud-modules.md"
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

The opening paragraph, shown on the blog's index page.

<!-- more -->

The rest of the post.
```

- The post's URL is `/blog/<YYYY>/<MM>/<DD>/<slug>/`, from `date` and
  `slug`, so both are required, and neither changes once published.
- Everything above `<!-- more -->` is the excerpt on the index and in the
  feeds. The marker is required: the build fails without it.
- `authors` names entries in `docs/blog/.authors.yml`.
- Use one category, an existing one where it fits: `Documentation` or
  `Modules`. Each category gets its own index page.
- State only what the docs or the project's history back up, and link to
  the docs for detail rather than repeating it.

After adding or retitling a post, run `make gen`: the navigation drawer
lists the newest posts on blog pages from data it writes into
`zensical.toml`. The RSS and JSON feeds, the archive and the post's social
card are built automatically.

## Navigation and tabs

The `nav` in `zensical.toml` is the whole site's navigation. Its top-level
entries are the documentation's tabs, one per reader (see
[Where things go](documentation.md#where-things-go)), plus the blog. A
group without a page of its own shows as a heading; a group whose first
entry is a `README.md` opens on that page.

Each top-level section has an entry in `[project.extra.sections]`, keyed by
its title: a Lucide `icon`, a `subtitle` of at most 34 characters and, when
the title is long, a `short` label. The tab row and the drawer both use it,
so a section looks the same in each.

!!! warning "The tab row is full"

    Nine tabs with icons fill the tab row at the narrowest desktop width,
    and on smaller windows the row steps down to titles, then short labels,
    then icons. A tenth tab, or a longer section title, needs the row
    checked at every size: run `tools/mobile_audit.py`.

A page's own sidebar icon and subtitle come from `tools/nav_meta.json`; see
[Add a page](docs-workflow.md#add-a-page).

The navigation drawer, on windows narrower than the sidebar layout, follows
where the reader is: the docs sections on docs pages, the blog and its
recent posts on blog pages, and the landing page's sections on the home
page. Its top row switches between Home, Docs and Blog.

## Header, footer and banner

| Part | Where to change it |
| --- | --- |
| Site name | `site_name` in `zensical.toml`: the full name, for the browser title, link previews and feeds |
| Brand name | `extra.brand`: the short name in the header, the drawer and the footer |
| Home, Docs and Blog links | `overrides/partials/header.html` and, for the drawer, `overrides/partials/nav.html` |
| Footer columns, tagline, status | `[project.extra.footer]`; a link `href` without `://` is a page of this site |
| Social links | `[[project.extra.social]]` |
| Pre-release banner | The `announce` block in `overrides/main.html`; readers can dismiss it |
| Contract chip at the end of the tab row | `[project.extra.tabs]` |
| Hover tooltips for acronyms | `includes/abbreviations.md`, one `*[ABBR]: Expansion` line each |
| Logo and favicon | `docs/assets/brand/` |
| README components and their images | `includes/readme/` and `docs/assets/readme/`; see [README Components](readme-components.md) |

## Generated files

`make gen` rewrites three things. Never edit them by hand: the next run
overwrites the change.

| Generator | Writes | Reads |
| --- | --- | --- |
| `tools/gen_redirects.py` | A redirect page at each URL of the first edition of the docs (`/docs/<page>.html`), pointing at the page's current URL | Every page under `docs/docs/` not listed in its `SKIP` |
| `tools/gen_llms.py` | The `llms.txt` sections, between markers in `zensical.toml` | The `nav` and each page's `description:` |
| `tools/gen_blog_nav.py` | The recent posts for the drawer, between markers in `zensical.toml` | The posts' front matter |

Search, the RSS and JSON feeds, the sitemap, the social cards, `llms.txt`
itself and a Markdown copy of every page are built with the site.

## Page dates

A page's "Updated" date, its `dateModified` and `article:modified_time`,
and its `<lastmod>` in the sitemap all come from the `git_*_date_*` keys
of its front matter; Zensical has no git-dates plugin of its own. In the
repository those keys hold the dates of the page's history before this
repo, copied once by `tools/import_git_meta.py`. The published build,
`make build-pages`, brings them up to date first: `tools/git_dates.py`
sets each page's revision date to its last commit that changed the page
body, below the front matter, so a sweep over bylines or titles dates
nothing. It then builds the site and writes each page's date into the
sitemap.

The dates are written into the working tree that CI builds from and
discards, never committed, because a commit cannot carry its own date.
Plain `make build` shows the stored dates. To preview the published
dates, run `CI=1 make build-pages`, then `git checkout docs/docs`.

## The theme

The site uses Zensical's own theme, with templates under `overrides/`
replacing some of its parts:

| Override | What it changes |
| --- | --- |
| `main.html` | Page metadata (Open Graph, structured data, feeds), the browser title, the banner, the self-hosted fonts (`overrides/assets/fonts/`) and the deferred scripts |
| `home.html` | The landing page |
| `partials/header.html` | The header: brand, the Home, Docs and Blog links, search |
| `partials/tabs.html`, `partials/tabs-item.html` | The docs tab row, its icons and the contract chip |
| `partials/nav.html`, `partials/nav-item.html` | The sidebar and drawer: icons, subtitles, status badges, the drawer's switch and lists |
| `partials/footer.html` | The footer and the previous and next page links |
| `partials/source-file.html` | The page's dates and authors |
| `partials/comments.html` | The share links under blog posts |

The theme's look is changed in `overrides/assets/stylesheets/extra.css`,
in numbered sections with a comment on each saying what it is for. Colors
are variables at its top.

!!! warning "Overrides are copies"

    Each overridden template except `home.html` starts as a copy of the
    theme's own and names the Zensical version it was copied from. When the pinned Zensical version in
    `pyproject.toml` changes, compare each override with the new theme
    file and carry the theme's changes across.

Two rules keep the theme working across page changes:

- Clicking a link inside the site swaps the page's content without
  reloading, and the header stays. So anything in the header that depends
  on the page (which site link is active, for example) is set from a
  script on each page change (`overrides/assets/javascripts/sitenav.js`),
  and its links are absolute URLs. A part of the page is only swapped in
  if the page being left had it too, so such parts are rendered on every
  page, empty where unused.
- Do not put a `title` attribute on an element: the theme turns it into a
  tooltip that can stay on screen after a page change. Use `aria-label`.

Check a theme change with `make build`, then `tools/mobile_audit.py`,
clicking through from the home page as well as loading pages directly.

!!! related "See also"

    - [Contributing to the Docs](docs-workflow.md) for previewing, checking
      and sending a change.
    - [Writing Documentation](documentation.md) for the house style.
