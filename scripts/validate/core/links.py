"""Link extraction and resolution.

The failure this defends against is the quiet one: a renamed or deleted file
leaves a link pointing nowhere, Quarto renders it without complaint, and the
navigation is broken until a reader happens to click it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

# One level of nested brackets, to cope with this repository's `[[itp]](url)`
# and `[[GitHub repository]](url)` idiom.
INLINE_LINK_RE = re.compile(
    r"!?\[(?P<text>(?:[^\[\]]|\[[^\[\]]*\])*)\]"
    r"\(\s*(?P<target><[^>]*>|[^()\s]+)(?:\s+\"[^\"]*\")?\s*\)"
)
HTML_SRC_RE = re.compile(
    r"<(?:img|source|video|embed)\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I
)
HTML_HREF_RE = re.compile(r"<a\b[^>]*?\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I)
CODE_SPAN_RE = re.compile(r"`[^`\n]*`")

# Quarto listing filters, e.g. `index.qmd#category=!🍸Core papers`. These are
# NOT heading anchors; resolving them as such would produce a false positive on
# the core-papers link that the tutorials page depends on.
LISTING_FILTER_RE = re.compile(r"^(category|author|year|title|publication)=")

ASSET_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf", ".ico",
    ".itp", ".gro", ".pdb", ".xtc", ".tpr", ".mdp", ".top", ".map",
    ".zip", ".tar", ".gz", ".py", ".sh", ".csv", ".txt", ".ipynb", ".bib",
}


@dataclass
class Link:
    text: str
    target: str
    line: int
    is_image: bool = False

    @property
    def path_part(self) -> str:
        return self.target.split("#", 1)[0].split("?", 1)[0]

    @property
    def fragment(self) -> str | None:
        _, sep, frag = self.target.partition("#")
        return frag if sep else None


def extract_links(lines) -> list[Link]:
    """Pull links out of (line_number, text) pairs.

    Callers should pass markdown-only lines: the tutorials and lectures pages
    embed several hundred lines of raw CSS which would otherwise be mined for
    links that do not exist.
    """
    links: list[Link] = []

    for lineno, text in lines:
        scrubbed = CODE_SPAN_RE.sub(lambda m: " " * len(m.group(0)), text)

        for match in INLINE_LINK_RE.finditer(scrubbed):
            target = match.group("target").strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            links.append(Link(
                text=match.group("text").strip(),
                target=target,
                line=lineno,
                is_image=match.group(0).startswith("!"),
            ))

        for match in HTML_SRC_RE.finditer(text):
            links.append(Link("", match.group(1).strip(), lineno, is_image=True))
        for match in HTML_HREF_RE.finditer(text):
            links.append(Link("", match.group(1).strip(), lineno))

    return links


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
# A path-like target has a separator, an extension, or a fragment. Anything
# else is a bare word.
PATH_LIKE_RE = re.compile(r"[/.#]")


def classify(target: str) -> str:
    """One of: external, mailto, bare-email, anchor, listing-filter, empty,
    bare-word, internal."""
    if not target or target.strip() in {"#", ""}:
        return "empty"
    if target.startswith(("http://", "https://", "//")):
        return "external"
    if target.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return "mailto"
    if EMAIL_RE.match(target):
        # e.g. [Chris Brasnett](c.s.brasnett@rug.nl) — renders as a link to a
        # nonexistent relative path rather than an email.
        return "bare-email"
    if target.startswith("#"):
        return "listing-filter" if LISTING_FILTER_RE.match(target[1:]) else "anchor"
    if "#" in target and LISTING_FILTER_RE.match(target.split("#", 1)[1]):
        return "listing-filter"
    if not PATH_LIKE_RE.search(target):
        # A target with no separator, extension, or fragment. Usually chemical
        # nomenclature that happens to match link syntax -- abstracts are full
        # of constructs like "poly[(N,N'-bis...)](NDI)" -- but occasionally a
        # cross-reference missing its leading '#'. Treated separately so the
        # former does not produce hard errors across the publication corpus.
        return "bare-word"
    return "internal"


def resolve(source: Path, target: str, root: Path) -> Path | None:
    """Resolve an internal link to a filesystem path, or None if unresolvable."""
    raw = unquote(target.split("#", 1)[0].split("?", 1)[0]).strip()
    if not raw:
        return None

    if raw.startswith("/"):
        candidate = root / raw.lstrip("/")
    else:
        candidate = source.parent / raw

    try:
        candidate = candidate.resolve()
    except (OSError, RuntimeError):
        return None

    # Keep resolution inside the repository.
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def exists_with_fallbacks(candidate: Path) -> Path | None:
    """Accept the target, or the conventional Quarto equivalents.

    A directory link such as `/docs/tutorials/Martini3/Bentopy` is valid and
    resolves to that directory's index.qmd; `page.html` in source refers to
    `page.qmd`.
    """
    if candidate.exists():
        if candidate.is_dir():
            for name in ("index.qmd", "index.md", "index.html"):
                if (candidate / name).exists():
                    return candidate / name
            return candidate
        return candidate

    if candidate.suffix == ".html":
        for suffix in (".qmd", ".md", ".ipynb"):
            sibling = candidate.with_suffix(suffix)
            if sibling.exists():
                return sibling

    if not candidate.suffix:
        for suffix in (".qmd", ".md"):
            sibling = candidate.with_suffix(suffix)
            if sibling.exists():
                return sibling

    return None


def is_asset(target: str) -> bool:
    suffix = Path(unquote(target.split("#", 1)[0])).suffix.lower()
    return suffix in ASSET_SUFFIXES


def external_host(target: str) -> str:
    try:
        return urlparse(target).netloc.lower()
    except ValueError:
        return ""
