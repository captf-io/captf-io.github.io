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

"""Credit every blog post to the GitHub users who committed to it.

Authors are not kept in the repository: they are read from git when the
site is published. For each post in docs/blog/posts/, this follows the
file's history (renames included) and asks the GitHub API which account
authored each commit. The post's `authors:` becomes those logins, in the
order they first committed, and docs/blog/.authors.yml gets a card for
each from their GitHub profile: name (or login), avatar and URL. Bots are
left out, and so are commits whose email no GitHub account claims (they
are listed).

Like tools/git_dates.py, it rewrites the working tree that CI builds from
and discards (`make build-pages`); nothing it writes is committed, so a
post's authors are always its committers. The committed `maintainers`
card is what a local build shows, and what a post keeps if the API cannot
be reached (the build carries on and says so). The repository is
GITHUB_REPOSITORY in CI, else the origin remote; GH_TOKEN or GITHUB_TOKEN,
if set, raises the API's rate limit.

Usage:
  blog_authors.py --write [--force]   credit the posts (CI, before the build)
  blog_authors.py                     print who would be credited
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "docs" / "blog" / "posts"
AUTHORS = ROOT / "docs" / "blog" / ".authors.yml"
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def api(path: str) -> dict:
    req = urllib.request.Request(f"https://api.github.com/{path}",
                                 headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def repository() -> str:
    """owner/name: GITHUB_REPOSITORY in CI, else the origin remote."""
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, check=True,
                         capture_output=True, text=True).stdout.strip()
    return re.search(r"github\.com[:/](.+?)(?:\.git)?$", url).group(1)


def commits(post: Path) -> list[str]:
    """The post's commits, oldest first."""
    rel = post.relative_to(ROOT).as_posix()
    out = subprocess.run(["git", "log", "--follow", "--reverse", "--format=%H", "--", rel],
                         cwd=ROOT, check=True, capture_output=True, text=True).stdout
    return out.split()


def main(argv: list[str]) -> int:
    write = "--write" in argv
    if write and not os.environ.get("CI") and "--force" not in argv:
        print("blog_authors.py --write rewrites the posts for the published build;"
              " it runs in CI. Use --force to run it here, then `git checkout docs/blog`.",
              file=sys.stderr)
        return 1
    repo = repository()
    users: dict[str, dict] = {}
    by_sha: dict[str, str | None] = {}
    unlinked: set[str] = set()
    plan: dict[Path, list[str]] = {}
    try:
        for post in sorted(POSTS.glob("*.md")):
            logins: list[str] = []
            for sha in commits(post):
                if sha not in by_sha:
                    commit = api(f"repos/{repo}/commits/{sha}")
                    author = commit.get("author")
                    if not author:
                        unlinked.add(commit["commit"]["author"]["email"])
                        by_sha[sha] = None
                    elif author.get("type") == "Bot":
                        by_sha[sha] = None
                    else:
                        by_sha[sha] = author["login"]
                        if author["login"] not in users:
                            profile = api(f"users/{author['login']}")
                            users[author["login"]] = {
                                "name": profile.get("name") or author["login"],
                                "description": f"@{author['login']} on GitHub",
                                "avatar": author["avatar_url"],
                                "url": author["html_url"],
                            }
                login = by_sha[sha]
                if login and login not in logins:
                    logins.append(login)
            if logins:
                plan[post] = logins
    except (urllib.error.URLError, TimeoutError, KeyError) as err:
        print(f"blog_authors.py: GitHub API unavailable ({err}); authors left as committed", file=sys.stderr)
        return 0

    for email in sorted(unlinked):
        print(f"no GitHub account for commits by {email}; not credited", file=sys.stderr)

    cards = yaml.safe_load(AUTHORS.read_text())["authors"]
    cards_changed = False
    for login, card in users.items():
        if cards.get(login) != card:
            cards[login] = card
            cards_changed = True
    changed = 0
    for post, logins in plan.items():
        text = post.read_text()
        front = FRONT.match(text).group(1)
        current = re.search(r"^authors:\n((?:  - .*\n?)+)", front + "\n", re.M)
        old = re.findall(r"^  - (.*)$", current.group(1), re.M) if current else []
        if old == logins:
            continue
        changed += 1
        print(f"{post.name}: {', '.join(old) or '-'} -> {', '.join(logins)}")
        if write:
            block = "authors:\n" + "".join(f"  - {login}\n" for login in logins)
            if current:
                front = (front + "\n").replace(current.group(0), block, 1).rstrip("\n")
            else:
                front += "\n" + block.rstrip("\n")
            post.write_text(f"---\n{front}\n---\n" + text[FRONT.match(text).end():])
    if write and cards_changed:
        header = AUTHORS.read_text().split("authors:", 1)[0]
        AUTHORS.write_text(header + yaml.safe_dump({"authors": cards}, sort_keys=False, allow_unicode=True))
    print(f"{changed} posts {'updated' if write else 'would change'}"
          + (f"; .authors.yml {'updated' if write else 'would change'}" if cards_changed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
