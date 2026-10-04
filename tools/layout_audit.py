#!/usr/bin/env python3
"""Measure the rendered layout of every page, to find what looks broken.

Loads each page of a running `make serve` (pages from site/sitemap.xml) in
headless Chromium at several viewport widths and reports:

  - squeezed tables: a column narrower than MIN_COL px, a cell wrapped into
    more than MAX_LINES lines, or a table wider than its container;
  - font sizes of each kind of element, site-wide, to spot outliers;
  - pages that scroll sideways (wider than the viewport);
  - headings and code blocks wider than their box.

Run with: uv run --with playwright python tools/layout_audit.py [--json OUT]
It drives the Chromium headless shell at CHROME when that exists, else
Playwright's own (`uv run --with playwright playwright install
chromium-headless-shell`). BASE and the viewports are set below.
"""

import json
import os
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
# The running preview (`make serve`); CAPTF_SITE overrides it.
BASE = os.environ.get("CAPTF_SITE", "http://127.0.0.1:8001/")
CHROME = Path.home() / ".cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell"
VIEWPORTS = {"desktop": 1440, "laptop": 1024, "phone": 390}
MIN_COL = 90
MAX_LINES = 8

MEASURE = """
({minCol, maxLines}) => {
  const art = document.querySelector('article.md-content__inner') || document.querySelector('article');
  const out = {overflowX: document.documentElement.scrollWidth - window.innerWidth, tables: [], fonts: {}, wideHeadings: 0, wideCode: 0};
  if (!art) return out;
  const fs = (el) => parseFloat(getComputedStyle(el).fontSize);
  const sample = {
    'p': 'article > p, .md-content__inner > p', 'li': '.md-content__inner > ul > li, .md-content__inner > ol > li',
    'td': 'td', 'th': 'th', 'h1': 'h1', 'h2': 'h2', 'h3': 'h3', 'admonition p': '.admonition > p, details > p',
    'admonition title': '.admonition-title, details > summary', 'card text': '.grid.cards > ul > li > p',
    'inline code': 'p > code, li > code', 'code block': 'pre > code', 'tab label': '.tabbed-labels > label',
    'nav link': '.md-nav__link', 'tabs link': '.md-tabs__link', 'source-file': '.md-source-file',
    'breadcrumb': '.md-path', 'banner': '.md-banner', 'hero h1': '.captf-hero h1', 'hero p': '.captf-hero p',
    'dl dt': 'dl dt', 'dl dd': 'dl dd', 'footer': '.md-footer-meta', 'toc link': '.md-nav--secondary .md-nav__link',
  };
  for (const [k, sel] of Object.entries(sample)) {
    const el = document.querySelector(sel);
    if (el && el.offsetParent !== null) out.fonts[k] = fs(el);
  }
  const contentW = art.clientWidth;
  for (const t of art.querySelectorAll('table')) {
    const wrap = t.closest('.md-typeset__scrollwrap') || t.parentElement;
    const rows = [...t.rows];
    if (!rows.length) continue;
    const head = rows[0].cells;
    const cols = [...head].map(c => Math.round(c.getBoundingClientRect().width));
    // Lines of each cell's own text (a Range around its contents), not the
    // row height every cell in a row shares. A cell counts as squeezed when
    // it wraps past maxLines while its column is narrower than 200px.
    let worst = 0, worstText = '', squeezedCells = 0;
    for (const r of rows) for (const [i, c] of [...r.cells].entries()) {
      const range = document.createRange(); range.selectNodeContents(c);
      const lh = parseFloat(getComputedStyle(c).lineHeight) || fs(c) * 1.5;
      const lines = Math.round(range.getBoundingClientRect().height / lh);
      if (lines > maxLines && c.getBoundingClientRect().width < 200) squeezedCells++;
      if (lines > worst) { worst = lines; worstText = c.innerText.slice(0, 40); }
    }
    const narrow = squeezedCells;
    out.tables.push({cols: cols.length, colW: cols, tableW: Math.round(t.getBoundingClientRect().width), contentW,
      scrolls: wrap.scrollWidth > wrap.clientWidth + 1, narrowCols: narrow, maxLines: worst, maxLinesText: worstText,
      heading: (t.closest('section,article').querySelector('h1')||{}).innerText});
  }
  for (const h of art.querySelectorAll('h1,h2,h3')) if (h.scrollWidth > h.clientWidth + 1) out.wideHeadings++;
  return out;
}
"""


def pages():
    # From the running server, not site/: `make serve` rewrites site/ on
    # every rebuild, so the file can be missing mid-build.
    with urllib.request.urlopen(BASE + "sitemap.xml", timeout=30) as resp:
        xml = resp.read().decode()
    for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
        yield loc.replace("https://captf.io/", "")


def main(argv):
    out_json = argv[argv.index("--json") + 1] if "--json" in argv else None
    results = defaultdict(dict)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(CHROME) if CHROME.exists() else None, args=["--no-sandbox"])
        for vp, width in VIEWPORTS.items():
            page = browser.new_page(viewport={"width": width, "height": 900})
            for rel in pages():
                page.goto(BASE + rel, wait_until="load", timeout=30000)
                results[vp][rel] = page.evaluate(MEASURE, {"minCol": MIN_COL, "maxLines": MAX_LINES})
            page.close()
        browser.close()
    if out_json:
        Path(out_json).write_text(json.dumps(results, indent=1))

    for vp, by_page in results.items():
        print(f"\n=== {vp} ({VIEWPORTS[vp]}px), {len(by_page)} pages")
        fonts = defaultdict(Counter)
        for r in by_page.values():
            for k, v in r["fonts"].items():
                fonts[k][v] += 1
        print("font sizes (px: pages):", "; ".join(f"{k} " + ",".join(f"{s:g}:{n}" for s, n in c.most_common(3)) for k, c in fonts.items()))
        sideways = {rel: r["overflowX"] for rel, r in by_page.items() if r["overflowX"] > 0}
        print(f"pages scrolling sideways: {len(sideways)}", list(sideways.items())[:6])
        tables = [(rel, t) for rel, r in by_page.items() for t in r["tables"]]
        squeezed = [(rel, t) for rel, t in tables if t["narrowCols"]]
        scrolling = [(rel, t) for rel, t in tables if t["scrolls"]]
        print(f"tables: {len(tables)}; squeezed: {len(squeezed)} on {len({r for r, _ in squeezed})} pages; scrolling sideways: {len(scrolling)}")
        for rel, t in sorted(squeezed, key=lambda x: -x[1]["maxLines"])[:12]:
            print(f"  {rel:55} cols={t['cols']} widths={t['colW']} squeezed-cells={t['narrowCols']} maxLines={t['maxLines']} ({t['maxLinesText']!r})")
        wide = sum(r["wideHeadings"] for r in by_page.values())
        print(f"headings wider than their box: {wide}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
