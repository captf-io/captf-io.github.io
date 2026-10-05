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

"""Copy each page's git history facts from the original mdBook repo.

This experiment is not a git repo, but its pages were forked from
../docs/src, whose history is the real one. For every page here this reads
`git log --follow` of the matching source file and writes, into the page's
front matter:

  git_creation_date_localized   date of the first commit ("October 1, 2026")
  git_revision_date_localized   date of the last commit
  git_creation_date_iso         the same two dates as YYYY-MM-DD, for the
  git_revision_date_iso         structured data in overrides/main.html
  authors                       commit authors, in order of first commit

The theme shows the two dates under each page; overrides/partials/
source-file.html shows `authors`. The dates are those of the original
pages, not of the edits made here since the fork. Pages with no source
(such as tags.md) are left alone. Existing values are replaced. The docs
pages live in docs/docs/ (the site root is the landing page).

Usage: import_git_meta.py [--write]   (without --write: print a summary)
"""

import datetime
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "docs"
REPO = ROOT.parent / "docs"
SRC = "src"
KEYS = ("git_creation_date_localized", "git_revision_date_localized",
        "git_creation_date_iso", "git_revision_date_iso", "authors")


def source_of(rel: str) -> str:
    return f"{SRC}/introduction.md" if rel == "index.md" else f"{SRC}/{rel}"


def history(path: str) -> list[tuple[datetime.date, str]]:
    out = subprocess.run(
        ["git", "log", "--follow", "--format=%aI%x09%an", "--", path],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    entries = []
    for line in out.splitlines():
        when, name = line.split("\t", 1)
        entries.append((datetime.datetime.fromisoformat(when).date(), name))
    return entries  # newest first


def human(d: datetime.date) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def set_meta(text: str, meta: dict) -> str:
    end = text.index("\n---", 4)
    lines = [l for l in text[4:end].split("\n") if l.strip()]
    # Drop any previous values (including an indented list under a key).
    kept, skip = [], False
    for l in lines:
        if any(l.startswith(k + ":") for k in KEYS):
            skip = True
            continue
        if skip and l.startswith("  "):
            continue
        skip = False
        kept.append(l)
    kept.append(f'git_creation_date_localized: "{meta["created"]}"')
    kept.append(f'git_revision_date_localized: "{meta["updated"]}"')
    kept.append(f'git_creation_date_iso: "{meta["created_iso"]}"')
    kept.append(f'git_revision_date_iso: "{meta["updated_iso"]}"')
    kept.append("authors:")
    kept += [f"  - {yaml.safe_dump(a, default_style='\"').strip()}" for a in meta["authors"]]
    new = "---\n" + "\n".join(kept) + text[end:]
    yaml.safe_load(new[4:new.index("\n---", 4)])  # still valid
    return new


def main(argv: list[str]) -> int:
    write = "--write" in argv
    done = skipped = 0
    for page in sorted(DOCS.rglob("*.md")):
        rel = page.relative_to(DOCS).as_posix()
        log = history(source_of(rel))
        if not log:
            print(f"no history: {rel}")
            skipped += 1
            continue
        authors = []
        for _, name in reversed(log):
            if name not in authors:
                authors.append(name)
        meta = {"created": human(log[-1][0]), "updated": human(log[0][0]),
                "created_iso": log[-1][0].isoformat(), "updated_iso": log[0][0].isoformat(),
                "authors": authors}
        if write:
            page.write_text(set_meta(page.read_text(), meta))
        elif done < 5:
            print(f"{rel}: created {meta['created']}, updated {meta['updated']}, {len(log)} commits, authors {authors}")
        done += 1
    print(f"{'wrote' if write else 'would write'} {done} pages; {skipped} without history", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
