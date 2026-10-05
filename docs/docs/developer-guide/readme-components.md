---
description: "The header, badges, status note and footer that every captf-io README is composed from, the images they load from captf.io, and how to change them."
authors:
  - "The CAPTF Authors"
icon: lucide/puzzle
subtitle: "Header, badges, status, footer"
---

# README Components

Every captf-io repository's README is composed from the same four
components: a header, a badge row, a status note and a footer. They are
plain HTML and Markdown that you copy into a README and fill in. No tool
renders or syncs them, and no repository has its own images: the two
images the components load are served by this site from
`https://captf.io/assets/readme/`.

The components live in the website repository,
[captf-io/captf-io.github.io](https://github.com/captf-io/captf-io.github.io):
the sources in `includes/readme/`, which this page embeds, and the images in
`docs/assets/readme/`.

## The README layout

A README puts the components around its own content in this order:

```markdown
<header>

<badges>

<status note>

One paragraph: what this repository is and where it sits in CAPTF.

## Using it

## Developing

## Releasing

<footer>
```

The sections in the middle are the repository's own. Keep to these rules so
that the READMEs read the same:

- The header's `<h1>` is the title, so the README has no `# title` line.
- Name sections with gerunds where they fit: `Using it`, `Building…`,
  `Developing`, `Releasing`. Reference sections such as `Inputs` and
  `Outputs` keep their nouns.
- Style the body with plain Markdown only: tables, fenced code with a
  language, and GitHub alerts (`[!NOTE]`, `[!TIP]`, `[!WARNING]`). The
  components carry all of the brand's images, colour and HTML.
- No emoji, and no badges outside the badge row.
- Link to pages of other repositories and of this site with absolute URLs.
  A README that a registry also renders, such as a Terraform module's, uses
  absolute URLs for its own files too.
- Write prose in the docs' house style: plain, direct, present tense, with
  lines of at most 80 columns where the content allows.

## Placeholders

Each component is written for one repository. Replace these placeholders
when you paste it:

| Placeholder | Replace with | Example |
| --- | --- | --- |
| `REPO_NAME` | The repository's name in captf-io | `cluster-api-provider-terraform` |
| `TAGLINE` | One plain sentence, no full stop, at most 60 characters | `Run Terraform and OpenTofu modules as Cluster API providers` |
| `CI_WORKFLOW` | The file name of the workflow the build badge reports | `ci.yaml` |

The workflows that the build badges report:

| Repositories | `CI_WORKFLOW` |
| --- | --- |
| `cluster-api-provider-terraform` | `ci.yaml` |
| `opentofu-base`, `terraform-base` and `module-images` | `build.yml` |
| The `terraform-<provider>-<role>` module repositories | `ci.yml` |
| `captf-io.github.io` | `pages.yml` |
| `.github` | `checks.yml` |

## Header

The CAPTF mark, linked to the site, above the repository's name, and the
tagline under it. It is the first thing in the README.

```html title="includes/readme/header.md"
--8<-- "includes/readme/header.md"
```

## Badges

Build status, contract version, docs and license, under the header. Keep the
order, and leave out the build badge only for a repository with no workflow
on `main`. The shields
use the site's colours: `161B3A` for the label and the brand's purple, blue
and yellow for the values.

```html title="includes/readme/badges.md"
--8<-- "includes/readme/badges.md"
```

## Status note

The pre-release note, under the badges. Every repository carries it while
the API and the module contract are `v1alpha1`.

```markdown title="includes/readme/status.md"
--8<-- "includes/readme/status.md"
```

## Footer

A gradient divider, the mark, the site's main links and the license, as the
last thing in the README. It replaces a `## License` section.

```html title="includes/readme/footer.md"
--8<-- "includes/readme/footer.md"
```

## Images

The components load their images from this site, so a change to one of them
reaches every README once the site deploys.

| Image | URL | Used by |
| --- | --- | --- |
| The CAPTF mark on a dark tile | `https://captf.io/assets/readme/mark.svg` | Header (72 px) and footer (40 px) |
| The gradient divider | `https://captf.io/assets/readme/divider.svg` | Footer |

Keep the file names: every README links to them. The mark has a dark tile
of its own, unlike `docs/assets/brand/mark.svg`, so it reads on GitHub's
light and dark themes alike.

## Changing a component

1. Edit the file in `includes/readme/`. This page embeds it, so the docs
   change with it.
2. Apply the same change by hand to every README that carries the
   component. From a workspace with every repository checked out side by
   side, list them with:

    ```sh
    grep -l 'captf.io/assets/readme/mark.svg' */README.md .github/README.md .github/profile/README.md
    ```

3. Commit the website change first and let it deploy when the change adds
   or renames an image; then commit the README in each repository.

To add a repository, copy the four components into its README and fill in
the placeholders. There is nothing to register.

!!! related "See also"

    - [Working Across Repositories](cross-repo.md)
    - [Writing Documentation](documentation.md)
    - [Updating the Website](website.md)
