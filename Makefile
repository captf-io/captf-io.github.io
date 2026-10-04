SHELL := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c

# Machine-local settings, such as ADDR = <a LAN address> to reach the
# preview from other machines; local.mk is not committed.
-include local.mk

# Where `make serve` listens.
ADDR ?= 127.0.0.1
PORT ?= 8001

ZENSICAL := uv run zensical

.PHONY: help
help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  %-8s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: build
build: ## Build the site into site/, failing on any warning.
	$(ZENSICAL) build --strict -f zensical.toml

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
