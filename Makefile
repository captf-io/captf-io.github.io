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

SHELL := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c

# Machine-local settings, such as ADDR = <a LAN address> to reach the
# preview from other machines; local.mk is not committed.
-include local.mk

# Where `make serve` listens.
ADDR ?= 127.0.0.1
PORT ?= 8001

ZENSICAL := uv run zensical

# podman or docker, for check-headers and fix-headers.
ENGINE ?= podman

.PHONY: help
help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  %-8s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: build
build: ## Build the site into site/, failing on any warning.
	$(ZENSICAL) build --strict -f zensical.toml

# The published build, as CI runs it: tools/git_dates.py dates each page
# and tools/blog_authors.py credits each post to its committers, both from
# git (rewriting front matter in the working tree, so don't commit what
# they leave; `git checkout docs` undoes it), then the build, then
# <lastmod> in the sitemap. Needs the whole history.
.PHONY: build-pages
build-pages: ## Build as CI publishes it: page dates, post authors and sitemap <lastmod> from git (rewrites front matter; CI only).
	uv run python tools/git_dates.py --write
	uv run python tools/blog_authors.py --write
	$(ZENSICAL) build --strict -f zensical.toml
	uv run python tools/git_dates.py --sitemap site/sitemap.xml

.PHONY: serve
serve: ## Serve on http://$(ADDR):$(PORT)/ with live reload.
	$(ZENSICAL) serve -f zensical.toml --dev-addr $(ADDR):$(PORT)

.PHONY: gen
gen: ## Regenerate the old-URL redirect stubs, the llms.txt sections and the drawer's recent posts (after adding, moving or re-describing pages or posts).
	uv run python tools/gen_redirects.py --write
	uv run python tools/gen_llms.py --write
	uv run python tools/gen_blog_nav.py --write

.PHONY: clean
clean: ## Remove the built site.
	rm -rf site

# The Apache-2.0 license header check: .licenserc.yaml says which files need
# the header. Runs as the host user, so fix-headers keeps file ownership.
LICENSE_EYE_IMAGE := docker.io/apache/skywalking-eyes:0.9.0@sha256:cd89ccbbcba2e87d3fb0e34b156b1da208d6c5ac1ada4e2d335e920022c765b8
ifeq ($(ENGINE),docker)
LICENSE_EYE_USER := --user $(shell id -u):$(shell id -g)
else
LICENSE_EYE_USER := --userns=keep-id --user $(shell id -u):$(shell id -g)
endif
LICENSE_EYE = $(ENGINE) run --rm $(LICENSE_EYE_USER) --security-opt label=disable \
	-v "$(CURDIR):/work" -w /work "$(LICENSE_EYE_IMAGE)"

.PHONY: check-headers
check-headers: ## Fail on any source file without the Apache-2.0 license header (.licenserc.yaml).
	@$(LICENSE_EYE) header check

.PHONY: fix-headers
fix-headers: ## Add the Apache-2.0 license header to every source file missing it.
	@$(LICENSE_EYE) header fix
