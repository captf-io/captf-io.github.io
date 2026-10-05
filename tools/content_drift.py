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

"""Report text in the original mdBook pages that is missing from this site.

The pages in docs/docs/ were forked from ../docs/src and restyled
(admonitions, tabs, tables, cards, front matter), so a line diff is useless
for telling what the original has gained since. This compares words
instead: both versions are reduced to their words (Markdown, admonition and
tab markers, table pipes, front matter and HTML dropped), aligned, and every
run of words present in the original but absent here is reported, per page.

Words the restyling added here (admonition titles, card blurbs) don't count;
only text the original has and this site lacks. Run it after the original
book changes, integrate what it lists, and run it again: a clean result is
"no missing text".

With --base REV (a commit of ../docs, such as the fork point), gaps that
already existed between the original at REV and this site are left out:
those are the restyling's own rewrites, so what remains is text the
original gained after REV and this site has not taken in.

Usage: content_drift.py [--min N] [--base REV] [PAGE...]   (default: every
       page; N = the shortest run of missing words reported, default 3)
"""

import difflib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OURS = ROOT / "docs" / "docs"
SRC = ROOT.parent / "docs" / "src"

FRONT = re.compile(r"\A---\n.*?\n---\n", re.S)
FENCE_INFO = re.compile(r"^\s*(```+|~~~+)[^\n]*$", re.M)
# Admonition and tab openers: drop the marker and type, keep a quoted title
# (headings such as "Before you begin" became admonition titles).
MARKERS = re.compile(r'^\s*(?:!!!|\?\?\?\+?|===)\s*[a-z-]*\s*(?:"([^"]*)")?.*$', re.M)
HTML = re.compile(r"<[^>]+>")
INCLUDE = re.compile(r"\{\{#include\s+([^}]+)\}\}|--8<--\s+\"([^\"]+)\"")
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-/:]*")


def words(text: str) -> list[str]:
    text = FRONT.sub("", text)
    text = INCLUDE.sub(lambda m: " INCLUDE " + Path(m.group(1) or m.group(2)).name + " ", text)
    text = MARKERS.sub(lambda m: " " + (m.group(1) or "") + " ", text)
    text = FENCE_INFO.sub(" ", text)
    text = HTML.sub(" ", text)
    text = re.sub(r"\]\([^)]*\)", "]", text)  # link targets moved with the restructure
    return [w.lower().rstrip(".:,;") for w in WORD.findall(text)]


def page_pairs(selected: list[str]):
    for src in sorted(SRC.rglob("*.md")):
        rel = src.relative_to(SRC).as_posix()
        if rel == "SUMMARY.md":
            continue
        ours_rel = "index.md" if rel == "introduction.md" else rel
        if selected and rel not in selected and ours_rel not in selected:
            continue
        yield rel, src, OURS / ours_rel


def gaps(original: str, ours: str, min_run: int) -> list[str]:
    a, b = words(original), words(ours)
    out = []
    for op, i1, i2, _, _ in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op in ("delete", "replace") and i2 - i1 >= min_run:
            out.append(" ".join(a[i1:i2]))
    return out


def at(rev: str, rel: str) -> str:
    r = subprocess.run(["git", "show", f"{rev}:src/{rel}"], cwd=SRC.parent, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def main(argv: list[str]) -> int:
    min_run = int(argv[argv.index("--min") + 1]) if "--min" in argv else 3
    base = argv[argv.index("--base") + 1] if "--base" in argv else None
    selected = [a for a in argv if a.endswith(".md")]
    total = 0
    for rel, src, ours in page_pairs(selected):
        if not ours.exists():
            print(f"{rel}: MISSING PAGE (not in this site)")
            total += 1
            continue
        ours_text = ours.read_text()
        runs = gaps(src.read_text(), ours_text, min_run)
        if base and runs:
            old = gaps(at(base, rel), ours_text, min_run)
            old_words = set(" ".join(old).split())
            # Keep a gap only if it carries words the base-era gaps did not.
            runs = [r for r in runs if r not in old and not set(r.split()) <= old_words]
        if runs:
            total += 1
            missing = sum(len(r.split()) for r in runs)
            print(f"{rel}: {missing} words missing in {len(runs)} run(s)")
            for r in runs[:6]:
                print(f"    - {r[:220]}{'…' if len(r) > 220 else ''}")
    print(f"\n{total} page(s) with text missing from this site", file=sys.stderr)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
