"""Structural rules for tutorials and tool cards.

These contribution types are not defined by front-matter fields but by the
shape of fenced divs in the body, so they cannot be expressed in the
declarative schemas.
"""

from __future__ import annotations

import re

from ..core.discovery import is_excluded
from ..core.divs import parse_divs, slugify
from ..core.finding import Finding, error, warning
from ..core.links import classify, exists_with_fallbacks, extract_links, resolve
from ..core.qmd import parse_qmd

TUTORIAL_REGISTRY = "docs/tutorials/Martini3/tutorials.qmd"
TOOLS_DIR = "docs/downloads/tools"
TUTORIAL_ROOT = "docs/tutorials/Martini3"

BULLET_TITLE_RE = re.compile(r"^\*\*&#x2022;\s+.+\*\*\s*$")
DESCRIPTION_RE = re.compile(r"^\*\*Description:\*\*")


def check_structure(ctx) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_check_tool_cards(ctx))
    findings.extend(_check_tutorials(ctx))
    return findings


# ---------------------------------------------------------------------------
# Tool cards
# ---------------------------------------------------------------------------

def _check_tool_cards(ctx) -> list[Finding]:
    """A software card must open with an H3.

    styles.css attaches the gear glyph and the underline to `.software-card
    h3` specifically. A card whose first heading is `##` or `####` renders
    without either, and nothing else in the pipeline notices.
    """
    findings: list[Finding] = []
    tools_dir = ctx.root / TOOLS_DIR
    if not tools_dir.is_dir():
        return findings

    global_slugs: dict[str, str] = {}

    for path in sorted(tools_dir.glob("*.qmd")):
        doc = parse_qmd(path, ctx.root)
        result = parse_divs(doc.markdown_lines())

        for div in result.unclosed:
            findings.append(error(
                "tool.card-unclosed", doc.relpath,
                f"The '{div.name}' block opened here is never closed.",
                div.start_line,
                "Add a ':::' line to close it. Without one, everything below "
                "is swallowed into this card.",
            ))

        for lineno in result.stray_closes:
            findings.append(warning(
                "tool.stray-fence", doc.relpath,
                "A ':::' here closes a block that was never opened.", lineno,
                "Remove it, or add the matching opening fence.",
            ))

        cards = [d for d in result.divs if d.has_class("software-card")]
        for card in cards:
            first = card.first_significant()
            if first is None:
                findings.append(warning(
                    "tool.card-empty", doc.relpath,
                    "This software card is empty.", card.start_line, None,
                ))
                continue

            kind, level, text = first
            if kind != "heading" or level != 3:
                found = f"a level-{level} heading" if kind == "heading" else kind
                findings.append(error(
                    "tool.card-first-child-not-h3", doc.relpath,
                    f"A software card must begin with a '### ' heading; found "
                    f"{found}.",
                    card.start_line,
                    "The tool name has to be an H3. The gear icon and the "
                    "underline come from a CSS rule that matches "
                    "'.software-card h3' only, so any other level renders "
                    "unstyled.",
                ))
                continue

            slug = slugify(text)
            if slug in global_slugs and global_slugs[slug] != doc.relpath:
                findings.append(warning(
                    "tool.duplicate-card-slug", doc.relpath,
                    f"A card named {text!r} also exists in "
                    f"{global_slugs[slug]}.",
                    card.start_line,
                    "Cross-links use these anchors, so duplicates make "
                    "'#{}' ambiguous.".format(slug),
                ))
            global_slugs.setdefault(slug, doc.relpath)

            body = card.text()
            if not re.search(r"\]\(\s*https?://", body):
                findings.append(warning(
                    "tool.card-without-link", doc.relpath,
                    f"The card for {text!r} has no link to a repository or "
                    f"download.",
                    card.start_line,
                    "Readers need somewhere to obtain the tool.",
                ))

    return findings


# ---------------------------------------------------------------------------
# Tutorials
# ---------------------------------------------------------------------------

