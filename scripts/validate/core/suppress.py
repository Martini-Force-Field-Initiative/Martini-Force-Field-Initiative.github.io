"""Per-file suppression of individual rules.

No rule set is right every time. Chemical nomenclature in an abstract can look
exactly like markdown link syntax, and a tutorial can have a good reason to
break a convention. Without an escape hatch, contributors learn to ignore CI
wholesale, which is worse than having no CI.

The directive is deliberately shaped to stay auditable:

    <!-- mffi-validate: ignore[link.broken-internal] chemical name, not a link -->
    ; mffi-validate: ignore[itp.non-integral-charge] counter-ion added separately

A reason is mandatory. A suppression without one is reported rather than
honoured, so "silence the check" always leaves a record of who decided what.
"""

from __future__ import annotations

import re
from pathlib import Path

DIRECTIVE_RE = re.compile(
    r"mffi-validate:\s*ignore\[(?P<rule>[a-z0-9._-]+)\]\s*(?P<reason>[^\n>;]*)"
)

MIN_REASON_WORDS = 2


def parse_directives(text: str) -> tuple[dict[str, str], list[tuple[str, int]]]:
    """Return (rule -> reason) and a list of (rule, line) lacking a reason."""
    honoured: dict[str, str] = {}
    unreasoned: list[tuple[str, int]] = []

    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in DIRECTIVE_RE.finditer(line):
            rule = match.group("rule")
            reason = match.group("reason").strip().rstrip("-").strip()
            if len(reason.split()) < MIN_REASON_WORDS:
                unreasoned.append((rule, lineno))
            else:
                honoured[rule] = reason

    return honoured, unreasoned


def apply(findings, root: Path):
    """Drop suppressed findings; report suppressions that give no reason."""
    from .finding import warning

    cache: dict[str, tuple[dict[str, str], list[tuple[str, int]]]] = {}
    kept = []
    extra = []

    for finding in findings:
        if finding.path not in cache:
            path = root / finding.path
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except (OSError, IsADirectoryError):
                text = ""
            cache[finding.path] = parse_directives(text)

        honoured, unreasoned = cache[finding.path]

        if finding.rule in honoured:
            continue
        kept.append(finding)

        for rule, lineno in unreasoned:
            if rule == finding.rule:
                extra.append(warning(
                    "validate.suppression-without-reason", finding.path,
                    f"Suppression of {rule!r} gives no reason, so it was not "
                    f"applied.", lineno,
                    "Write why the rule does not apply here, e.g. "
                    "'mffi-validate: ignore[rule.name] chemical name, not a link'.",
                ))

    seen = set()
    for finding in extra:
        key = (finding.rule, finding.path, finding.line)
        if key not in seen:
            seen.add(key)
            kept.append(finding)

    return kept
