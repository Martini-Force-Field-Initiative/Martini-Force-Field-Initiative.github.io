"""Relational rules for announcement posts.

The rules here defend the two consumers that a field-level schema cannot
reach: the S3-triggered email Lambda, and the homepage feed.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from ..core.finding import Finding, error, warning
from ..core.qmd import QmdDoc
from . import rule

DATE_FORMAT = "%m/%d/%Y"
# Correctly shaped MM/DD/YYYY, which does not imply a date that exists.
SHAPE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")

# Tags that render acceptably in an HTML email body. The Lambda injects the
# description straight into the SES message, so an unbalanced block-level tag
# corrupts the email for every subscriber.
ALLOWED_HTML_TAGS = {"i", "b", "em", "strong", "br", "code", "sub", "sup", "a"}
TAG_RE = re.compile(r"<\s*(/?)\s*([A-Za-z][A-Za-z0-9]*)[^>]*?(/?)\s*>")

DIRNAME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[-_].+$")


@rule("announcement.date_is_real")
def date_is_real(doc: QmdDoc, ctx) -> list[Finding]:
    """A syntactically valid date can still be a nonexistent calendar day."""
    value = doc.fm.get("date")
    if not isinstance(value, str) or not value.strip():
        return []
    line = doc.line_of("date", 1)
    text = value.strip()
    try:
        parsed = datetime.strptime(text, DATE_FORMAT).date()
    except ValueError:
        if SHAPE_RE.match(text):
            # Correctly shaped but not a real day: 02/31, 04/31, 02/30 in a
            # non-leap year. The schema's pattern cannot express this.
            return [error(
                "announcement.date-not-a-real-day", doc.relpath,
                f"Date {text!r} is correctly formatted but is not a real "
                f"calendar day.", line,
                "Check the day number for that month.",
            )]
        return []

    findings: list[Finding] = []
    horizon = date.today() + timedelta(days=365)
    if parsed > horizon:
        findings.append(warning(
            "announcement.date-far-future", doc.relpath,
            f"Date {value!r} is more than a year in the future.", line,
            "Check the year. Remember the format is MM/DD/YYYY, not DD/MM/YYYY.",
        ))
    if parsed.year < 2003:
        findings.append(warning(
            "announcement.date-implausible", doc.relpath,
            f"Date {value!r} predates the Martini force field.", line,
            "Check the year digits.",
        ))
    return findings


@rule("announcement.image_exists")
def image_exists(doc: QmdDoc, ctx) -> list[Finding]:
    value = doc.fm.get("image")
    if not isinstance(value, str) or not value.strip():
        return []
    name = value.strip()
    target = doc.path.parent / name
    if not target.exists():
        available = sorted(
            p.name for p in doc.path.parent.iterdir()
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        )
        suggestion = (
            f" Images in this folder: {', '.join(available)}."
            if available else
            " There are no image files in this post's folder."
        )
        return [error(
            "announcement.image-missing", doc.relpath,
            f"Image {name!r} does not exist next to index.qmd.",
            doc.line_of("image", 1),
            f"Add the file to the post folder, or clear the field."
            f"{suggestion}",
        )]
    return []


@rule("announcement.directory_layout")
def directory_layout(doc: QmdDoc, ctx) -> list[Finding]:
    """Post folders are named YYYY-MM-DD-keywords.

    The folder date and the front-matter date are allowed to differ: several
    posts legitimately record an event date distinct from the posting date.
    Flagging that as an error would be wrong, so it is only ever a warning.
    """
    findings: list[Finding] = []
    dirname = doc.path.parent.name

    match = DIRNAME_RE.match(dirname)
    if not match:
        return [warning(
            "announcement.dirname-format", doc.relpath,
            f"Post folder {dirname!r} does not follow YYYY-MM-DD-keywords.", 1,
            "Rename the folder, e.g. 2026-05-28-metabolites.",
        )]

    value = doc.fm.get("date")
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.strptime(value.strip(), DATE_FORMAT).date()
        except ValueError:
            return findings
        folder_date = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        if parsed.isoformat() != folder_date:
            findings.append(warning(
                "announcement.dirname-date-mismatch", doc.relpath,
                f"Folder date {folder_date} differs from the front-matter date "
                f"{parsed.isoformat()}.",
                doc.line_of("date", 1),
                "This is fine if deliberate (for example an event date that "
                "differs from the posting date); otherwise align the two.",
            ))
    return findings


@rule("announcement.description_html_safe")
def description_html_safe(doc: QmdDoc, ctx) -> list[Finding]:
    """The description is injected into the notification email as raw HTML."""
    value = doc.fm.get("description")
    if not isinstance(value, str) or "<" not in value:
        return []

    line = doc.line_of("description", 1)
    findings: list[Finding] = []
    stack: list[str] = []

    for closing, name, self_closing in TAG_RE.findall(value):
        tag = name.lower()
        if tag not in ALLOWED_HTML_TAGS:
            findings.append(error(
                "announcement.description-html-tag", doc.relpath,
                f"Description uses <{tag}>, which is not allowed in the "
                f"notification email.", line,
                f"Allowed tags are: {', '.join(sorted(ALLOWED_HTML_TAGS))}. "
                f"Prefer plain text.",
            ))
            continue
        if tag == "br" or self_closing:
            continue
        if closing:
            if not stack or stack[-1] != tag:
                findings.append(error(
                    "announcement.description-html-unbalanced", doc.relpath,
                    f"Description has a closing </{tag}> with no matching "
                    f"opening tag.", line,
                    "Unbalanced HTML corrupts the email sent to every "
                    "subscriber.",
                ))
            else:
                stack.pop()
        else:
            stack.append(tag)

    if stack:
        findings.append(error(
            "announcement.description-html-unbalanced", doc.relpath,
            f"Description leaves {', '.join('<%s>' % t for t in stack)} "
            f"unclosed.", line,
            "Close every tag you open; the description is sent as HTML email.",
        ))
    return findings


@rule("announcement.lambda_contract")
def lambda_contract(doc: QmdDoc, ctx) -> list[Finding]:
    """Reproduce the email Lambda's regex parse and compare to the YAML truth.

    docs/announcements/backend/lambda/sendAnnouncement.js extracts the title
    and description with regular expressions, then emails the result to every
    subscriber. If its extraction disagrees with what the YAML actually says,
    subscribers receive something other than what the author wrote -- and
    nothing on the website reveals the discrepancy.

    This rule is the fast, dependency-free approximation. The authoritative
    check runs the real JavaScript; see scripts/validate/consumers/.
    """
    findings: list[Finding] = []

    front_matter = re.search(r"---([\s\S]*?)---", doc.raw)
    if not front_matter:
        return [error(
            "announcement.lambda-no-frontmatter", doc.relpath,
            "The email Lambda cannot find a front-matter block in this post.",
            1,
            "The file must open with a '---' line and close the block with "
            "another '---'. Without it the announcement email is never sent.",
        )]
    block = front_matter.group(1)

    title_match = re.search(r'title: ["\']?([\s\S]*?)["\']?(?=\n\S|$)', block)
    if not title_match:
        findings.append(error(
            "announcement.lambda-no-title", doc.relpath,
            "The email Lambda cannot extract a title from this post.",
            doc.line_of("title", 1),
            "It throws without one, so no email is sent at all.",
        ))
    else:
        extracted = title_match.group(1).strip()
        actual = doc.fm.get("title")
        if isinstance(actual, str) and extracted != actual.strip():
            findings.append(error(
                "announcement.lambda-title-mismatch", doc.relpath,
                f"Subscribers would receive the title {extracted!r} instead of "
                f"{actual.strip()!r}.",
                doc.line_of("title", 1),
                "This is almost always a trailing '# ...' comment on the title "
                "line; the Lambda's regex does not understand comments.",
            ))

    desc_match = re.search(
        r"description:\s*(\|)?\s*([\s\S]*?)(?=\n\S|$)", block
    )
    if not desc_match:
        findings.append(error(
            "announcement.lambda-no-description", doc.relpath,
            "The email Lambda cannot extract a description from this post.",
            doc.line_of("description", 1),
            "It throws without one, so no email is sent at all.",
        ))
    else:
        extracted = desc_match.group(2).strip().strip('"').strip()
        actual = doc.fm.get("description")
        if isinstance(actual, str):
            if _normalise(extracted) != _normalise(actual):
                findings.append(error(
                    "announcement.lambda-description-mismatch", doc.relpath,
                    "The description subscribers would receive differs from "
                    "the one in the front matter.",
                    doc.line_of("description", 1),
                    "Usually a trailing comment on the 'description:' line, or "
                    "a description spanning more lines than the Lambda's regex "
                    "captures.",
                ))
    return findings


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().strip('"')).strip()


@rule("announcement.metadata_in_sync")
def metadata_in_sync(doc: QmdDoc, ctx) -> list[Finding]:
    """The committed _metadata.yml must match what the posts imply.

    That file is both Quarto directory metadata and the data source for the
    homepage news feed. It has been hand-edited in the past and silently
    drifted from the posts, so the homepage showed a stale feed with an
    author name that appeared nowhere in the sources.

    Reported once per run, not once per post.
    """
    if ctx.shared.get("_metadata_checked"):
        return []
    ctx.shared["_metadata_checked"] = True

    import importlib.util

    generator = ctx.root / "scripts" / "generate-announcements-metadata.py"
    spec = importlib.util.spec_from_file_location("_mffi_gen", generator)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    target = ctx.root / "docs" / "announcements" / "posts" / "_metadata.yml"
    relpath = target.relative_to(ctx.root).as_posix()

    try:
        expected = module.render_metadata(module.load_announcements())
    except SystemExit as exc:
        return [error(
            "announcement.metadata-ungeneratable", relpath, str(exc), None,
            "Fix the reported post(s); the homepage feed cannot be rebuilt "
            "until they parse.",
        )]

    actual = target.read_text(encoding="utf-8") if target.exists() else ""
    if actual != expected:
        return [warning(
            "announcement.metadata-stale", relpath,
            "The committed homepage feed does not match the announcement posts.",
            None,
            "Run: python scripts/generate-announcements-metadata.py — and "
            "commit the result. Deployment regenerates it anyway, so this is "
            "not a merge blocker, but the committed copy should not drift.",
        )]
    return []
