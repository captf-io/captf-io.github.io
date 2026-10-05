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

"""Fix list nesting that CommonMark accepts but Python-Markdown does not.

The pages were forked from an mdBook (CommonMark) book, where a nested list
item, or a block inside a list item, only needs to start at the parent's
content column: 2 spaces under "- ", 3 under "1. ". Python-Markdown, which
MkDocs uses, needs 4 spaces per level; otherwise nested lists render flat,
code blocks fall out of their step, and numbered lists restart.

Only what Python-Markdown would misread is moved:

  - a nested item less than 4 columns right of its parent's marker moves to
    exactly 4 (and everything inside it moves with it);
  - a block that starts after a blank line inside an item (a paragraph, a
    code fence, a table) but sits left of the marker + 4 column moves to
    that column; a code fence's contents keep their indentation relative to
    the fence.

Lazy continuation lines of an item's first paragraph are left alone, since
Python-Markdown joins them at any indent. Front matter is skipped.

Usage: reindent_lists.py [--write] FILE...   (without --write: print a diff)
"""

import difflib
import re
import sys
from pathlib import Path

ITEM = re.compile(r"^( *)([-*+]|\d+[.)])( +)(?=\S)")
FENCE = re.compile(r"^( *)(```+|~~~+)")


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def shift(line: str, by: int) -> str:
    if not line.strip() or by == 0:
        return line
    if by > 0:
        return " " * by + line
    return line[min(-by, indent_of(line)):]


class Item:
    def __init__(self, marker: int, new_marker: int):
        self.marker = marker          # original marker column
        self.new_marker = new_marker  # marker column after the fix
        self.shift = new_marker - marker
        self.block_shift = self.shift  # shift for the block being emitted


def reindent(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    start = 0
    if lines and lines[0] == "---" and "---" in lines[1:]:
        end = lines.index("---", 1)
        out.extend(lines[: end + 1])
        start = end + 1

    stack: list[Item] = []
    fence = None  # (closing marker, shift) while inside a code fence
    prev_blank = True
    for line in lines[start:]:
        if fence is not None:
            out.append(shift(line, fence[1]))
            s = line.strip()
            if s.startswith(fence[0]) and s.strip(fence[0][0]) == "":
                fence = None
            prev_blank = False
            continue
        if not line.strip():
            out.append(line)
            prev_blank = True
            continue

        ind = indent_of(line)
        # Leave every item this line is not inside. A non-item line inside an
        # item's first paragraph (no blank line yet) is a lazy continuation.
        while stack and ind <= stack[-1].marker and (prev_blank or ITEM.match(line)):
            stack.pop()

        m = ITEM.match(line)
        if m:
            marker = len(m.group(1))
            if stack:
                parent = stack[-1]
                new_marker = max(marker + parent.shift, parent.new_marker + 4)
            else:
                new_marker = marker
            item = Item(marker, new_marker)
            stack.append(item)
            out.append(shift(line, item.shift))
            prev_blank = False
            continue

        fm = FENCE.match(line)
        if stack:
            item = stack[-1]
            if prev_blank or fm:
                # A new block inside the item: keep it at or right of the
                # item's content column (marker + 4).
                need = item.new_marker + 4 - (ind + item.shift)
                item.block_shift = item.shift + max(need, 0)
            by = item.block_shift
        else:
            by = 0
        if fm:
            # Track every fence, inside a list or not, so its contents are
            # never read as Markdown.
            fence = (fm.group(2), by)
        out.append(shift(line, by))
        prev_blank = False
    return "\n".join(out)


def main(argv: list[str]) -> int:
    write = "--write" in argv
    files = [a for a in argv if a != "--write"]
    changed = 0
    for f in files:
        p = Path(f)
        old = p.read_text()
        new = reindent(old)
        if new == old:
            continue
        changed += 1
        if write:
            p.write_text(new)
        else:
            sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f, f, n=1))
    print(f"{'rewrote' if write else 'would change'} {changed} of {len(files)} files", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
