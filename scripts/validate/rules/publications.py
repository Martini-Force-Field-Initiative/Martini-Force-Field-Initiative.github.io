"""Relational rules for publication entries."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from ..core.finding import Finding, Severity, error, warning
from ..core.qmd import QmdDoc
from . import rule

# Characters that look like ASCII but are not.
CONFUSABLES = {
    "‐": "HYPHEN (U+2010)",
    "‑": "NON-BREAKING HYPHEN (U+2011)",
    "‒": "FIGURE DASH (U+2012)",
    "–": "EN DASH (U+2013)",
    "—": "EM DASH (U+2014)",
    " ": "NO-BREAK SPACE (U+00A0)",
    "​": "ZERO WIDTH SPACE (U+200B)",
    "﻿": "BYTE ORDER MARK (U+FEFF)",
    "‘": "LEFT SINGLE QUOTE (U+2018)",
    "’": "RIGHT SINGLE QUOTE (U+2019)",
    "“": "LEFT DOUBLE QUOTE (U+201C)",
    "”": "RIGHT DOUBLE QUOTE (U+201D)",
}

FILENAME_RE = re.compile(r"^[^\W\d_][\w'\-]*\d{4}_[\w\-]+\.qmd$", re.UNICODE)


@rule("publication.year_matches_directory")
def year_matches_directory(doc: QmdDoc, ctx) -> list[Finding]:
    """The `year` field must equal the containing directory's name.

    All 264 entries satisfy this today, which makes it a safe invariant to
    lock in: it costs nothing now and catches a misfiled entry later.
    """
    year = doc.fm.get("year")
    directory = doc.path.parent.name
    if not isinstance(year, str) or not year.strip():
        return []
    if year.strip() != directory:
        return [error(
            "publication.year-directory-mismatch", doc.relpath,
            f"Field 'year' is {year!r} but the entry is filed under "
            f"{directory!r}.",
            doc.line_of("year", 1),
            f"Either correct the year or move the file to "
            f"docs/publications/entries/{year}/.",
        )]
    return []


@rule("publication.not_in_entries_root")
def not_in_entries_root(doc: QmdDoc, ctx) -> list[Finding]:
    """Entries must live one directory deep, under a year.

    The listing in docs/publications/index.qmd globs `entries/*/**.qmd`. A
    file placed directly in `entries/` is not matched, so it is silently
    absent from the site with no error anywhere. That invisibility is what
    makes this worth an explicit check.
    """
    parent = doc.path.parent
    if parent.name == "entries":
        return [error(
            "publication.not-under-year", doc.relpath,
            "Entry sits directly in entries/ instead of a year directory.",
            1,
            "Move it into the matching year, e.g. "
            "docs/publications/entries/2026/. The Publications listing only "
            "matches entries/<year>/*.qmd, so the entry would otherwise never "
            "appear on the site.",
        )]
    return []


@rule("publication.filename_hygiene")
def filename_hygiene(doc: QmdDoc, ctx) -> list[Finding]:
    """Filenames must be typeable and follow the Author<Year>_Keyword pattern."""
    findings: list[Finding] = []
    name = doc.path.name

    found = {ch: label for ch, label in CONFUSABLES.items() if ch in name}
    if found:
        described = ", ".join(sorted(found.values()))
        findings.append(error(
            "publication.filename-confusable", doc.relpath,
            f"Filename contains a look-alike character: {described}.", 1,
            "Replace it with the plain ASCII equivalent (a normal '-' or a "
            "normal space). These characters are visually identical to ASCII "
            "but break copy-pasted links.",
        ))

    if not FILENAME_RE.match(unicodedata.normalize("NFC", name)):
        findings.append(warning(
            "publication.filename-convention", doc.relpath,
            f"Filename {name!r} does not follow the Author<Year>_Keyword "
            f"convention.", 1,
            "Use e.g. Marrink2007_MartiniForceField.qmd — first author "
            "surname, four-digit year, underscore, one keyword.",
        ))

    return findings


@rule("publication.duplicate_doi")
def duplicate_doi(doc: QmdDoc, ctx) -> list[Finding]:
    """Two entries sharing a DOI usually means the same paper was added twice."""
    index = ctx.shared.get("publication_doi_index")
    if index is None:
        index = _build_doi_index(ctx)
        ctx.shared["publication_doi_index"] = index

    doi = _normalise_doi(doc.fm.get("doi"))
    if not doi:
        return []

    others = [p for p in index.get(doi, []) if p != doc.relpath]
    if others:
        return [warning(
            "publication.duplicate-doi", doc.relpath,
            f"DOI is also used by: {', '.join(sorted(others))}.",
            doc.line_of("doi", 1),
            "If these are genuinely different works, check the DOIs. If it is "
            "the same paper, keep one entry.",
        )]
    return []


def _build_doi_index(ctx) -> dict[str, list[str]]:
    index: dict[str, list[str]] = defaultdict(list)
    for doc in ctx.all_docs_for("publication"):
        doi = _normalise_doi(doc.fm.get("doi"))
        if doi:
            index[doi].append(doc.relpath)
    return index


def _normalise_doi(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().lower().rstrip("/")
    return text or None
