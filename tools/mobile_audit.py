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

"""Test the site's navigation at every phone, tablet and breakpoint size.

For each viewport in VIEWPORTS (portrait and landscape phones, tablets, and
both sides of each layout breakpoint) and each page in PAGES (home, docs
index, a deep docs page, blog, a post) against a running `make serve`, it
records the header (overlaps, clipping, sideways scroll, the tab row's
stage and overflow, its height), then drives the drawer: opens it from the
menu button, checks its rows, closes it by the overlay and by Escape,
expands and collapses a section, uses the Home / Docs / Blog switch and
follows a page link. It also opens search and the floating table of
contents, and scrolls to exercise the auto-hiding header. A screenshot of
every state goes next to the results.

Usage (uv run --with playwright python tools/mobile_audit.py ...):
    mobile_audit.py OUTDIR            every viewport, 8 at a time, then check
    mobile_audit.py OUTDIR NAME       one viewport (NAME from VIEWPORTS)
    mobile_audit.py OUTDIR --check    check results already in OUTDIR

Writes OUTDIR/NAME.json and OUTDIR/NAME-<page>-<state>.png; the check
prints every failed expectation, or "all checks pass", and exits non-zero
on a failure. Like layout_audit.py, it drives the Chromium headless shell
at CHROME when that exists, else Playwright's own.
"""
import json
import os
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = Path.home() / ".cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell"
# The running preview (`make serve`); CAPTF_SITE overrides it.
BASE = os.environ.get("CAPTF_SITE", "http://127.0.0.1:8001/")
VIEWPORTS = {
    "p320": (320, 568, True), "p360": (360, 740, True), "p375": (375, 667, True), "p390": (390, 844, True), "p393": (393, 852, True), "c393": (393, 852, False),
    "p412": (412, 915, True), "p430": (430, 932, True),
    "l568": (568, 320, True), "l667": (667, 375, True), "l844": (844, 390, True), "l932": (932, 430, True),
    "t600": (600, 960, True), "t768": (768, 1024, True), "t820": (820, 1180, True), "t1024p": (1024, 1366, True),
    "t1024l": (1024, 768, True), "t1180l": (1180, 820, True),
    "b719": (719, 900, False), "b720": (720, 900, False), "b959": (959, 900, False), "b960": (960, 900, False),
    "b1219": (1219, 900, False), "b1220": (1220, 900, False), "d1440": (1440, 900, False),
}
PAGES = {
    "home": "", "docs": "docs/", "deep": "docs/user-guide/drift/",
    "blog": "blog/", "post": "blog/2026/10/02/reference-cloud-modules/",
}

HEADER = r"""() => {
  const vw = document.documentElement.clientWidth, vh = innerHeight;
  const box = e => { if (!e) return null; const s = getComputedStyle(e), r = e.getBoundingClientRect();
    if (s.display === 'none' || s.visibility === 'hidden' || r.width === 0 || r.height === 0) return null;
    return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), r: Math.round(r.right), b: Math.round(r.bottom)}; };
  const h = document.querySelector('.md-header');
  const parts = {
    logo: box(h.querySelector('.md-logo')), burger: box(h.querySelector('label[for=__drawer]')),
    title: box(h.querySelector('.md-header__title')), sitenav: box(h.querySelector('.captf-sitenav')),
    search: box(h.querySelector('label[for=__search]')), searchbar: box(h.querySelector('.md-search')),
  };
  const overlaps = [];
  const names = Object.keys(parts).filter(k => parts[k]);
  for (let i = 0; i < names.length; i++) for (let j = i + 1; j < names.length; j++) {
    const a = parts[names[i]], b = parts[names[j]];
    if (names[i] === 'search' && names[j] === 'searchbar' || names[i] === 'searchbar' || names[j] === 'searchbar') continue;
    const ix = Math.min(a.r, b.r) - Math.max(a.x, b.x), iy = Math.min(a.b, b.b) - Math.max(a.y, b.y);
    if (ix > 1 && iy > 1) overlaps.push(names[i] + '/' + names[j] + ':' + ix);
  }
  const offscreen = names.filter(k => parts[k].x < -1 || parts[k].r > vw + 1);
  const titleEl = h.querySelector('.md-header__title .md-ellipsis');
  const tabs = document.querySelector('.md-tabs'), list = tabs && tabs.querySelector('.md-tabs__list');
  let stage = null;
  if (box(tabs) && list && list.querySelector('.md-tabs__item')) {
    const it = list.querySelector('.md-tabs__item:not(.md-tabs__item--active)') || list.querySelector('.md-tabs__item');
    stage = [box(it.querySelector('svg')) ? 'icon' : '', box(it.querySelector('.md-tabs__label')) ? 'title' : '', box(it.querySelector('.md-tabs__short')) ? 'short' : ''].filter(Boolean).join('+');
  }
  const offenders = [];
  for (const e of document.body.querySelectorAll('*')) {
    const r = e.getBoundingClientRect();
    if (r.right <= vw + 1 || r.width === 0) continue;
    let p = e.parentElement, clipped = false;
    while (p && p !== document.body) { const o = getComputedStyle(p).overflowX; if (o !== 'visible') { clipped = true; break; } p = p.parentElement; }
    if (!clipped && getComputedStyle(e).position !== 'fixed') offenders.push((e.className && typeof e.className === 'string' ? e.tagName + '.' + e.className.split(' ')[0] : e.tagName) + '@' + Math.round(r.right));
    if (offenders.length > 6) break;
  }
  const banner = box(document.querySelector('.md-banner'));
  const toc = box(document.querySelector('.md-sidebar--secondary'));
  const top = document.querySelector('.md-top');
  return {
    vw, overflowX: document.documentElement.scrollWidth - vw, offenders,
    header: box(h), parts, overlaps, offscreen,
    titleText: titleEl ? titleEl.textContent.trim() : null, titleClipped: titleEl ? titleEl.scrollWidth > titleEl.clientWidth + 1 : null,
    tabs: box(tabs), tabStage: stage, tabOverflow: list ? list.scrollWidth - list.clientWidth : null,
    banner: banner ? banner.h : 0, tocBox: toc,
    topVisible: top ? (getComputedStyle(top).opacity !== '0' && !top.hidden && box(top) !== null) : null,
    h1: box(document.querySelector('.md-content h1, .captf-hero h1')),
  };
}"""

