#!/usr/bin/env python3
"""Check that external and download links still resolve.

Kept out of the pull-request gate on purpose. There are roughly 1700 external
URLs, many pointing at publishers that block automated requests, and a
contributor must never be blocked because a third-party site is having a bad
day. This runs on a schedule instead and reports into a tracking issue.

The exception is our own library. A 403 or 404 from the S3 bucket or the
CloudFront distribution means the object is missing or not public -- a
download the portal advertises but cannot deliver. Those are errors.

Usage:
    python -m scripts.validate_links --scope all
    python -m scripts.validate_links --scope changed --changed-only changed.txt
"""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.validate.core.discovery import iter_qmd_files, repo_root  # noqa: E402
from scripts.validate.core.links import classify, extract_links  # noqa: E402
from scripts.validate.core.qmd import parse_qmd  # noqa: E402

OWNED_HOSTS = {
    "cgmartini-library.s3.ca-central-1.amazonaws.com",
    "d3ebrx6qufncts.cloudfront.net",
}

# Publishers that routinely refuse automated requests. A non-2xx from these
# says nothing about whether the link works in a browser.
BOT_HOSTILE = {
    "pubs.acs.org", "onlinelibrary.wiley.com", "sciencedirect.com",
    "www.sciencedirect.com", "link.springer.com", "www.nature.com",
    "pubs.rsc.org", "journals.aps.org", "www.tandfonline.com",
    "academic.oup.com", "www.science.org", "iopscience.iop.org",
    "www.pnas.org", "doi.org", "dx.doi.org",
}

TIMEOUT = 10
WORKERS = 8
USER_AGENT = "Mozilla/5.0 (compatible; MFFI-link-check/1.0; +https://cgmartini.nl)"


def probe(url: str) -> tuple[int | None, str | None]:
    """Return (status, error). HEAD first, GET as a fallback."""
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(
            url, method=method, headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return response.status, None
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405, 501):
                continue          # some servers reject HEAD but allow GET
            return exc.code, None
        except urllib.error.URLError as exc:
            return None, str(exc.reason)
        except (TimeoutError, ConnectionError) as exc:
            return None, str(exc)
        except Exception as exc:                      # noqa: BLE001
            return None, f"{type(exc).__name__}: {exc}"
    return None, "no response"


def collect(root: Path, changed: set[str] | None) -> dict[str, list[tuple[str, int]]]:
    """Map each external URL to the (file, line) places it appears."""
    urls: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for path in iter_qmd_files(root):
        rel = path.relative_to(root).as_posix()
        if changed is not None and rel not in changed:
            continue
        doc = parse_qmd(path, root)
        for link in extract_links(doc.markdown_lines()):
            if classify(link.target) == "external":
                urls[link.target].append((rel, link.line))
    return urls


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scope", choices=("all", "owned", "changed"), default="owned")
    parser.add_argument("--changed-only", type=Path)
    parser.add_argument("--format", choices=("console", "github"), default="console")
    args = parser.parse_args(argv)

    root = repo_root(Path.cwd())

    changed = None
    if args.scope == "changed":
        if not args.changed_only or not args.changed_only.exists():
            print("error: --scope changed requires --changed-only FILE", file=sys.stderr)
            return 2
        changed = {
            line.strip() for line in
            args.changed_only.read_text(encoding="utf-8").splitlines() if line.strip()
        }

    urls = collect(root, changed)

    from urllib.parse import urlparse
    if args.scope == "owned":
        urls = {u: v for u, v in urls.items()
                if urlparse(u).netloc.lower() in OWNED_HOSTS}

    if not urls:
        print("No links to check.")
        return 0

    print(f"Checking {len(urls)} unique URL(s)...", file=sys.stderr)

    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(probe, url): url for url in sorted(urls)}
        for future in concurrent.futures.as_completed(futures):
            url = futures[future]
            status, error = future.result()
            host = urlparse(url).netloc.lower()
            owned = host in OWNED_HOSTS

            if status and 200 <= status < 400:
                continue
            if not owned and host in BOT_HOSTILE and status in (401, 403, 405, 429):
                continue          # blocked bot, not a dead link
            if not owned and status in (401, 403, 429):
                continue

            failures.append((url, status, error, owned, urls[url]))

    if not failures:
        print(f"All {len(urls)} link(s) resolve.")
        return 0

    hard = 0
    for url, status, error, owned, places in sorted(failures):
        detail = f"HTTP {status}" if status else (error or "no response")
        severity = "error" if owned else "warning"
        if owned:
            hard += 1
        where = places[0]
        if args.format == "github":
            hint = (
                " The portal advertises this download but the object is "
                "missing or not public in the library."
                if owned else ""
            )
            print(f"::{severity} file={where[0]},line={where[1]},"
                  f"title=link.unreachable::{url} returned {detail}.{hint}")
        else:
            print(f"[{severity}] {detail:<18} {url}")
            for path, line in places[:3]:
                print(f"           {path}:{line}")

    print(f"\n{len(failures)} unreachable link(s); {hard} in our own library.",
          file=sys.stderr)
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