def _check_tutorials(ctx) -> list[Finding]:
    findings: list[Finding] = []
    registry_path = ctx.root / TUTORIAL_REGISTRY
    tutorial_root = ctx.root / TUTORIAL_ROOT

    if not tutorial_root.is_dir():
        return findings

    # Every tutorial page needs a title: it becomes the page heading and the
    # navigation label.
    for path in sorted(tutorial_root.rglob("*.qmd")):
        if is_excluded(path, ctx.root) or path.name.startswith("_"):
            continue
        doc = parse_qmd(path, ctx.root)
        if not doc.fm_present:
            findings.append(error(
                "tutorial.frontmatter-missing", doc.relpath,
                "Tutorial page has no YAML front matter.", 1,
                'Add a block at the top:\n---\ntitle: "..."\nformat: html\n---',
            ))
            continue
        title = doc.fm.get("title")
        if not isinstance(title, str) or not title.strip():
            findings.append(error(
                "tutorial.title-missing", doc.relpath,
                "Tutorial front matter has no non-empty 'title'.",
                doc.line_of("title", 1),
                "The title becomes the page heading and the navigation label.",
            ))

    if not registry_path.exists():
        return findings

    registry = parse_qmd(registry_path, ctx.root)
    result = parse_divs(registry.markdown_lines())

    for div in result.unclosed:
        findings.append(error(
            "tutorial.registry-unclosed", registry.relpath,
            f"The '{div.name}' block opened here is never closed.",
            div.start_line, "Add a ':::' line to close it.",
        ))

    items = [d for d in result.divs if d.has_class("tutorial-item")]
    if not items:
        findings.append(error(
            "tutorial.registry-empty", registry.relpath,
            "No ':::tutorial-item' entries found in the registry.", 1,
            "Each tutorial needs an entry here to appear on the site.",
        ))

    registered: set[str] = set()

    for item in items:
        lines = item.own_lines
        text_lines = [t.strip() for _, t in lines if t.strip()]

        if not any(BULLET_TITLE_RE.match(t) for t in text_lines):
            findings.append(warning(
                "tutorial.item-no-title", registry.relpath,
                "This tutorial entry has no bold bullet title line.",
                item.start_line,
                'Expected a line like: **&#x2022;  Lipid bilayers - Part I**',
            ))

        if not any(DESCRIPTION_RE.match(t) for t in text_lines):
            findings.append(warning(
                "tutorial.item-no-description", registry.relpath,
                "This tutorial entry has no '**Description:**' line.",
                item.start_line,
                "Readers scan these descriptions to choose a tutorial.",
            ))

        buttons = [c for c in item.children if c.has_class("tutorial-buttons")]
        if not buttons:
            findings.append(error(
                "tutorial.item-no-buttons", registry.relpath,
                "This tutorial entry has no ':::tutorial-buttons' block.",
                item.start_line,
                "Without it the entry renders with no way to open the "
                "tutorial.",
            ))
            continue

        links = []
        for button in buttons:
            links.extend(extract_links(button.own_lines))

        if not links:
            findings.append(error(
                "tutorial.item-no-link", registry.relpath,
                "This tutorial entry has a buttons block with no link in it.",
                item.start_line, None,
            ))

        for link in links:
            if classify(link.target) != "internal":
                continue
            candidate = resolve(registry_path, link.target, ctx.root)
            resolved = exists_with_fallbacks(candidate) if candidate else None
            if resolved is None:
                findings.append(error(
                    "tutorial.link-broken", registry.relpath,
                    f"Tutorial link {link.target!r} does not resolve to a file.",
                    link.line,
                    "Paths here are relative to docs/tutorials/Martini3/, "
                    "e.g. LipidsI/index.qmd",
                ))
            else:
                registered.add(resolved.relative_to(ctx.root).as_posix())

    # Reverse direction: a tutorial nobody can reach from the registry.
    for directory in sorted(p for p in tutorial_root.iterdir() if p.is_dir()):
        if directory.name.startswith((".", "_")):
            continue
        pages = {
            p.relative_to(ctx.root).as_posix()
            for p in directory.rglob("*.qmd")
        }
        if pages and not (pages & registered):
            rel = directory.relative_to(ctx.root).as_posix()
            findings.append(warning(
                "tutorial.unregistered", rel,
                f"Tutorial directory {directory.name!r} is not linked from "
                f"the hands-on tutorials page.", 1,
                f"Add a ':::tutorial-item' entry in {TUTORIAL_REGISTRY} so "
                f"readers can find it.",
            ))

    return findings