DRAWER = r"""() => {
  const vw = document.documentElement.clientWidth, vh = innerHeight;
  const box = e => { if (!e) return null; const s = getComputedStyle(e), r = e.getBoundingClientRect();
    if (s.display === 'none' || s.visibility === 'hidden' || r.width === 0 || r.height === 0) return null;
    return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), r: Math.round(r.right), b: Math.round(r.bottom)}; };
  const side = document.querySelector('.md-sidebar--primary');
  const nav = side.querySelector('.md-nav--primary');
  const title = nav.querySelector(':scope > .md-nav__title');
  const items = [...nav.querySelectorAll(':scope > .md-nav__list:not(.captf-drawer-posts) > .md-nav__item')].map(li => {
    const link = [...li.querySelectorAll(':scope > a.md-nav__link, :scope > label.md-nav__link, :scope > .md-nav__container > a.md-nav__link, :scope > .md-nav__container > label.md-nav__link')].find(e => box(e));
    if (!link) return {hidden: true, cls: li.className};
    const txt = [...link.querySelectorAll('.md-ellipsis')].map(e => e.childNodes[0] ? e.childNodes[0].textContent.trim() : '').join(' ') || link.innerText.split('\n')[0].trim();
    return {text: txt, tag: link.tagName, icon: !!link.querySelector(':scope svg:not(.md-nav__icon svg)') && !!box(link.querySelector('svg')),
      subtitle: !!box(link.querySelector('small')), chevron: !!box(li.querySelector(':scope > .md-nav__container .md-nav__icon, :scope > a .md-nav__icon, :scope > label .md-nav__icon, :scope > .md-nav__link .md-nav__icon')),
      h: box(link) ? box(link).h : 0, section: li.classList.contains('md-nav__item--section'), pruned: li.classList.contains('md-nav__item--pruned'), active: li.classList.contains('md-nav__item--active')};
  });
  const hrefs = [...nav.querySelectorAll('a[href]')].map(a => new URL(a.href).pathname);
  const scroller = side.querySelector('.md-sidebar__scrollwrap');
  return {
    open: document.getElementById('__drawer').checked, side: box(side), overlay: box(document.querySelector('.md-overlay')),
    title: title ? title.innerText.trim() : null, titleBox: box(title),
    items, hasHome: hrefs.includes(new URL(document.querySelector('[data-md-component=logo]').href).pathname),
    hasBlog: hrefs.some(h => /\/blog\/$/.test(h)), hasDocs: hrefs.some(h => /\/docs\/$/.test(h)),
    scroll: scroller ? {sh: scroller.scrollHeight, ch: scroller.clientHeight} : null,
    scrollbar: scroller ? scroller.offsetWidth - scroller.clientWidth : 0,
    headings: [...nav.querySelectorAll('.captf-drawer-heading')].filter(e => box(e)).map(e => e.textContent.trim()),
    anchors: nav.querySelectorAll('.captf-drawer-anchors a').length,
    posts: nav.querySelectorAll('.captf-drawer-posts a').length,
    bodyScrollLocked: getComputedStyle(document.body).overflow === 'hidden' || getComputedStyle(document.documentElement).overflow === 'hidden',
  };
}"""


