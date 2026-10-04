# captf.io

The website of [Cluster API Provider Terraform (CAPTF)](https://github.com/captf-io):
the landing page at <https://captf.io/>, the documentation at
<https://captf.io/docs/> and the blog at <https://captf.io/blog/>, built
together with [Zensical](https://zensical.org/) and published to GitHub
Pages on every push to `main`.

## Working on it

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
| `STYLE.md` | The house style for documentation pages |

The documentation's [Contributing to the Docs](https://captf.io/docs/developer-guide/docs-workflow/),
[Writing Documentation](https://captf.io/docs/developer-guide/documentation/) and
[Updating the Website](https://captf.io/docs/developer-guide/website/) pages
cover the workflow, the style and the site's moving parts. The
[organization's contributing guide](https://github.com/captf-io/.github/blob/main/CONTRIBUTING.md)
covers commits, pull requests and conduct.

## License

[Apache-2.0](LICENSE.md).
