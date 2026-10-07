#!/usr/bin/env python3
# Copyright 2026 The CAPTF Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Date every docs page from git, for the published build.

Zensical has no git-dates plugin: the theme's "Last update" line and the
structured data (overrides/main.html) read the git_* keys of a page's front
matter. tools/import_git_meta.py wrote them once, from the history of the
mdBook repo the pages came from, so on their own they stop at the move to
this repo. Before the published build, this brings them up to date from
this repo's history:

  git_creation_date_*   kept where the front matter has it (the page's
                        history goes back before this repo); otherwise the
                        page's first commit here
  git_revision_date_*   the later of the front matter's date and the last
                        commit here that changed the page's body

A commit counts only if it changed the body, below the front matter, so
sweeps over the metadata (bylines, titles) date nothing, and neither does
the commit that brought a page with history into this repo.

The new dates are written into the front matter of the working tree, which
CI builds from and throws away; they are never committed, because a commit
cannot carry its own date. So the tool refuses to write outside CI unless
given --force; `git checkout docs/docs` undoes a local run. It needs the
whole history (a checkout with fetch-depth: 0).

After the build, --sitemap adds each page's <lastmod> to the sitemap: the
article:modified_time the page itself declares, so the sitemap and the
page never disagree. Pages that declare none (the home page, blog
listings) get none.

Usage:
  git_dates.py --write [--force]   date the pages (CI, before the build)
  git_dates.py --sitemap FILE      add <lastmod> (CI, after the build)
  git_dates.py                     print the dates that would change
"""

import datetime
import os
import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "docs"
SITE_URL = "https://captf.io/"
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout


def body(text: str) -> str:
    return FRONT.sub("", text, count=1)


def history(rel: str) -> list[tuple[str, datetime.date, str]]:
    """The page's commits, newest first: (sha, author date, path then)."""
    out = git("log", "--follow", "--format=%x00%H %aI", "--name-only", "--", rel)
    commits = []
    for chunk in out.split("\0")[1:]:
        head, *names = [line for line in chunk.splitlines() if line]
        sha, when = head.split()
        commits.append((sha, datetime.date.fromisoformat(when[:10]), names[-1] if names else rel))
    return commits


def show(sha: str, path: str) -> str:
    return git("show", f"{sha}:{path}")


def localized(day: datetime.date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


def set_key(front: str, key: str, value: str) -> str:
    line = f'{key}: "{value}"'
    if re.search(rf"^{key}:", front, re.M):
        return re.sub(rf"^{key}:.*$", line, front, count=1, flags=re.M)
    return front + "\n" + line


def dates(path: Path) -> tuple[dict, dict] | None:
    """The page's current and git-derived dates, or None if not in git."""
    rel = path.relative_to(ROOT).as_posix()
    commits = history(rel)
    if not commits:
        return None
    match = FRONT.match(path.read_text())
    front = match.group(1) if match else ""
    old = dict(re.findall(r'^(git_(?:creation|revision)_date_iso): "?([\d-]+)"?$', front, re.M))
    imported = "git_revision_date_iso" in old
    edits = []
    for i, (sha, day, name) in enumerate(commits):
        older = commits[i + 1] if i + 1 < len(commits) else None
        if older is None:
            # The page's first commit here: an edit only if the page has no
            # history from before this repo.
            if not imported:
                edits.append(day)
            continue
        if body(show(sha, name)) != body(show(older[0], older[2])):
            edits.append(day)
    created = old.get("git_creation_date_iso") or commits[-1][1].isoformat()
    revised = max([d.isoformat() for d in edits] + ([old["git_revision_date_iso"]] if imported else []) + [created])
    return old, {"git_creation_date_iso": created, "git_revision_date_iso": revised}


def write(path: Path, new: dict) -> None:
    text = path.read_text()
    match = FRONT.match(text)
    front = match.group(1) if match else ""
    for kind in ("creation", "revision"):
        iso = new[f"git_{kind}_date_iso"]
        front = set_key(front, f"git_{kind}_date_localized", localized(datetime.date.fromisoformat(iso)))
        front = set_key(front, f"git_{kind}_date_iso", iso)
    front = front.lstrip("\n")
    rest = text[match.end():] if match else text
    path.write_text(f"---\n{front}\n---\n{rest}")


def sitemap(file: Path) -> int:
    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("", ns)
    tree = ET.parse(file)
    site = file.parent
    added = 0
    for url in tree.getroot().findall(f"{{{ns}}}url"):
        loc = url.find(f"{{{ns}}}loc").text
        page = site / loc.removeprefix(SITE_URL)
        page = page / "index.html" if loc.endswith("/") else page
        if not page.is_file() or url.find(f"{{{ns}}}lastmod") is not None:
            continue
        found = re.search(r'<meta property="?article:modified_time"? content="?([\d-]{10})', page.read_text())
        if found:
            ET.SubElement(url, f"{{{ns}}}lastmod").text = found.group(1)
            added += 1
    ET.indent(tree)
    tree.write(file, encoding="UTF-8", xml_declaration=True)
    print(f"{file}: <lastmod> on {added} URLs")
    return 0


def main(argv: list[str]) -> int:
    if "--sitemap" in argv:
        return sitemap(Path(argv[argv.index("--sitemap") + 1]))
    writing = "--write" in argv
    if writing and not os.environ.get("CI") and "--force" not in argv:
        print("git_dates.py --write rewrites front matter for the published build;"
              " it runs in CI. Use --force to run it here, then `git checkout docs/docs`.",
              file=sys.stderr)
        return 1
    if git("rev-parse", "--is-shallow-repository").strip() == "true":
        print("git_dates.py needs the whole history: check out with fetch-depth: 0.", file=sys.stderr)
        return 1
    changed = 0
    for path in sorted(DOCS.rglob("*.md")):
        found = dates(path)
        if not found:
            continue
        old, new = found
        if old == new:
            continue
        changed += 1
        if writing:
            write(path, new)
        else:
            print(f"{path.relative_to(DOCS)}: {old.get('git_revision_date_iso', '-')} -> {new['git_revision_date_iso']}"
                  + ("" if old.get("git_creation_date_iso") else f" (created {new['git_creation_date_iso']})"))
    print(f"{changed} pages {'dated' if writing else 'would change'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
