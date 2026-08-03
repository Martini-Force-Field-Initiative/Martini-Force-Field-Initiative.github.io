"""Lint GROMACS topology (.itp) files carrying Martini parameters.

    python -m scripts.lint_itp martini_POPC.itp [more.itp ...]
    python -m scripts.lint_itp path/to/directory

The `.itp` files themselves are not kept in this repository -- they live in
the Martini download library, and a contributor shares them with the
parameters editors as a link. So this cannot run as part of the pull-request
gate the way the `.qmd` checks do. It is a tool instead: a contributor runs it
on their own files before proposing them, and a reviewer runs it on the files
they were sent.

Scope is the same as the linter it wraps: syntax, internal consistency, and
force-field compatibility. Whether the parameters reproduce reality is expert
review's question, not this program's.

Exit codes:
    0  no errors (warnings do not fail)
    1  at least one error
    2  bad usage, or a path that cannot be read
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow `python scripts/lint_itp.py` as well as `python -m scripts.lint_itp`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "scripts"

from .validate.core import report
from .validate.core.finding import Finding, error, warning
from .validate.core.itp import lint


def collect(paths: list[Path]) -> list[Path]:
    """Expand directories to the .itp files inside them."""
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.itp")))
        else:
            files.append(path)
    return files


def check_file(path: Path) -> list[Finding]:
    label = path.as_posix()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SystemExit(f"error: cannot read {label}: {exc}")

    findings: list[Finding] = []

    if not _has_header_comment(text):
        findings.append(warning(
            "parameters.itp-no-header", label,
            "The file has no leading comment block.", 1,
            "Start the file with a ';' comment naming the molecule, the "
            "Martini version, and the paper to cite. Users read this header "
            "long after the contribution is forgotten.",
        ))

    for issue in lint(text):
        builder = error if issue.severity == "error" else warning
        findings.append(builder(
            issue.rule, label, issue.message, issue.line, issue.hint,
        ))

    return findings


def _has_header_comment(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        return stripped.startswith(";")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.lint_itp",
        description="Lint Martini .itp topologies for syntax, internal "
                    "consistency, and force-field compatibility.",
    )
    parser.add_argument(
        "paths", nargs="+", type=Path, metavar="PATH",
        help="One or more .itp files, or directories to search recursively.",
    )
    parser.add_argument(
        "--format", choices=("console", "github", "json"), default="console",
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Disable coloured console output.",
    )
    args = parser.parse_args(argv)

    files = collect(args.paths)
    missing = [p for p in files if not p.is_file()]
    if missing:
        for path in missing:
            print(f"error: {path} does not exist", file=sys.stderr)
        return 2
    if not files:
        print("error: no .itp files found in the given paths", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for path in files:
        findings.extend(check_file(path))

    if args.format == "github":
        sys.stdout.write(report.render_github(findings))
    elif args.format == "json":
        sys.stdout.write(report.render_json(findings))
    else:
        color = (
            not args.no_color
            and sys.stdout.isatty()
            and not os.environ.get("CI")
        )
        sys.stdout.write(report.render_console(findings, color=color))
        print(f"Checked {len(files)} file(s).")

    return 1 if report.has_errors(findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
