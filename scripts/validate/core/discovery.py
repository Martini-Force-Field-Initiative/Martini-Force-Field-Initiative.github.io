"""Locating the files a schema applies to.

Two subtleties worth stating, because getting either wrong makes the whole
framework misleading:

1. Build output must never be scanned. `_site/`, `_freeze/` and `.quarto/`
   contain copies of real content; findings there are noise and, worse, would
   report paths that do not exist in the source tree.

2. `--changed-only` narrows which files are checked *against their own
   schema*. It must not narrow the cross-cutting graph checks (navigation,
   orphans, link targets), because deleting file A breaks a link in an
   unchanged file B.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

EXCLUDED_DIRS = {
    "_site", "_freeze", ".quarto", ".git", ".venv", "node_modules",
    "_extensions", "__pycache__",
}


def repo_root(start: Path | None = None) -> Path:
    """Walk up until we find the marker files that identify this repository."""
    current = (start or Path(__file__)).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "_quarto.yml").exists() and (candidate / "docs").is_dir():
            return candidate
    raise RuntimeError(
        "Could not locate the repository root (no _quarto.yml with a docs/ "
        "directory found in any parent)."
    )


def is_excluded(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in EXCLUDED_DIRS for part in parts)


def iter_qmd_files(root: Path):
    """Every source `.qmd` in the repository, build output excluded."""
    for path in sorted(root.rglob("*.qmd")):
        if not is_excluded(path, root):
            yield path


def match_globs(root: Path, patterns: list[str],
                exclude: list[str] | None = None) -> list[Path]:
    """Resolve a schema's `applies_to` / `exclude` globs to real files."""
    exclude = exclude or []
    seen: dict[str, Path] = {}

    for pattern in patterns:
        for path in root.glob(pattern):
            if not path.is_file() or is_excluded(path, root):
                continue
            rel = path.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, ex) for ex in exclude):
                continue
            seen[rel] = path

    return [seen[key] for key in sorted(seen)]


def read_changed_list(path: Path) -> set[str]:
    """Read a newline-delimited list of repo-relative paths from a PR diff."""
    entries = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.add(Path(line).as_posix())
    return entries
