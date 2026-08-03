# Contributor entry points for the MFFI portal.
#
# Prerequisites:
#   * Quarto      https://quarto.org/docs/get-started/
#   * Python 3.9+ with PyYAML
#
# If `python3` does not have PyYAML, run `make setup` once. That is the common
# case on macOS and newer Linux distributions, where the system Python refuses
# `pip install` with an "externally-managed-environment" error.
#
# Deliberately no lockfile and no task runner beyond this. The point of the
# portal is that a domain scientist can contribute without becoming a web
# developer; the tooling has to honour that.

# Prefer a local .venv when one exists, otherwise fall back to python3.
# Override explicitly with:  make PYTHON=/path/to/python validate
PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.PHONY: help setup validate validate-changed lint-itp links metadata \
        metadata-check render preview test check

help:
	@echo "make setup            Create .venv with the one dependency (PyYAML)"
	@echo "make validate         Check every contribution against its contract"
	@echo "make validate-changed Check only what you changed against main"
	@echo "make lint-itp FILES=  Lint Martini .itp topologies anywhere on disk"
	@echo "make links            Also check that external and S3 links resolve"
	@echo "make metadata         Regenerate the homepage news feed"
	@echo "make metadata-check   Verify the feed matches the announcement posts"
	@echo "make preview          Serve the site locally on port 4040"
	@echo "make render           Build the site once"
	@echo "make test             Run the validator's own test suite"
	@echo "make check            validate + metadata-check + test  (what CI runs)"
	@echo ""
	@echo "Using python: $(PYTHON)"

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install --quiet --upgrade pip
	.venv/bin/python -m pip install --quiet pyyaml
	@echo "Ready. 'make validate' will now use .venv automatically."

validate:
	$(PYTHON) -m scripts.validate

# Scratch list of changed paths. Written, consumed, and deleted within the
# recipe below; never meant to survive it.
CHANGED_FILE := .changed-files

# Kept to a single shell (note the trailing backslashes) so the cleanup runs
# whether or not validation passed. As separate recipe lines, make aborted on
# the validator's non-zero exit and the `rm` never ran -- leaking the scratch
# file in exactly the case the target exists to detect.
#
# `2>/dev/null` on the first diff: repositories whose remote is not called
# "origin" would otherwise print "unknown revision origin/main" before the
# fallback succeeds.
validate-changed:
	@{ git diff --name-only --diff-filter=ACMR origin/main...HEAD 2>/dev/null \
	   || git diff --name-only --diff-filter=ACMR main...HEAD; } > $(CHANGED_FILE); \
	 $(PYTHON) -m scripts.validate --changed-only $(CHANGED_FILE); \
	 status=$$?; \
	 rm -f $(CHANGED_FILE); \
	 exit $$status

# Parameter files are not kept in this repository -- they live in the download
# library and reach the editors as a link -- so this takes paths to wherever
# they happen to be:  make lint-itp FILES="~/params/*.itp"
lint-itp:
	@if [ -z "$(FILES)" ]; then \
	   echo 'usage: make lint-itp FILES="path/to/file.itp [more.itp ...]"'; \
	   exit 2; \
	 fi
	$(PYTHON) -m scripts.lint_itp $(FILES)

links:
	$(PYTHON) -m scripts.validate_links --scope all

metadata:
	$(PYTHON) scripts/generate-announcements-metadata.py

metadata-check:
	$(PYTHON) scripts/generate-announcements-metadata.py --check

render:
	quarto render

preview:
	quarto preview --port 4040

test:
	$(PYTHON) -m unittest discover -s scripts/validate/tests -t . -v

check: validate metadata-check test
