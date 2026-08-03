"""Site-wide structural rules: navigation, internal links, assets, orphans.

These run over the whole repository regardless of --changed-only, because
deleting or renaming one file breaks links in files the pull request never
touched.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..core.discovery import iter_qmd_files
from ..core.divs import heading_slugs
from ..core.finding import Finding, error, warning
from ..core.links import (
    classify,
    exists_with_fallbacks,
    extract_links,
    is_asset,
    resolve,
)
from ..core.qmd import parse_qmd

# Hosts we own. A 403 or 404 from these means the object is missing or not
# public, whereas a publisher blocking a bot says nothing about the link.
OWNED_HOSTS = {
    "cgmartini-library.s3.ca-central-1.amazonaws.com",
    "d3ebrx6qufncts.cloudfront.net",
}


def check_site(ctx) -> list[Finding]:
    """Entry point invoked once per run, outside the per-document loop."""
    findings: list[Finding] = []
    findings.extend(_check_navigation(ctx))
    findings.extend(_check_internal_links(ctx))
    findings.extend(_check_stray_files(ctx))
    return findings


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def _check_navigation(ctx) -> list[Finding]:
    """Every navbar / sidebar / footer target must exist.

    _quarto.yml enumerates roughly forty explicit .qmd paths across four
    hand-maintained sidebars. A renamed file leaves a dead nav entry that
    Quarto renders without complaint.
    """
    findings: list[Finding] = []
    config_path = ctx.root / "_quarto.yml"
    text = config_path.read_text(encoding="utf-8")

    try:
        config = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        return [error(
            "site.quarto-yml-invalid", "_quarto.yml",
            f"_quarto.yml is not valid YAML: {exc}", 1,
            "The site cannot build until this parses.",
        )]

    lines = text.splitlines()

    def line_of(needle: str) -> int:
        for index, line in enumerate(lines, start=1):
            if needle in line:
                return index
        return 1

    referenced: set[str] = set()

    for target in _walk_hrefs(config.get("website", {})):
        if classify(target) != "internal":
            continue
        candidate = resolve(config_path, target, ctx.root)
        resolved = exists_with_fallbacks(candidate) if candidate else None
        if resolved is None:
            findings.append(error(
                "site.nav-target-missing", "_quarto.yml",
                f"Navigation entry points to {target!r}, which does not exist.",
                line_of(target),
                "Correct the path or remove the entry. Quarto renders a dead "
                "navigation link without reporting anything.",
            ))
        else:
            referenced.add(resolved.relative_to(ctx.root).as_posix())

    ctx.shared["nav_referenced"] = referenced

    # The reverse direction: a parameters page absent from the sidebar AND not
    # linked from any other page is unreachable. Being linked from a sidebar
    # page is fine -- several detail pages are deliberately reached that way
    # rather than cluttering the navigation.
    linked_from_content = _linked_targets(ctx)

    for path in sorted((ctx.root / "docs" / "downloads" / "force-field-parameters").rglob("*.qmd")):
        rel = path.relative_to(ctx.root).as_posix()
        if rel not in referenced and rel not in linked_from_content:
            findings.append(warning(
                "site.page-unreachable", rel,
                "This parameters page is in neither a _quarto.yml sidebar nor "
                "linked from any other page, so nobody can reach it.",
                1,
                "Add it to the matching Martini version section in "
                "_quarto.yml, link to it from a related page, or delete it if "
                "it is obsolete.",
            ))

    return findings


def _linked_targets(ctx) -> set[str]:
    """Every internal page reachable by a link from some other page."""
    cached = ctx.shared.get("linked_targets")
    if cached is not None:
        return cached

    docs = ctx.shared.get("all_site_docs")
    if docs is None:
        docs = [parse_qmd(p, ctx.root) for p in iter_qmd_files(ctx.root)]
        ctx.shared["all_site_docs"] = docs

    targets: set[str] = set()
    for doc in docs:
        for link in extract_links(doc.markdown_lines()):
            if classify(link.target) != "internal":
                continue
            candidate = resolve(doc.path, link.target, ctx.root)
            resolved = exists_with_fallbacks(candidate) if candidate else None
            if resolved is not None:
                targets.add(resolved.relative_to(ctx.root).as_posix())

    ctx.shared["linked_targets"] = targets
    return targets


def _walk_hrefs(node):
    """Yield every href / bare path string in the website config."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "href" and isinstance(value, str):
                yield value
            else:
                yield from _walk_hrefs(value)
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, str) and item.endswith((".qmd", ".md", ".ipynb")):
                yield item
            else:
                yield from _walk_hrefs(item)


# ---------------------------------------------------------------------------
# Internal links and assets
# ---------------------------------------------------------------------------

