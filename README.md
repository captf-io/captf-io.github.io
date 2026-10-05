<h1 align="center">
  <a href="https://captf.io/"><img
    src="https://captf.io/assets/readme/mark.svg"
    width="72" height="72" alt="CAPTF"></a>
  <br>
  captf-io.github.io
</h1>

<p align="center">The captf.io website, docs book and blog</p>

<p align="center">
  <a href="https://github.com/captf-io/captf-io.github.io/actions/workflows/pages.yml"><img
    src="https://img.shields.io/github/actions/workflow/status/captf-io/captf-io.github.io/pages.yml?branch=main&amp;label=build&amp;labelColor=161B3A&amp;style=flat-square"
    alt="build"></a>
  <a href="https://captf.io/docs/module-author/contract/index.html"><img
    src="https://img.shields.io/static/v1?label=contract&amp;message=v1alpha1&amp;color=A974FF&amp;labelColor=161B3A&amp;style=flat-square"
    alt="contract v1alpha1"></a>
  <a href="https://captf.io/docs/"><img
    src="https://img.shields.io/static/v1?label=docs&amp;message=captf.io&amp;color=5B8CFF&amp;labelColor=161B3A&amp;style=flat-square"
    alt="docs captf.io"></a>
  <a href="https://github.com/captf-io/captf-io.github.io/blob/main/LICENSE.md"><img
    src="https://img.shields.io/static/v1?label=license&amp;message=Apache-2.0&amp;color=FFD84D&amp;labelColor=161B3A&amp;style=flat-square"
    alt="license Apache-2.0"></a>
</p>

> [!NOTE]
> **Pre-release.** CAPTF is `v1alpha1`: its API and its
> [module contract](https://captf.io/docs/module-author/contract/index.html)
> may still change between releases.

The website of [Cluster API Provider Terraform (CAPTF)](https://github.com/captf-io):
the landing page at <https://captf.io/>, the documentation at
<https://captf.io/docs/> and the blog at <https://captf.io/blog/>, built
together with [Zensical](https://zensical.org/) and published to GitHub
Pages on every push to `main`.

## Developing

You need `make` and [`uv`](https://docs.astral.sh/uv/); `uv` installs the
Python version and the pinned Zensical release on first use.

```sh
make serve                  # preview at http://127.0.0.1:8001/, rebuilt on save
make build                  # the strict build CI runs: fails on any warning
make gen                    # after adding, moving or describing a page or post
make help                   # every target
```

| Path | What it holds |
| --- | --- |
| `docs/index.md` | The landing page's data (its copy is in `overrides/home.html`) |
| `docs/docs/` | The documentation, one Markdown file per page |
| `docs/blog/posts/` | Blog posts |
| `zensical.toml` | Configuration: navigation, plugins, header and footer content |
| `overrides/` | Theme overrides: templates, stylesheets and scripts |
| `tools/` | Generators and checks |
| [`STYLE.md`](STYLE.md) | The house style for documentation pages |

The documentation's [Contributing to the Docs](https://captf.io/docs/developer-guide/docs-workflow/),
[Writing Documentation](https://captf.io/docs/developer-guide/documentation/) and
[Updating the Website](https://captf.io/docs/developer-guide/website/) pages
cover the workflow, the style and the site's moving parts. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for commits, pull requests and conduct.

## Releasing

The `Pages` workflow (`.github/workflows/pages.yml`) checks that `make gen`
leaves the tree unchanged and runs `make build` on every pull request and
push. A push to `main` also publishes the built site to GitHub Pages.

<br>
<p align="center">
  <img
    src="https://captf.io/assets/readme/divider.svg"
    width="100%" height="4" alt="">
</p>
<p align="center">
  <a href="https://captf.io/"><img
    src="https://captf.io/assets/readme/mark.svg"
    width="40" height="40" alt="CAPTF"></a>
  <br>
  <a href="https://captf.io/docs/"
    ><b>Documentation</b></a> ·
  <a href="https://captf.io/docs/getting-started/quick-start.html"
    ><b>Quick start</b></a> ·
  <a href="https://github.com/captf-io/.github/blob/main/CONTRIBUTING.md"
    ><b>Contributing</b></a> ·
  <a href="https://github.com/captf-io/.github/blob/main/SECURITY.md"
    ><b>Security</b></a>
  <br>
  <sub>Built for
    <a href="https://cluster-api.sigs.k8s.io/">Cluster API</a>.
    <a href="https://github.com/captf-io/captf-io.github.io/blob/main/LICENSE.md"
    >Apache 2.0</a>.</sub>
</p>
