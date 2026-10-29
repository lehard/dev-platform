#!/usr/bin/env python3
"""Disposable local read cache for GitHub GET responses.

GitHub stays the only source of truth. An entry holds one complete response page with its ETag and
is revalidated with a conditional request on every read; a 304 answer is not charged against the
primary REST limit and returns the *whole* stored page, so no cursor can hide a change. Only raw
responses are stored: assessments, ages and claim expiry are always recomputed by the caller.
Deleting the file never changes a result. A corrupt or inconsistent file raises
``GithubReadCacheError`` naming the file and the reset command; nothing is silently re-read in its place.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from _platform_common import run_github_with_retry
from _platform_common import run_git

VERSION = 1
CACHE_NAME = "github-read-cache.json"
_LINK_NEXT = re.compile(r'<([^>]+)>;\s*rel="next"')
_STATUS = re.compile(r"^HTTP/\S+\s+(\d{3})")
_lock = threading.Lock()


class GithubReadError(RuntimeError):
    """A GitHub read failed (not a cache problem)."""


class GithubReadCacheError(RuntimeError):
    """The cache file is corrupt or inconsistent; the message names it and how to reset it."""


def cache_path(root: Path) -> Path:
    common = run_git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root).stdout.strip()
    if not common:
        raise GithubReadCacheError(f"cannot locate the git common directory of {root} for the GitHub read cache")
    return Path(common) / "dev-platform" / CACHE_NAME


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _corrupt(path: Path, cause: str) -> GithubReadCacheError:
    return GithubReadCacheError(f"GitHub read cache {path} is corrupt ({cause}); delete it to reset: rm {path}")


def _load(path: Path) -> dict[str, Any]:
    """The validated file content; an absent file is an empty cache."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"version": VERSION, "pages": {}}
    except OSError as exc:
        raise _corrupt(path, f"unreadable: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _corrupt(path, f"not JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != VERSION:
        raise _corrupt(path, f"unsupported version {data.get('version') if isinstance(data, dict) else type(data).__name__}")
    for section, fields in (("pages", ("etag", "digest", "body", "next")),):
        entries = data.get(section)
        if not isinstance(entries, dict):
            raise _corrupt(path, f"{section} is not an object")
        for key, entry in entries.items():
            if not isinstance(entry, dict) or set(entry) != set(fields):
                raise _corrupt(path, f"{section} entry {key!r} has unexpected fields")
    return data


def _store(path: Path, section: str, key: str, entry: dict[str, Any]) -> None:
    """Atomically add one entry, merging with whatever other processes wrote meanwhile."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "a") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        data = _load(path)
        data[section][key] = entry
        fd, temp = tempfile.mkstemp(dir=path.parent, prefix=CACHE_NAME + ".")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, separators=(",", ":"))
            os.replace(temp, path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp)
            raise


def parse_response(stdout: str) -> tuple[int, dict[str, str], str]:
    """``(status, lower-cased headers, body)`` of ``gh api --include`` output."""
    head, separator, body = stdout.partition("\n\n")
    if not separator:
        head, separator, body = stdout.replace("\r\n", "\n").partition("\n\n")
    lines = head.replace("\r\n", "\n").split("\n")
    match = _STATUS.match(lines[0]) if lines else None
    if not match:
        raise GithubReadError(f"unrecognised GitHub response status line: {lines[0][:80] if lines else ''!r}")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, colon, value = line.partition(":")
        if colon:
            headers[name.strip().lower()] = value.strip()
    return int(match.group(1)), headers, body


DEFAULT_PAGE_SIZE = 30  # GitHub's page size when the URL names no ``per_page``


def page_size(url: str) -> int:
    """The page size ``url`` asks for; a ``per_page`` that is not an integer from 1 to 100 is an error, not a guess."""
    values = parse_qs(urlsplit(url).query).get("per_page")
    if values is None:
        return DEFAULT_PAGE_SIZE
    if len(values) != 1 or not values[0].isdigit() or not 1 <= int(values[0]) <= 100:
        raise GithubReadError(f"cannot determine the page size of {url}: per_page must be one integer from 1 to 100")
    return int(values[0])


def _may_have_unseen_next_page(url: str, entry: dict[str, Any]) -> bool:
    return entry["next"] is None and isinstance(entry["body"], list) and len(entry["body"]) >= page_size(url)


def _page(root: Path, path: Path, url: str, run: Callable[..., Any]) -> tuple[Any, str | None]:
    with _lock:
        entry = _load(path)["pages"].get(url)
    if entry is not None and _digest(entry["body"]) != entry["digest"]:
        raise _corrupt(path, f"body of {url} does not match its digest")
    command = ["gh", "api", "-i"]
    # A stored 304 answer carries the ``next`` link of the old 200. A list page that is full and has no stored ``next``
    # may have grown a following page without changing itself, so only that page is re-read unconditionally.
    unconditional = entry is not None and _may_have_unseen_next_page(url, entry)
    if entry is not None and not unconditional:
        command += ["-H", f"If-None-Match: {entry['etag']}"]
    result = run([*command, url], cwd=root)
    try:
        status, headers, body = parse_response(result.stdout or "")
    except GithubReadError:
        raise GithubReadError((result.stderr or "").strip() or f"gh failed reading {url}") from None
    if status == 304:
        if entry is None or unconditional:
            raise GithubReadError(f"GitHub answered 304 to an unconditional request for {url}")
        return entry["body"], entry["next"]
    if status != 200 or result.returncode:
        raise GithubReadError((result.stderr or "").strip() or f"GitHub answered {status} for {url}")
    try:
        parsed = json.loads(body) if body.strip() else None
    except json.JSONDecodeError as exc:
        raise GithubReadError(f"GitHub returned non-JSON for {url}") from exc
    link = _LINK_NEXT.search(headers.get("link", ""))
    next_url = link.group(1) if link else None
    etag = headers.get("etag")
    if etag:
        # Written only after the page is fully received and parsed: a failed read keeps the old entry.
        with _lock:
            _store(path, "pages", url, {"etag": etag, "digest": _digest(parsed), "body": parsed, "next": next_url})
    return parsed, next_url


def get_pages(root: Path, endpoint: str, *, run: Callable[..., Any] = run_github_with_retry) -> list[Any]:
    """The response pages of ``endpoint`` in order, following ``rel="next"``; every page is revalidated by ETag."""
    path = cache_path(root)
    body, next_url = _page(root, path, endpoint, run)
    pages = [body]
    seen = {endpoint}
    while next_url:
        if next_url in seen:
            raise GithubReadError(f"pagination of {endpoint} loops at {next_url}")
        seen.add(next_url)
        body, next_url = _page(root, path, next_url, run)
        pages.append(body)
    return pages


def get_json(root: Path, endpoint: str, *, paginate: bool = False, run: Callable[..., Any] = run_github_with_retry) -> Any:
    """GET ``endpoint`` (path below the API root).

    ``paginate`` concatenates array pages, like ``gh api --paginate``; a page that is not an array is an error.
    """
    if not paginate:
        return _page(root, cache_path(root), endpoint, run)[0]
    items: list[Any] = []
    for page in get_pages(root, endpoint, run=run):
        if not isinstance(page, list):
            raise GithubReadError(f"paginated read of {endpoint} returned a page that is not an array")
        items.extend(page)
    return items


def cached_gh_json(root: Path, *args: str, run: Callable[..., Any] = run_github_with_retry) -> Any:
    """``gh_json``-shaped read: only ``api [--paginate] <path>`` GETs are supported; anything else is refused."""
    rest = list(args)
    if not rest or rest[0] != "api":
        raise GithubReadError(f"the GitHub read cache serves only 'gh api' reads, not {' '.join(args)!r}")
    rest = rest[1:]
    paginate = bool(rest) and rest[0] == "--paginate"
    if paginate:
        rest = rest[1:]
    if len(rest) != 1:
        raise GithubReadError(f"the GitHub read cache serves only 'gh api [--paginate] <path>' reads, not {' '.join(args)!r}")
    return get_json(root, rest[0], paginate=paginate, run=run)