def _check_internal_links(ctx) -> list[Finding]:
    findings: list[Finding] = []
    slug_cache: dict[Path, dict[str, int]] = {}

    docs = ctx.shared.get("all_site_docs")
    if docs is None:
        docs = [parse_qmd(p, ctx.root) for p in iter_qmd_files(ctx.root)]
        ctx.shared["all_site_docs"] = docs

    for doc in docs:
        for link in extract_links(doc.markdown_lines()):
            kind = classify(link.target)

            if kind in ("external", "mailto", "empty", "listing-filter"):
                continue

            if kind == "bare-email":
                findings.append(error(
                    "link.email-without-mailto", doc.relpath,
                    f"Link target {link.target!r} is an email address written "
                    f"without a mailto: prefix.",
                    link.line,
                    f"Write [text](mailto:{link.target}). As it stands the link "
                    f"resolves to a nonexistent page on the site.",
                ))
                continue

            if kind == "bare-word":
                slugs = _slugs_for(doc.path, ctx.root, slug_cache)
                if link.target in slugs:
                    findings.append(warning(
                        "link.anchor-missing-hash", doc.relpath,
                        f"Link target {link.target!r} matches a heading on this "
                        f"page but is missing its leading '#'.",
                        link.line,
                        f"Write [text](#{link.target}).",
                    ))
                continue

            if kind == "anchor":
                slugs = _slugs_for(doc.path, ctx.root, slug_cache)
                anchor = link.fragment or ""
                if anchor and anchor not in slugs:
                    findings.append(warning(
                        "link.broken-anchor", doc.relpath,
                        f"Link to #{anchor} does not match any heading on this page.",
                        link.line,
                        "Anchors come from heading text: lowercase, punctuation "
                        "removed, spaces replaced by hyphens.",
                    ))
                continue

            candidate = resolve(doc.path, link.target, ctx.root)
            resolved = exists_with_fallbacks(candidate) if candidate else None

            if resolved is None:
                rule = "link.broken-asset" if is_asset(link.target) else "link.broken-internal"
                findings.append(error(
                    rule, doc.relpath,
                    f"Link target {link.target!r} does not exist.",
                    link.line,
                    "Check the path is relative to this file. Large data files "
                    "belong in the S3 library rather than the repository.",
                ))
                continue

            fragment = link.fragment
            if fragment and resolved.suffix in (".qmd", ".md"):
                slugs = _slugs_for(resolved, ctx.root, slug_cache)
                if fragment not in slugs:
                    findings.append(warning(
                        "link.broken-anchor", doc.relpath,
                        f"Link to {link.target!r} resolves, but the page has no "
                        f"#{fragment} heading.",
                        link.line,
                        "Check the heading text on the target page; the anchor "
                        "is derived from it.",
                    ))

    return findings


def _slugs_for(path: Path, root: Path, cache: dict) -> dict[str, int]:
    if path not in cache:
        try:
            doc = parse_qmd(path, root)
            cache[path] = heading_slugs(doc.markdown_lines())
        except (OSError, ValueError):
            cache[path] = {}
    return cache[path]


# ---------------------------------------------------------------------------
# Repository hygiene
# ---------------------------------------------------------------------------

STRAY_SUFFIXES = {".top", ".gro", ".xtc", ".tpr", ".trr", ".edr", ".log", ".cpt"}
LARGE_FILE_BYTES = 5 * 1024 * 1024


def _check_stray_files(ctx) -> list[Finding]:
    """Simulation output committed by accident, and empty pages."""
    findings: list[Finding] = []

    for path in sorted(ctx.root.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ctx.root).parts
        if any(part in {".git", "_site", "_freeze", ".quarto", ".venv",
                        "node_modules", "_extensions"} for part in rel_parts):
            continue
        rel = path.relative_to(ctx.root).as_posix()

        if path.suffix.lower() in STRAY_SUFFIXES:
            findings.append(warning(
                "site.stray-simulation-file", rel,
                f"{path.name} looks like simulation input or output committed "
                f"to the repository.", 1,
                "Simulation data belongs in the S3 library, not in the site "
                "repository. Link to it instead.",
            ))

        if path.suffix.lower() in {".qmd", ".md"} and path.stat().st_size == 0:
            findings.append(error(
                "site.empty-page", rel,
                "File is empty.", 1,
                "Add content or delete the file; an empty page renders as a "
                "blank entry.",
            ))

        try:
            if path.stat().st_size > LARGE_FILE_BYTES and path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif"}:
                mb = path.stat().st_size / 1024 / 1024
                findings.append(warning(
                    "site.large-file", rel,
                    f"File is {mb:.1f} MB.", 1,
                    "Large files bloat every clone. Host it in the S3 library "
                    "and link to it.",
                ))
        except OSError:
            pass

    return findings
