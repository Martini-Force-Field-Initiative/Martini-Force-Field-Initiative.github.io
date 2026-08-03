"""Parsing of Quarto `.qmd` source files.

This module exists because the obvious approach is wrong. The announcements
metadata generator used to do::

    parts = content.split('---', 2)

which finds *any* ``---`` anywhere in the file. A post whose body contains a
horizontal rule, an em-dash run, or a YAML block in a code fence is silently
mis-parsed. It also throws away line numbers, duplicate keys, and trailing
comments -- and trailing comments are precisely what the announcements Lambda
leaks into subscriber emails.

So: frontmatter exists only if line 1 is exactly ``---``, and it ends at the
next line that is exactly ``---`` (or ``...``). We never scan the body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FENCE_RE = re.compile(r"^(?:---|\.\.\.)\s*$")
TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.\-]*)\s*:")
BLOCK_SCALAR_RE = re.compile(r":\s*[|>][+-]?\d*\s*$")


class _DupTrackingLoader(yaml.SafeLoader):
    """SafeLoader that records duplicate mapping keys instead of silently
    keeping the last one. `yaml.safe_load` is used rather than `yaml.load`
    because contributor-supplied files are untrusted in the fork-PR model."""


def _construct_mapping(loader, node, deep=False):
    mapping = {}
    duplicates = []
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            duplicates.append((key, key_node.start_mark.line + 1))
        mapping[key] = loader.construct_object(value_node, deep=deep)
    loader.mffi_duplicates = getattr(loader, "mffi_duplicates", []) + duplicates
    return mapping


_DupTrackingLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def strip_comment(line: str) -> tuple[str, str | None]:
    """Split a YAML line into (code, comment), respecting quoting.

    A ``#`` only starts a comment at the start of the line or after
    whitespace -- otherwise ``#FDF7F4`` and URLs with fragments would be
    mangled.
    """
    out: list[str] = []
    quote: str | None = None
    for i, char in enumerate(line):
        if quote:
            out.append(char)
            if char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
            out.append(char)
            continue
        if char == "#" and (not out or out[-1].isspace()):
            return "".join(out).rstrip(), line[i:].strip()
        out.append(char)
    return "".join(out).rstrip(), None


@dataclass
class QmdDoc:
    """A parsed `.qmd` file. Line numbers are 1-based throughout."""

    path: Path
    relpath: str
    raw: str
    lines: list[str]

    fm_present: bool = False
    fm_end_line: int | None = None
    fm_raw: str = ""
    fm: dict = field(default_factory=dict)
    fm_error: str | None = None
    fm_unterminated: bool = False

    key_lines: dict[str, int] = field(default_factory=dict)
    key_comments: dict[str, str] = field(default_factory=dict)
    duplicate_keys: list[tuple[str, int]] = field(default_factory=list)

    body_start_line: int = 1

    def line_of(self, key: str, default: int | None = None) -> int | None:
        """Line number of a top-level frontmatter key, for annotations."""
        return self.key_lines.get(key, default)

    @property
    def body(self) -> str:
        return "\n".join(self.lines[self.body_start_line - 1:])

    def body_lines(self):
        """Yield (line_number, text) for body lines only."""
        for offset, text in enumerate(self.lines[self.body_start_line - 1:]):
            yield self.body_start_line + offset, text

    def markdown_lines(self):
        """Yield (line_number, text) for body lines outside fenced code blocks.

        Every structural scanner (divs, links, headings) must consume this
        rather than the raw body: `tutorials.qmd` and `lectures.qmd` each
        embed a several-hundred-line ```{=HTML} CSS blob that would otherwise
        poison div and link detection.
        """
        in_fence = False
        fence_marker = ""
        for lineno, text in self.body_lines():
            stripped = text.lstrip()
            if not in_fence:
                match = re.match(r"^(`{3,}|~{3,})", stripped)
                if match:
                    in_fence = True
                    fence_marker = match.group(1)[0] * 3
                    continue
                yield lineno, text
            else:
                if stripped.startswith(fence_marker):
                    in_fence = False


def parse_qmd(path: Path, repo_root: Path) -> QmdDoc:
    raw = path.read_text(encoding="utf-8", errors="replace").lstrip("﻿")
    lines = raw.splitlines()
    relpath = path.relative_to(repo_root).as_posix()

    doc = QmdDoc(path=path, relpath=relpath, raw=raw, lines=lines)

    if not lines or lines[0].strip() != "---":
        # No frontmatter. Deliberately do NOT go hunting for a `---` further
        # down: that is exactly the bug this module exists to avoid.
        doc.body_start_line = 1
        return doc

    end_index = next(
        (i for i in range(1, len(lines)) if FENCE_RE.match(lines[i])), None
    )
    if end_index is None:
        doc.fm_present = True
        doc.fm_unterminated = True
        doc.body_start_line = len(lines) + 1
        return doc

    doc.fm_present = True
    doc.fm_end_line = end_index + 1
    doc.fm_raw = "\n".join(lines[1:end_index])
    doc.body_start_line = end_index + 2

    loader = _DupTrackingLoader(doc.fm_raw)
    try:
        parsed = loader.get_single_data()
        doc.duplicate_keys = getattr(loader, "mffi_duplicates", [])
        if parsed is None:
            doc.fm = {}
        elif isinstance(parsed, dict):
            doc.fm = parsed
        else:
            doc.fm_error = "front matter must be a mapping of key: value pairs"
    except yaml.YAMLError as exc:
        doc.fm_error = str(exc).replace("\n", " ")
    finally:
        loader.dispose()

    _index_keys(doc, lines, end_index)
    return doc


def _index_keys(doc: QmdDoc, lines: list[str], end_index: int) -> None:
    """Record the line number and trailing comment of each top-level key.

    Done by raw line scan because PyYAML discards both. Lines belonging to a
    block scalar's indented continuation are skipped so that a `description: |`
    body cannot masquerade as a key.
    """
    block_scalar_indent: int | None = None

    for offset in range(1, end_index):
        text = lines[offset]
        lineno = offset + 1
        indent = len(text) - len(text.lstrip())

        if block_scalar_indent is not None:
            if text.strip() and indent > block_scalar_indent:
                continue
            block_scalar_indent = None

        if not text.strip() or text.lstrip().startswith("#"):
            continue
        if indent != 0:
            continue

        match = TOP_LEVEL_KEY_RE.match(text)
        if not match:
            continue

        key = match.group(1)
        doc.key_lines.setdefault(key, lineno)
        code, comment = strip_comment(text)
        if comment:
            doc.key_comments[key] = comment
        if BLOCK_SCALAR_RE.search(code):
            block_scalar_indent = indent
