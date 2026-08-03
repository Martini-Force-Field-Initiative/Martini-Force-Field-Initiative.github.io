"""Command-line entry point.

    python -m scripts.validate                    # everything
    python -m scripts.validate --only announcements
    python -m scripts.validate --changed-only changed.txt --format github

Exit codes:
    0  clean (warnings and notices do not fail)
    1  at least one error
    2  the validator itself is misconfigured (bad schema, unknown rule)

Exit code 2 is deliberately distinct: a framework that silently skips checks
because a schema failed to load would be worse than no framework at all.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Allow `python scripts/validate` as well as `python -m scripts.validate`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "scripts.validate"

from .core import report, suppress
from .core.discovery import (
    match_globs,
    read_changed_list,
    repo_root,
)
from .core.finding import Finding, Severity, notice
from .core.qmd import parse_qmd
from .core.schema import Schema, SchemaError
from . import rules

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

# Pseudo-type for the cross-cutting structural pass, which has no schema
# because it validates relationships between files rather than fields.
SITE_CHECK = "site"

# Pseudo-type for tutorials and tool cards, whose contract is the shape of
# their fenced divs rather than a set of front-matter fields.
STRUCTURE_CHECK = "structure"


@dataclass
class Context:
    """Shared state passed to every relational rule."""

    root: Path
    schemas: dict[str, Schema]
    docs_by_schema: dict[str, list] = field(default_factory=dict)
    shared: dict = field(default_factory=dict)

    def all_docs_for(self, schema_id: str) -> list:
        """Every document of a type, regardless of --changed-only.

        Cross-file rules (duplicate DOIs, orphan detection) must see the whole
        corpus even when only a few files changed.
        """
        return self.docs_by_schema.get(schema_id, [])


def load_schemas() -> dict[str, Schema]:
    schemas = {}
    for path in sorted(SCHEMA_DIR.glob("*.yml")):
        schema = Schema.load(path)
        if schema.id in schemas:
            raise SchemaError(f"duplicate schema id {schema.id!r} in {path}")
        schemas[schema.id] = schema
    return schemas


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.validate",
        description="Validate MFFI portal contributions against their "
                    "declared contracts.",
    )
    parser.add_argument(
        "--only", action="append", metavar="TYPE",
        help="Restrict to one contribution type (repeatable). "
             "Use --list-types to see the available names.",
    )
    parser.add_argument(
        "--changed-only", metavar="FILE", type=Path,
        help="File containing newline-delimited paths changed by the pull "
             "request. Per-file checks are limited to these; cross-file "
             "checks still run over the whole repository.",
    )
    parser.add_argument(
        "--format", choices=("console", "github", "json"), default="console",
    )
    parser.add_argument(
        "--summary-file", metavar="FILE", type=Path,
        help="Write a markdown job summary here (typically $GITHUB_STEP_SUMMARY).",
    )
    parser.add_argument(
        "--list-types", action="store_true",
        help="List the available contribution types and exit.",
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Disable coloured console output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        root = repo_root(Path.cwd())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        schemas = load_schemas()
        rules.load_all()
    except SchemaError as exc:
        print(f"schema error: {exc}", file=sys.stderr)
        return 2

    if args.list_types:
        for schema in schemas.values():
            print(f"{schema.id:<16} {schema.label}")
        print(f"{SITE_CHECK:<16} Site-wide structure (navigation, links, assets)")
        print(f"{STRUCTURE_CHECK:<16} Tutorials and tool cards (fenced-div structure)")
        return 0

    # "site" is not a contribution type with a schema; it is the cross-cutting
    # structural pass (navigation, links, assets, repository hygiene).
    available = set(schemas) | {SITE_CHECK, STRUCTURE_CHECK}

    requested = set(args.only) if args.only else available
    unknown = requested - available
    if unknown:
        print(
            f"error: unknown contribution type(s) {sorted(unknown)}; "
            f"available types are {sorted(available)}",
            file=sys.stderr,
        )
        return 2

    selected = requested & set(schemas)
    run_site_checks = SITE_CHECK in requested
    run_structure_checks = STRUCTURE_CHECK in requested

    changed: set[str] | None = None
    if args.changed_only:
        if not args.changed_only.exists():
            print(f"error: {args.changed_only} does not exist", file=sys.stderr)
            return 2
        changed = read_changed_list(args.changed_only)

    ctx = Context(root=root, schemas=schemas)
    findings: list[Finding] = []
    checked: dict[str, int] = {}

    # Parse every document of every selected type first, so cross-file rules
    # can see the whole corpus even under --changed-only.
    for schema_id in sorted(selected):
        schema = schemas[schema_id]
        paths = match_globs(root, schema.applies_to, schema.exclude)
        ctx.docs_by_schema[schema_id] = [parse_qmd(p, root) for p in paths]

    for schema_id in sorted(selected):
        schema = schemas[schema_id]
        docs = ctx.docs_by_schema[schema_id]

        targets = docs
        if changed is not None:
            targets = [d for d in docs if d.relpath in changed]

        checked[schema.label] = len(targets)

        for doc in targets:
            findings.extend(schema.check(doc))
            for rule_name in schema.rules:
                try:
                    func = rules.get(rule_name)
                except KeyError as exc:
                    print(f"schema error: {exc}", file=sys.stderr)
                    return 2
                if doc.fm_present and not doc.fm_error:
                    findings.extend(func(doc, ctx))

    # Site-wide checks always run over the whole repository, even under
    # --changed-only: deleting file A breaks a link in unchanged file B.
    if run_site_checks:
        from .rules.site import check_site
        findings.extend(check_site(ctx))
        checked["Site-wide structure"] = len(ctx.shared.get("all_site_docs", []))

    if run_structure_checks:
        from .rules.structure import check_structure
        findings.extend(check_structure(ctx))
        checked["Tutorials and tool cards"] = len(
            list((ctx.root / "docs" / "downloads" / "tools").glob("*.qmd"))
        )

    if changed is not None and not any(checked.values()):
        findings.append(notice(
            "validate.no-matching-changes", ".",
            "No changed files matched a known contribution type.",
        ))

    findings = suppress.apply(findings, root)

    _emit(args, findings, checked)
    return 1 if report.has_errors(findings) else 0


def _emit(args, findings: list[Finding], checked: dict[str, int]) -> None:
    if args.format == "github":
        sys.stdout.write(report.render_github(findings))
    elif args.format == "json":
        sys.stdout.write(report.render_json(findings))
    else:
        color = not args.no_color and sys.stdout.isatty() and not os.environ.get("CI")
        sys.stdout.write(report.render_console(findings, color=color))

    if args.summary_file:
        args.summary_file.parent.mkdir(parents=True, exist_ok=True)
        with args.summary_file.open("a", encoding="utf-8") as handle:
            handle.write(report.render_summary(findings, checked))

    if args.format == "github":
        tally = report.counts(findings)
        sys.stderr.write(
            f"{tally[Severity.ERROR]} error(s), "
            f"{tally[Severity.WARNING]} warning(s), "
            f"{tally[Severity.NOTICE]} notice(s).\n"
        )


if __name__ == "__main__":
    raise SystemExit(main())
