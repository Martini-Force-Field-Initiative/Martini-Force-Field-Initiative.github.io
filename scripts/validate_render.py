#!/usr/bin/env python3
"""Turn Quarto render warnings into failures.

`quarto render` exits 0 even when it cannot resolve a link target or a
cross-reference. A bare render check therefore passes while shipping broken
navigation -- exactly the failure mode this framework exists to prevent.

Usage:
    python -m scripts.validate_render render.log
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Patterns Quarto emits that indicate genuinely broken output. Each maps to a
# rule id so the annotation is searchable alongside the other checks.
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("render.unresolved-link",
     re.compile(r"Unable to resolve link target:\s*(?P<detail>.+)", re.I)),
    ("render.unresolved-crossref",
     re.compile(r"Unable to resolve crossref\s*(?P<detail>.+)", re.I)),
    ("render.missing-file",
     re.compile(r"(?P<detail>.*\bdoes not exist\b.*)", re.I)),
    ("render.pandoc-warning",
     re.compile(r"\[WARNING\]\s*(?P<detail>.+)")),
]

# Quarto warnings that are noise rather than defects.
IGNORE = re.compile(
    r"deprecated|update available|available at https|"
    r"was not found in the theme",
    re.I,
)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    log_path = Path(argv[1])
    if not log_path.exists():
        print(f"error: {log_path} does not exist", file=sys.stderr)
        return 2

    text = log_path.read_text(encoding="utf-8", errors="replace")
    findings: list[tuple[str, str]] = []

    for line in text.splitlines():
        if IGNORE.search(line):
            continue
        for rule, pattern in PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append((rule, match.group("detail").strip()))
                break

    if not findings:
        print("Quarto render produced no link or cross-reference warnings.")
        return 0

    seen = set()
    for rule, detail in findings:
        if (rule, detail) in seen:
            continue
        seen.add((rule, detail))
        escaped = detail.replace("%", "%25").replace("\n", "%0A")
        print(f"::error title={rule}::{escaped}")

    print(
        f"\n{len(seen)} render problem(s). Quarto exits 0 on these, so they "
        f"would otherwise ship silently.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