def run(out: Path, name: str) -> dict:
    w, h, mobile = VIEWPORTS[name]
    res = {"viewport": name, "w": w, "h": h, "pages": {}}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROME) if CHROME.exists() else None)
        ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, device_scale_factor=1)
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        shot = lambda page, state: pg.screenshot(path=str(out / f"{name}-{page}-{state}.png"))
        for key, path in PAGES.items():
            r = {}
            try:
                pg.goto(BASE + path, wait_until="networkidle")
                pg.wait_for_timeout(250)
                r["closed"] = pg.evaluate(HEADER)
                shot(key, "closed")
                burger = pg.locator(".md-header label[for=__drawer]")
                if burger.is_visible():
                    burger.click()
                    pg.wait_for_timeout(450)
                    r["drawer"] = pg.evaluate(DRAWER)
                    shot(key, "drawer")
                    # Scroll the drawer to its end.
                    pg.evaluate("() => { const s = document.querySelector('.md-sidebar--primary .md-sidebar__scrollwrap'); if (s) s.scrollTop = s.scrollHeight; }")
                    pg.wait_for_timeout(150)
                    shot(key, "drawer-end")
                    pg.evaluate("() => { const s = document.querySelector('.md-sidebar--primary .md-sidebar__scrollwrap'); if (s) s.scrollTop = 0; }")
                    r["drawer"]["htmlOverflow"] = pg.evaluate("() => getComputedStyle(document.documentElement).overflow")
                    cw = pg.evaluate("() => document.documentElement.clientWidth")
                    # Close by tapping the overlay, right of the drawer.
                    side = r["drawer"]["side"]
                    if side and side["r"] < cw - 20:
                        pg.mouse.click(cw - 40, h // 2)
                        pg.wait_for_timeout(400)
                        r["overlayCloses"] = not pg.evaluate("() => document.getElementById('__drawer').checked")
                    else:
                        r["overlayCloses"] = "no overlay area"
                    # The close button (the only way out of a full-window drawer).
                    if not pg.evaluate("() => document.getElementById('__drawer').checked"):
                        burger.click(); pg.wait_for_timeout(450)
                    x = pg.locator(".md-sidebar--primary .captf-drawer-close")
                    r["closeButton"] = x.is_visible()
                    if r["closeButton"]:
                        x.click(); pg.wait_for_timeout(400)
                        r["closeButton"] = not pg.evaluate("() => document.getElementById('__drawer').checked")
                    # Escape.
                    if pg.evaluate("() => document.getElementById('__drawer').checked"):
                        pg.evaluate("() => { const d = document.getElementById('__drawer'); d.checked = false; d.dispatchEvent(new Event('change')); }")
                        pg.wait_for_timeout(300)
                    burger.click(); pg.wait_for_timeout(400)
                    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
                    r["escapeCloses"] = not pg.evaluate("() => document.getElementById('__drawer').checked")
                    if not r["escapeCloses"]:
                        pg.evaluate("() => { const d = document.getElementById('__drawer'); d.checked = false; d.dispatchEvent(new Event('change')); }")
                        pg.wait_for_timeout(300)
                    # Expand a collapsed top-level section, then collapse it again.
                    burger.click(); pg.wait_for_timeout(450)
                    before = pg.url
                    items = pg.locator(".md-sidebar--primary .md-nav--primary > .md-nav__list > li.md-nav__item--nested:not(.md-nav__item--active)")
                    if items.count():
                        li = items.nth(1 if items.count() > 1 else 0)
                        toggle = li.locator(":scope > label.md-nav__link, :scope > .md-nav__container > label.md-nav__link").first
                        tname = li.locator(".md-ellipsis").first.inner_text().split("\n")[0].strip()
                        toggle.click(); pg.wait_for_timeout(600)
                        opened = li.evaluate("e => ({checked: e.querySelector(':scope > input').checked, kids: [...e.querySelectorAll(':scope > nav > ul > li')].filter(k => k.getBoundingClientRect().height > 0).length})")
                        shot(key, "expand")
                        toggle.click(); pg.wait_for_timeout(600)
                        closed = li.evaluate("e => ({checked: e.querySelector(':scope > input').checked, kids: [...e.querySelectorAll(':scope > nav > ul > li')].filter(k => k.getBoundingClientRect().height > 0).length})")
                        r["drill"] = {"item": tname, "navigated": pg.url != before, "opened": opened, "closed": closed,
                                      "drawerOpen": pg.evaluate("() => document.getElementById('__drawer').checked")}
                    # Site switch: Blog (or Docs from the blog).
                    target = "Docs" if key in ("blog", "post") else "Blog"
                    sw = pg.locator(f".captf-drawer-sites a:has-text('{target}')")
                    if sw.count() and sw.first.is_visible():
                        sw.first.click(); pg.wait_for_timeout(1500)
                        r["switch"] = {"to": target, "url": pg.url.replace(BASE, "/"),
                                       "drawerOpen": pg.evaluate("() => document.getElementById('__drawer').checked"),
                                       "active": pg.evaluate("() => [...document.querySelectorAll('.captf-drawer-sites .captf-sitenav__link--active')].map(a => a.textContent.trim())")}
                    else:
                        r["switch"] = "missing"
                    if pg.url != BASE + path:
                        pg.goto(BASE + path, wait_until="networkidle"); pg.wait_for_timeout(250)
                    # Follow a leaf link in the drawer: does it navigate and close?
                    if not pg.evaluate("() => document.getElementById('__drawer').checked"):
                        burger.click(); pg.wait_for_timeout(450)
                    leaf = pg.locator(".md-sidebar--primary .md-nav__item--active a.md-nav__link:not(.md-nav__link--active):visible, .md-sidebar--primary li:not(.md-nav__item--nested) > a.md-nav__link:not(.md-nav__link--active):visible").first
                    if leaf.count():
                        lname = leaf.inner_text().split("\n")[0].strip()
                        leaf.click(); pg.wait_for_timeout(1500)
                        r["leaf"] = {"item": lname, "url": pg.url.replace(BASE, "/"),
                                     "drawerOpen": pg.evaluate("() => document.getElementById('__drawer').checked"),
                                     "after": pg.evaluate(HEADER)}
                        shot(key, "leaf")
                    pg.goto(BASE + path, wait_until="networkidle"); pg.wait_for_timeout(250)
                # Search: open, type, screenshot, Escape (verified by hand to work).
                s = pg.locator(".md-header label[for=__search]")
                if s.is_visible():
                    s.click(); pg.wait_for_timeout(500)
                    pg.keyboard.type("drift"); pg.wait_for_timeout(1000)
                    shot(key, "search")
                    pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
                # TOC floating button (narrow docs pages).
                toc = r["closed"].get("tocBox")
                if toc and toc["w"] < 80:
                    pg.mouse.click(toc["x"] + toc["w"] / 2, toc["y"] + toc["h"] / 2); pg.wait_for_timeout(500)
                    r["toc"] = pg.evaluate(r"""() => { const n = document.querySelector('.md-sidebar--secondary .md-nav--secondary'); const rb = n ? n.getBoundingClientRect() : null;
                        return {box: rb ? [Math.round(rb.x), Math.round(rb.y), Math.round(rb.width), Math.round(rb.height)] : null,
                                links: [...document.querySelectorAll('.md-sidebar--secondary a.md-nav__link')].filter(a => a.getBoundingClientRect().height > 0).length}; }""")
                    shot(key, "toc")
                    pg.goto(BASE + path, wait_until="networkidle"); pg.wait_for_timeout(250)
                # Autohide: scroll down, then a little up.
                for _ in range(6):
                    pg.mouse.wheel(0, 300); pg.wait_for_timeout(200)
                pg.wait_for_timeout(500)
                r["scrolledDown"] = pg.evaluate(HEADER)
                shot(key, "scrolled")
                pg.mouse.wheel(0, -300); pg.wait_for_timeout(700)
                r["scrolledUp"] = pg.evaluate(HEADER)
                shot(key, "scrolled-up")
            except Exception:
                r["error"] = traceback.format_exc(limit=3)
            res["pages"][key] = r
        res["jsErrors"] = errors
        b.close()
    (out / f"{name}.json").write_text(json.dumps(res, indent=1))
    return res


def check(out: Path) -> list[str]:
    """Every failed expectation in the results in OUT."""
    bad = []
    for name, (w, _, _) in VIEWPORTS.items():
        f = out / f"{name}.json"
        if not f.exists():
            bad.append(f"{name}: no results")
            continue
        r = json.loads(f.read_text())
        if r["jsErrors"]:
            bad.append(f"{name}: JavaScript errors {r['jsErrors']}")
        for key, v in r["pages"].items():
            where = f"{name} {key}"
            if "error" in v:
                bad.append(f"{where}: {v['error'].splitlines()[-1][:160]}")
                continue
            c = v["closed"]
            if c["overflowX"] > 0:
                bad.append(f"{where}: scrolls sideways by {c['overflowX']}px {c['offenders']}")
            if c["overlaps"] or c["offscreen"]:
                bad.append(f"{where}: header overlaps {c['overlaps']} offscreen {c['offscreen']}")
            if c["tabOverflow"] and c["tabOverflow"] > 0:
                bad.append(f"{where}: tab row overflows by {c['tabOverflow']}px")
            if key in ("docs", "deep") and c["header"] and c["header"]["h"] != 98:
                bad.append(f"{where}: header is {c['header']['h']}px high, not 98")
            if w >= 1220:
                if v.get("drawer"):
                    bad.append(f"{where}: drawer button shown at {w}px")
                continue
            d = v.get("drawer")
            if not d or not d["open"]:
                bad.append(f"{where}: drawer missing or did not open")
                continue
            if d["side"]["r"] > c["vw"]:
                bad.append(f"{where}: drawer wider than the window")
            full = d["side"]["w"] >= c["vw"] - 1
            if w < 720 and not full:
                bad.append(f"{where}: phone drawer is {d['side']['w']}px, not the full window")
            if d["side"]["x"] != 0 or d["side"]["y"] != 0:
                bad.append(f"{where}: drawer not flush with the window corner ({d['side']['x']},{d['side']['y']})")
            if d.get("scrollbar", 0) > 0:
                bad.append(f"{where}: drawer shows its own scrollbar ({d['scrollbar']}px)")
            if v.get("closeButton") is not True:
                bad.append(f"{where}: close button missing or did not close the drawer")
            if not full and v.get("overlayCloses") is not True:
                bad.append(f"{where}: tapping the overlay did not close the drawer")
            if v.get("escapeCloses") is not True:
                bad.append(f"{where}: Escape did not close the drawer")
            if d.get("htmlOverflow") != "hidden":
                bad.append(f"{where}: page behind the drawer still scrolls")
            # The list follows the part of the site: home anchors, the blog
            # alone (plus recent posts), or the docs without the blog.
            titles = [i.get("text") for i in d["items"] if not i.get("hidden")]
            if key == "home":
                if not d["anchors"] or d["headings"] != ["On this page"]:
                    bad.append(f"{where}: home drawer should list the page's sections {titles} {d['headings']}")
            elif key in ("blog", "post"):
                if titles != ["Blog"] or not d["posts"] or d["headings"] != ["Recent posts"]:
                    bad.append(f"{where}: blog drawer should hold the blog alone, then recent posts {titles} {d['headings']}")
            elif "Blog" in titles or len(titles) < 2:
                bad.append(f"{where}: docs drawer should hold the docs sections only {titles}")
            needs_chevron = key != "home"
            if any(not i.get("hidden") and not (i["icon"] and i["subtitle"] and (i["chevron"] or not needs_chevron)) for i in d["items"]):
                bad.append(f"{where}: a top-level drawer row lacks its icon, subtitle or chevron")
            dr = v.get("drill", {})
            if key in ("docs", "deep") and (dr.get("navigated") or not dr.get("opened", {}).get("checked") or dr.get("closed", {}).get("checked")):
                bad.append(f"{where}: section did not expand and collapse in place {dr}")
            sw = v.get("switch")
            if not isinstance(sw, dict) or sw["drawerOpen"] or sw["active"] != [sw["to"]]:
                bad.append(f"{where}: site switch {sw}")
            if v.get("leaf", {}).get("drawerOpen"):
                bad.append(f"{where}: following a link left the drawer open")
    return bad


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    if len(argv) > 1 and argv[1] != "--check":
        run(out, argv[1])
        return 0
    if len(argv) == 1:
        def one(name):
            return subprocess.run([sys.executable, __file__, str(out), name], capture_output=True, text=True).returncode
        with ThreadPoolExecutor(8) as pool:
            list(pool.map(one, VIEWPORTS))
    bad = check(out)
    print("\n".join(bad) if bad else "all checks pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
