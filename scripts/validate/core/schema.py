"""Interpreter for the declarative contribution-type schemas.

The design goal is that a domain scientist can add a required field, tighten a
pattern, or extend a controlled vocabulary by editing YAML under
`scripts/validate/schemas/`, never Python. Python is needed only for genuinely
relational checks (does this file's `year` match its directory?), which are
registered by name in `rules/`.

An unknown atom in a schema file is a hard failure, not a silent skip. A
check that quietly does nothing is worse than no check at all when the
framework is being cited as evidence of validation.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .finding import Finding, Severity
from .qmd import QmdDoc

KNOWN_ATOMS = {
    "required", "type", "const", "pattern", "pattern_message", "non_empty",
    "allow_empty", "min_items", "max_len", "forbid_chars", "forbid",
    "forbid_substrings", "vocabulary", "vocabulary_severity", "hint",
    "severity", "suggest_close_matches",
}

KNOWN_TYPES = {"str", "bool", "int", "url", "list_of_str", "relative_filename"}


class SchemaError(Exception):
    """Raised for a malformed schema file. Always fatal (exit code 2)."""


@dataclass
class Schema:
    id: str
    label: str
    applies_to: list[str]
    exclude: list[str] = field(default_factory=list)
    frontmatter: dict = field(default_factory=dict)
    body: dict = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    source: Path | None = None
    _vocabularies: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Schema":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for required in ("id", "applies_to"):
            if required not in data:
                raise SchemaError(f"{path}: missing required key {required!r}")

        schema = cls(
            id=data["id"],
            label=data.get("label", data["id"]),
            applies_to=list(data["applies_to"]),
            exclude=list(data.get("exclude", [])),
            frontmatter=data.get("frontmatter", {}) or {},
            body=data.get("body", {}) or {},
            rules=list(data.get("rules", []) or []),
            source=path,
        )
        schema._validate_atoms()
        schema._load_vocabularies(path.parent)
        return schema

    def _validate_atoms(self) -> None:
        for name, spec in (self.frontmatter.get("fields") or {}).items():
            if not isinstance(spec, dict):
                raise SchemaError(
                    f"{self.source}: field {name!r} must be a mapping"
                )
            unknown = set(spec) - KNOWN_ATOMS
            if unknown:
                raise SchemaError(
                    f"{self.source}: field {name!r} uses unknown atom(s) "
                    f"{sorted(unknown)}; known atoms are {sorted(KNOWN_ATOMS)}"
                )
            declared = spec.get("type")
            if declared and declared not in KNOWN_TYPES:
                raise SchemaError(
                    f"{self.source}: field {name!r} has unknown type "
                    f"{declared!r}; known types are {sorted(KNOWN_TYPES)}"
                )

    def _load_vocabularies(self, base: Path) -> None:
        for name, spec in (self.frontmatter.get("fields") or {}).items():
            vocab = spec.get("vocabulary")
            if not vocab:
                continue
            vocab_path = base / vocab
            if not vocab_path.exists():
                raise SchemaError(
                    f"{self.source}: field {name!r} references missing "
                    f"vocabulary file {vocab_path}"
                )
            data = yaml.safe_load(vocab_path.read_text(encoding="utf-8")) or {}
            self._vocabularies[name] = set(data.get("terms") or [])

    # ------------------------------------------------------------------
    # checking
    # ------------------------------------------------------------------

    def check(self, doc: QmdDoc) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._check_frontmatter_present(doc))
        if not doc.fm_present or doc.fm_error or doc.fm_unterminated:
            return findings
        findings.extend(self._check_structural(doc))
        findings.extend(self._check_fields(doc))
        findings.extend(self._check_body(doc))
        return findings

    def _check_frontmatter_present(self, doc: QmdDoc) -> list[Finding]:
        sev = Severity.parse(self.frontmatter.get("required", "error"))
        out = []
        if not doc.fm_present:
            out.append(Finding(
                f"{self.id}.frontmatter-missing", sev, doc.relpath,
                "File has no YAML front matter.", 1,
                'Add a "---" block at the very top of the file, before any other '
                "content. Copy the field list from the entry template.",
            ))
            return out
        if doc.fm_unterminated:
            out.append(Finding(
                f"{self.id}.frontmatter-unterminated", Severity.ERROR,
                doc.relpath, "Front matter is opened but never closed.", 1,
                'Add a closing "---" line after the last field.',
            ))
            return out
        if doc.fm_error:
            out.append(Finding(
                f"{self.id}.frontmatter-invalid", Severity.ERROR, doc.relpath,
                f"Front matter is not valid YAML: {doc.fm_error}", 1,
                "Check for unbalanced quotes and for values containing a colon "
                "that are not quoted.",
            ))
        return out

    def _check_structural(self, doc: QmdDoc) -> list[Finding]:
        out: list[Finding] = []

        dup_sev = self.frontmatter.get("duplicate_keys")
        if dup_sev:
            for key, lineno in doc.duplicate_keys:
                out.append(Finding(
                    f"{self.id}.duplicate-key", Severity.parse(dup_sev),
                    doc.relpath, f"Front matter defines {key!r} more than once.",
                    lineno, "Delete the redundant line; YAML keeps only the last "
                    "one, so the value you see may not be the value used.",
                ))

        unknown_sev = self.frontmatter.get("unknown_fields")
        if unknown_sev:
            declared = set(self.frontmatter.get("fields") or {})
            for key in doc.fm:
                if key not in declared:
                    suggestion = difflib.get_close_matches(key, declared, n=1, cutoff=0.7)
                    hint = (
                        f"Did you mean {suggestion[0]!r}?" if suggestion
                        else "Remove it, or add it to the schema if it is intentional."
                    )
                    out.append(Finding(
                        f"{self.id}.unknown-field", Severity.parse(unknown_sev),
                        doc.relpath, f"Unrecognised front-matter field {key!r}.",
                        doc.line_of(key, 1), hint,
                    ))

        comment_sev = self.frontmatter.get("trailing_comments")
        if comment_sev:
            for key, comment in doc.key_comments.items():
                out.append(Finding(
                    f"{self.id}.trailing-comment", Severity.parse(comment_sev),
                    doc.relpath,
                    f"Front-matter field {key!r} has a trailing comment: {comment}",
                    doc.line_of(key, 1),
                    "Delete the comment. The announcement email Lambda parses this "
                    "block with a regular expression that does not understand "
                    "comments, so the text is sent to subscribers.",
                ))

        return out

    def _check_fields(self, doc: QmdDoc) -> list[Finding]:
        out: list[Finding] = []
        for name, spec in (self.frontmatter.get("fields") or {}).items():
            out.extend(self._check_field(doc, name, spec))
        return out

    def _check_field(self, doc: QmdDoc, name: str, spec: dict) -> list[Finding]:
        out: list[Finding] = []
        line = doc.line_of(name, 1)
        hint = spec.get("hint")
        sev = Severity.parse(spec.get("severity", "error"))

        def fail(rule_suffix: str, message: str,
                 severity: Severity | None = None,
                 override_hint: str | None = None) -> None:
            out.append(Finding(
                f"{self.id}.{rule_suffix}", severity or sev, doc.relpath,
                message, line, override_hint or hint,
            ))

        present = name in doc.fm
        required = spec.get("required")
        if not present:
            if required and required is not False:
                req_sev = (
                    Severity.parse(required) if isinstance(required, str)
                    else Severity.ERROR
                )
                fail("field-missing", f"Required field {name!r} is missing.", req_sev)
            return out

        value = doc.fm[name]

        if "const" in spec:
            expected = spec["const"]
            if value != expected:
                fail(
                    "field-const",
                    f"Field {name!r} must be {_fmt(expected)}, found {_fmt(value)}.",
                )
                return out

        declared = spec.get("type")
        empty = value is None or (isinstance(value, str) and not value.strip())

        if empty:
            if spec.get("allow_empty"):
                return out
            if spec.get("non_empty") or required:
                fail("field-empty", f"Field {name!r} must not be empty.")
            return out

        if declared:
            type_finding = _check_type(declared, name, value)
            if type_finding:
                fail("field-type", type_finding)
                return out

        if declared == "list_of_str":
            items = value
            min_items = spec.get("min_items")
            if min_items and len(items) < min_items:
                fail("field-too-few",
                     f"Field {name!r} needs at least {min_items} item(s), found {len(items)}.")
            vocab = self._vocabularies.get(name)
            if vocab:
                vocab_sev = Severity.parse(spec.get("vocabulary_severity", "warning"))
                for item in items:
                    if item in vocab:
                        continue
                    suggestion = (
                        difflib.get_close_matches(str(item), vocab, n=1, cutoff=0.75)
                        if spec.get("suggest_close_matches", True) else []
                    )
                    extra = (
                        f" Did you mean {suggestion[0]!r}?" if suggestion
                        else " Add it to the vocabulary file if it is a genuinely new term."
                    )
                    fail("vocabulary-unknown",
                         f"{name}: {item!r} is not an established term.",
                         vocab_sev, (hint or "") + extra)
            return out

        text = str(value)

        pattern = spec.get("pattern")
        if pattern and not re.match(pattern, text):
            fail("field-format",
                 spec.get("pattern_message")
                 or f"Field {name!r} has value {text!r}, which does not match "
                    f"the required format.")

        max_len = spec.get("max_len")
        if max_len and len(text) > max_len:
            fail("field-too-long",
                 f"Field {name!r} is {len(text)} characters; the limit is {max_len}.")

        for char in spec.get("forbid_chars") or []:
            if char in text:
                fail("field-forbidden-char",
                     f"Field {name!r} must not contain {char!r}.")

        for token in spec.get("forbid") or []:
            if token in text:
                fail("field-forbidden", f"Field {name!r} must not contain {token!r}.")

        for token in spec.get("forbid_substrings") or []:
            if token.lower() in text.lower():
                fail("field-placeholder",
                     f"Field {name!r} still contains template text {token!r}.")

        return out

    def _check_body(self, doc: QmdDoc) -> list[Finding]:
        out: list[Finding] = []
        if not self.body:
            return out

        body_lines = list(doc.markdown_lines())
        joined = "\n".join(text for _, text in body_lines)

        for entry in self.body.get("required_headings") or []:
            pattern = entry["pattern"]
            if not any(re.match(pattern, text) for _, text in body_lines):
                out.append(Finding(
                    f"{self.id}.heading-missing",
                    Severity.parse(entry.get("severity", "error")), doc.relpath,
                    f"Required section matching {pattern!r} is missing.",
                    doc.body_start_line, entry.get("hint"),
                ))

        for entry in self.body.get("section_content") or []:
            after = entry["after"]
            index = next(
                (i for i, (_, text) in enumerate(body_lines) if re.match(after, text)),
                None,
            )
            if index is None:
                continue
            following = [
                (n, t) for n, t in body_lines[index + 1:] if t.strip()
            ]
            if not following:
                out.append(Finding(
                    f"{self.id}.section-empty",
                    Severity.parse(entry.get("severity", "error")), doc.relpath,
                    f"The section matching {after!r} has no content.",
                    body_lines[index][0], entry.get("hint"),
                ))
                continue
            lineno, text = following[0]
            if not re.match(entry["must_match"], text):
                out.append(Finding(
                    f"{self.id}.section-format",
                    Severity.parse(entry.get("severity", "error")), doc.relpath,
                    f"The first line of the section matching {after!r} does not "
                    f"match the expected format.",
                    lineno, entry.get("hint"),
                ))

        for entry in self.body.get("forbidden_patterns") or []:
            match = re.search(entry["pattern"], joined)
            if match:
                lineno = doc.body_start_line + joined[:match.start()].count("\n")
                out.append(Finding(
                    f"{self.id}.placeholder-text",
                    Severity.parse(entry.get("severity", "error")), doc.relpath,
                    entry.get("message", f"Found forbidden text {match.group(0)!r}."),
                    lineno, entry.get("hint"),
                ))

        return out


def _check_type(declared: str, name: str, value) -> str | None:
    """Return an error message, or None if the value is acceptable."""
    if declared == "str":
        if not isinstance(value, str):
            return (f"Field {name!r} must be text, found "
                    f"{type(value).__name__}. Wrap the value in quotes.")
    elif declared == "bool":
        if not isinstance(value, bool):
            return f"Field {name!r} must be true or false, found {_fmt(value)}."
    elif declared == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            return f"Field {name!r} must be a whole number, found {_fmt(value)}."
    elif declared == "list_of_str":
        if not isinstance(value, list):
            return f"Field {name!r} must be a list."
        bad = [v for v in value if not isinstance(v, str)]
        if bad:
            return f"Field {name!r} must contain only text entries."
    elif declared == "url":
        if not isinstance(value, str):
            return f"Field {name!r} must be a URL written as text."
        if value != value.strip():
            return (f"Field {name!r} has leading or trailing whitespace inside "
                    f"the quotes.")
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return (f"Field {name!r} must be a full URL starting with https://, "
                    f"found {value!r}.")
    elif declared == "relative_filename":
        if not isinstance(value, str):
            return f"Field {name!r} must be a filename written as text."
    return None


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return repr(value)
