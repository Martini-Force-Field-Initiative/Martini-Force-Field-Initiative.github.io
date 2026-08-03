"""Rendering of findings.

Three output modes:

* ``console``  -- for local `make validate`
* ``github``   -- workflow commands that GitHub renders inline on the PR diff
* ``json``     -- machine-readable, used by the scheduled link-health job

Plus a markdown job summary, which is what makes CI read like a curation
report rather than a linter dump.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

from .finding import Finding, Severity

# GitHub silently truncates at ~50 annotations per run, so cap per rule and
# push the full list to the job summary instead.
MAX_ANNOTATIONS_PER_RULE = 10

_COLOR = {
    Severity.ERROR: "\033[31m",
    Severity.WARNING: "\033[33m",
    Severity.NOTICE: "\033[36m",
}
_RESET = "\033[0m"


def counts(findings: list[Finding]) -> Counter:
    return Counter(f.severity for f in findings)


def has_errors(findings: list[Finding]) -> bool:
    return any(f.severity is Severity.ERROR for f in findings)


def render_console(findings: list[Finding], *, color: bool = True) -> str:
    if not findings:
        return "All checks passed.\n"

    out: list[str] = []
    by_path: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_path[finding.path].append(finding)

    for path in sorted(by_path):
        out.append(f"\n{path}")
        for finding in sorted(by_path[path], key=Finding.sort_key):
            tint = _COLOR[finding.severity] if color else ""
            reset = _RESET if color else ""
            where = f"{finding.line}" if finding.line else "-"
            out.append(
                f"  {where:>5}  {tint}{finding.severity.label:<7}{reset} "
                f"{finding.message}  [{finding.rule}]"
            )
            if finding.hint:
                out.append(f"         → {finding.hint}")

    tally = counts(findings)
    out.append(
        f"\n{tally[Severity.ERROR]} error(s), "
        f"{tally[Severity.WARNING]} warning(s), "
        f"{tally[Severity.NOTICE]} notice(s)."
    )
    return "\n".join(out) + "\n"


def render_github(findings: list[Finding]) -> str:
    """Emit ::error / ::warning / ::notice workflow commands.

    GitHub renders these as inline comments on the changed lines, which is the
    difference between a contributor seeing the fix on the offending line and
    a contributor scrolling a CI log.
    """
    lines: list[str] = []
    seen_per_rule: Counter = Counter()

    for finding in sorted(findings, key=Finding.sort_key):
        seen_per_rule[finding.rule] += 1
        if seen_per_rule[finding.rule] > MAX_ANNOTATIONS_PER_RULE:
            continue

        command = {
            Severity.ERROR: "error",
            Severity.WARNING: "warning",
            Severity.NOTICE: "notice",
        }[finding.severity]

        message = finding.message
        if finding.hint:
            message = f"{message} — {finding.hint}"

        parts = [f"file={finding.path}"]
        if finding.line:
            parts.append(f"line={finding.line}")
        parts.append(f"title={finding.rule}")
        lines.append(f"::{command} {','.join(parts)}::{_escape(message)}")

    for rule, total in seen_per_rule.items():
        if total > MAX_ANNOTATIONS_PER_RULE:
            hidden = total - MAX_ANNOTATIONS_PER_RULE
            lines.append(
                f"::notice title={rule}::{hidden} further occurrence(s) not "
                f"annotated; see the job summary for the full list."
            )
    return "\n".join(lines) + ("\n" if lines else "")


def _escape(text: str) -> str:
    """GitHub workflow-command escaping."""
    return (
        text.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
        .replace(":", "%3A")
        .replace(",", "%2C")
    )


def render_json(findings: list[Finding]) -> str:
    return json.dumps(
        [
            {
                "rule": f.rule,
                "severity": f.severity.label,
                "path": f.path,
                "line": f.line,
                "message": f.message,
                "hint": f.hint,
            }
            for f in sorted(findings, key=Finding.sort_key)
        ],
        indent=2,
    ) + "\n"


def render_summary(findings: list[Finding], checked: dict[str, int]) -> str:
    """Markdown job summary, grouped by contribution type."""
    tally = counts(findings)
    verdict = "❌ Validation failed" if tally[Severity.ERROR] else "✅ Validation passed"

    out = [f"## {verdict}", ""]

    if checked:
        out.append("| Contribution type | Files checked |")
        out.append("|---|---:|")
        for name, count in sorted(checked.items()):
            out.append(f"| {name} | {count} |")
        out.append("")

    out.append(
        f"**{tally[Severity.ERROR]} error(s)**, "
        f"{tally[Severity.WARNING]} warning(s), "
        f"{tally[Severity.NOTICE]} notice(s)."
    )
    out.append("")

    if not findings:
        out.append("No problems found.")
        return "\n".join(out) + "\n"

    for severity in (Severity.ERROR, Severity.WARNING, Severity.NOTICE):
        group = [f for f in findings if f.severity is severity]
        if not group:
            continue
        out.append(f"### {severity.label.title()}s ({len(group)})")
        out.append("")
        out.append("| File | Line | Rule | Problem | Fix |")
        out.append("|---|---:|---|---|---|")
        for finding in sorted(group, key=Finding.sort_key):
            out.append(
                f"| `{finding.path}` | {finding.line or ''} | `{finding.rule}` "
                f"| {_md(finding.message)} | {_md(finding.hint or '')} |"
            )
        out.append("")

    return "\n".join(out) + "\n"


def _md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
