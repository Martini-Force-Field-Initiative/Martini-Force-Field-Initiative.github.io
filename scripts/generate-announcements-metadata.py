#!/usr/bin/env python3
"""Generate docs/announcements/posts/_metadata.yml from the announcement posts.

That file serves two purposes at once:

  * Quarto directory metadata applied to every post in the folder
    (title-block-banner and friends), and
  * the data source for the homepage news feed, fetched at runtime by
    js/news-loader.js.

Usage
-----
    python scripts/generate-announcements-metadata.py          # write the file
    python scripts/generate-announcements-metadata.py --check  # verify only

``--check`` writes nothing and exits non-zero when the committed file differs
from what the sources imply. It is what CI runs.

The functions here are importable so the validator can reuse the same parsing
logic. One implementation, two callers: if the generator can read a post, the
announcement contract is satisfied by construction.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from datetime import datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO_ROOT / "docs" / "announcements" / "posts"
OUTPUT_FILE = POSTS_DIR / "_metadata.yml"

DATE_FORMAT = "%m/%d/%Y"
FEED_LENGTH = 4
DEFAULT_IMAGE = "/images/cell1.jpg"

BANNER = {
    "title-block-banner": "#FDF7F4",
    "title-block-banner-color": "body",
    "search": False,
}


class PostError(Exception):
    """A post that cannot be turned into a feed entry."""

    def __init__(self, path: Path, message: str):
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


def clean_string(value):
    if isinstance(value, str):
        return value.strip().strip("\"'")
    return value


def read_front_matter(path: Path) -> dict:
    """Parse the YAML front matter of a .qmd file.

    Front matter exists only if the first line is exactly ``---``; the block
    ends at the next such line. Splitting on ``---`` anywhere in the file (the
    previous approach) silently mis-parses any post whose body contains a
    horizontal rule.
    """
    text = path.read_text(encoding="utf-8").lstrip("﻿")
    lines = text.splitlines()

    if not lines or lines[0].strip() != "---":
        raise PostError(path, "file does not start with a '---' front-matter block")

    end = next(
        (i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")),
        None,
    )
    if end is None:
        raise PostError(path, "front matter is opened but never closed")

    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise PostError(path, f"front matter is not valid YAML: {exc}") from None

    if data is None:
        raise PostError(path, "front matter is empty")
    if not isinstance(data, dict):
        raise PostError(path, "front matter must be a mapping of key: value pairs")
    return data


def parse_date(value, path: Path) -> datetime:
    text = clean_string(value)
    if not text:
        raise PostError(path, "front matter has no 'date' field")
    try:
        return datetime.strptime(text, DATE_FORMAT)
    except (TypeError, ValueError):
        raise PostError(
            path,
            f"date {text!r} is not in MM/DD/YYYY format "
            f'(for example date: "02/12/2026")',
        ) from None


def image_path(value, post_dir: str) -> str:
    name = clean_string(value)
    if not name:
        return DEFAULT_IMAGE
    return f"/docs/announcements/posts/{post_dir}/{name}"


def load_announcements(posts_dir: Path = POSTS_DIR) -> list[dict]:
    """Read every post, newest first.

    Every failing post is reported, not just the first: a contributor fixing a
    batch of posts should see the whole list in one CI run.
    """
    announcements: list[dict] = []
    errors: list[PostError] = []

    for post_dir in sorted(posts_dir.iterdir()):
        if not post_dir.is_dir() or post_dir.name.startswith("_"):
            continue

        qmd_files = sorted(post_dir.glob("*.qmd"))
        if not qmd_files:
            continue
        qmd_file = qmd_files[0]

        try:
            metadata = read_front_matter(qmd_file)
            when = parse_date(metadata.get("date"), qmd_file)
            announcements.append({
                "_sort_key": when,
                "title": clean_string(metadata.get("title", "Untitled")),
                "description": clean_string(metadata.get("description", "")),
                "date": clean_string(metadata.get("date", "")),
                "image": image_path(metadata.get("image", ""), post_dir.name),
                "url": f"/docs/announcements/posts/{post_dir.name}/",
                "author": clean_string(metadata.get("author", "Unknown Author")),
            })
        except PostError as exc:
            errors.append(exc)

    if errors:
        raise SystemExit(
            "Cannot generate announcement metadata:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    announcements.sort(key=lambda a: a["_sort_key"], reverse=True)
    for entry in announcements:
        del entry["_sort_key"]
    return announcements


class _QuotingDumper(yaml.Dumper):
    """Double-quote every scalar *value*, but leave keys plain.

    Values are quoted because js/news-loader.js strips one layer of
    surrounding quotes; quoting keeps values containing ':' or '#' intact
    through that parser and through Quarto's own YAML reader.

    Keys are deliberately left unquoted: the feed parser recognises the start
    of the list by matching the literal line ``announcements:``, so a quoted
    key would make the whole feed invisible.
    """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, indentless=False)

    def represent_mapping(self, tag, mapping, flow_style=None):
        node = super().represent_mapping(tag, mapping, flow_style)
        for key_node, _ in node.value:
            if isinstance(key_node, yaml.ScalarNode):
                key_node.style = ""
        return node


def _represent_quoted_str(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


_QuotingDumper.add_representer(str, _represent_quoted_str)


def render_metadata(announcements: list[dict]) -> str:
    document = dict(BANNER)
    document["announcements"] = announcements[:FEED_LENGTH]
    return yaml.dump(
        document,
        Dumper=_QuotingDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=4096,
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check", action="store_true",
        help="Verify the committed file matches the sources; write nothing.",
    )
    parser.add_argument(
        "--output", type=Path, default=OUTPUT_FILE,
        help="Where to write (default: the announcements posts directory).",
    )
    args = parser.parse_args(argv)

    rendered = render_metadata(load_announcements())

    if args.check:
        existing = (
            args.output.read_text(encoding="utf-8")
            if args.output.exists() else ""
        )
        if existing == rendered:
            print(f"{args.output.relative_to(REPO_ROOT)} is up to date.")
            return 0
        diff = difflib.unified_diff(
            existing.splitlines(keepends=True),
            rendered.splitlines(keepends=True),
            fromfile="committed",
            tofile="regenerated",
        )
        sys.stdout.writelines(diff)
        print(
            "\n_metadata.yml is out of date. Run:\n"
            "    python scripts/generate-announcements-metadata.py",
            file=sys.stderr,
        )
        return 1

    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
