---
description: "Change the CAPTF docs or website: set up a preview, edit or add a page, run the checks and open a pull request."
icon: lucide/git-pull-request
subtitle: "From preview to pull request"
---

# Contributing to the Docs

This page walks through a change to captf.io, from a local preview to a
pull request. The site's source is the
[captf-io/captf-io.github.io](https://github.com/captf-io/captf-io.github.io)
repository: the
documentation under `docs/docs/`, the blog under `docs/blog/` and the
landing page, all built together by [Zensical](https://zensical.org/). For
how to write a page, see [Writing Documentation](documentation.md); for
the landing page, blog, navigation and theme, see
[Updating the Website](website.md).

!!! info "Before you begin"

    - `git` and `make`.
    - [`uv`](https://docs.astral.sh/uv/). It installs the Python version and
      the pinned Zensical release the site needs on first use, so there is
      nothing else to install.
    - For the browser checks only: the Playwright Chromium headless shell
      (`uv run --with playwright playwright install chromium-headless-shell`).

## Layout

| Path | What it holds |
| --- | --- |
| `docs/docs/` | The documentation, one Markdown file per page, published under `/docs/` |
| `docs/blog/posts/` | Blog posts, published under `/blog/` |
| `docs/index.md` | The landing page's data (its copy is in `overrides/home.html`) |
| `docs/assets/` | Brand marks, the social card and the landing page's images |
| `zensical.toml` | Site configuration: the navigation, plugins, Markdown extensions, header and footer content |
| `overrides/` | Theme overrides: templates, stylesheets and scripts |
| `includes/abbreviations.md` | Acronyms that get a hover tooltip on every page |
| `tools/` | Generators and checks, described below |

## Preview the site

1. Clone your fork and change into it.
2. Start the preview server:

    ```sh
    make serve
    ```

    It builds the site, serves it at <http://127.0.0.1:8001/> and rebuilds
    when a page changes. To reach it from another machine, set `ADDR` to
    an address of yours, on the command line or in a `local.mk` file,
    which is not committed: `ADDR = <address>`.

3. Open the page you are changing.

!!! note "Restart after template or configuration changes"

    The preview rebuilds pages as you save them. A change to
    `zensical.toml` or to a template under `overrides/` needs the server
    stopped and started again.

## Edit a page

Find the page's file from its URL: `/docs/user-guide/drift/` is
`docs/docs/user-guide/drift.md`, and a section's own page
(`/docs/cloud-modules/`) is its `README.md`. Pages keep the paths they were
first published under even where the navigation groups them differently,
so the URL, not the tab, tells you where a file is.

Keep to the [house style](documentation.md). In particular, do not rename
a heading other pages link to: links point at the anchor its text makes.
Check for inbound links before renaming one:

```sh
grep -rn '#<anchor>' docs/
```

`<anchor>` is the heading in lowercase, with spaces as hyphens and
punctuation dropped.

The reference pages describe what the provider repository defines; see
[Reference pages](documentation.md#reference-pages) for keeping them in
step with it.

## Add a page

1. Create the Markdown file in the directory of the part of the docs it
   belongs to, such as `docs/docs/user-guide/`. Its tags come from that
   directory's `.meta.yml`.
2. Give it front matter with a `description:` and an H1, following
   [Page shape](documentation.md#page-shape).
3. Add it to the `nav` in `zensical.toml`, where readers will look for it.
   The entry's text is the page's title in the navigation.
4. Give it a sidebar icon and subtitle: add an entry to
   `tools/nav_meta.json`, then run:

    ```sh
    uv run python tools/apply_nav_meta.py --write
    ```

    It refuses to write if a page has no entry, an icon does not exist or
    a subtitle is longer than 34 characters.

5. List the page in `SKIP` in `tools/gen_redirects.py`. That script keeps
   the URLs of the first edition of the docs (`/docs/<page>.html`)
   working; a new page has no such URL.
6. Run `make gen` and `make build`.

Avoid moving or renaming a published page: its path is its URL, and every
link to it, inside the site and out, would break.

## Run the checks

| Command | What it does |
| --- | --- |
| `make build` | Builds the site in strict mode; any warning fails it, including a broken link or anchor and a missing snippet file |
| `CI=1 make build-pages` | The build CI publishes: page dates, post authors and the sitemap's `<lastmod>` from git. It rewrites front matter, so run `git checkout docs` after it |
| `make gen` | Rewrites the generated parts of `zensical.toml` and the redirect stubs; run it after adding, moving or re-describing a page or post, and commit what it changes |
| `uv run --with playwright python tools/layout_audit.py` | With `make serve` running: tables squeezed too narrow and font sizes, at desktop, laptop and phone widths |
| `uv run --with playwright python tools/mobile_audit.py <dir>` | With `make serve` running: the header, tab row and navigation drawer at 25 phone, tablet and desktop sizes, with a screenshot of each state in `<dir>` |
| `uv run python tools/check_resources.py --provider <path>` | Every field of every CAPTF kind is named on its page under `reference/resources/`; `<path>` is a provider repository checkout |

`make build` is the one to run on every change. Run the audits when a
change touches the navigation, a template or a stylesheet, or adds a wide
table. Both audits read the preview at <http://127.0.0.1:8001/>; set
`CAPTF_SITE` to another address if yours listens elsewhere.

## Send the change

1. Branch from `main` and make one logical change per commit.
2. Write the commit subject as `<subsystem>: <summary>`, imperative and
   about 50 characters, then a body, wrapped at about 72 columns, that says
   why. The subsystem is the part of the docs: `docs` for changes across
   sections or the site itself, or the section's directory, such as
   `user-guide`, `operator-guide`, `runbooks`, `concepts`,
   `cloud-modules`, `contract` or `reference`. Check `git log` for the
   names in use.
3. Push and open a pull request against `main`, filling in the template.

Open an issue before writing a change to the module contract pages, or to
any page that describes the API or the security model: such a change
starts in the provider repository. The project's
[CONTRIBUTING.md](https://github.com/captf-io/.github/blob/main/CONTRIBUTING.md)
covers licensing and conduct for every repository.

!!! related "See also"

    - [Writing Documentation](documentation.md) for the house style and the
      reference pages.
    - [Updating the Website](website.md) for the landing page, blog,
      navigation, header, footer and theme.
    - [Contributing](contributing.md) for changes to the provider itself.
