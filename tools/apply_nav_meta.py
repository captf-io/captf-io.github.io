#!/usr/bin/env python3
"""Apply tools/nav_meta.json: the sidebar icon and subtitle of every page.

nav_meta.json maps each page (relative to docs/docs/) to {"icon",
"subtitle"}. This writes them as `icon:` and `subtitle:` front matter,
replacing any existing values and leaving every other key alone. It refuses
to write if a page has no entry, an icon file does not exist in the theme,
or a subtitle is longer than 34 characters (one sidebar line) or ends with
a period. Edit nav_meta.json, then re-run this, to change the sidebar.

Usage: apply_nav_meta.py [--write]   (without --write: check only)
"""

import json
import sys
from pathlib import Path

import yaml
import zensical

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "docs"
META = Path(__file__).with_name("nav_meta.json")
ICONS = Path(zensical.__file__).parent / "templates" / ".icons"
MAX = 34


def check(mapping: dict) -> list[str]:
    problems = []
    pages = {p.relative_to(DOCS).as_posix() for p in DOCS.rglob("*.md")}
    for rel in sorted(pages - set(mapping)):
        problems.append(f"no entry: {rel}")
    for rel, entry in mapping.items():
        if rel not in pages:
            problems.append(f"entry for a missing page: {rel}")
        if not (ICONS / f"{entry['icon']}.svg").is_file():
            problems.append(f"{rel}: no icon {entry['icon']}")
        sub = entry["subtitle"]
        if len(sub) > MAX or sub.endswith("."):
            problems.append(f"{rel}: subtitle {sub!r} ({len(sub)} chars)")
    return problems


def apply(path: Path, icon: str, subtitle: str) -> bool:
    text = path.read_text()
    end = text.index("\n---", 4)
    lines = text[4:end].split("\n")
    kept = [l for l in lines if not l.startswith(("icon:", "subtitle:"))]
    kept += [f"icon: {icon}", f"subtitle: {json.dumps(subtitle, ensure_ascii=False)}"]
    new = "---\n" + "\n".join(kept) + text[end:]
    yaml.safe_load(new[4:new.index("\n---", 4)])  # still valid YAML
    if new != text:
        path.write_text(new)
        return True
    return False


def main(argv: list[str]) -> int:
    mapping = json.loads(META.read_text())
    problems = check(mapping)
    if problems:
        print("\n".join(problems))
        return 1
    if "--write" not in argv:
        print(f"ok: {len(mapping)} entries")
        return 0
    changed = sum(apply(DOCS / rel, e["icon"], e["subtitle"]) for rel, e in mapping.items())
    print(f"applied {len(mapping)} entries; {changed} pages changed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
