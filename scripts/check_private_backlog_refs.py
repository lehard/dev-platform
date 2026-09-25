#!/usr/bin/env python3
"""Reject direct private Backlog Issue references in a public candidate tree.

This intentionally reports opaque file fingerprints, because a file name can
itself contain a private Issue number. It does not inspect Git history.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import tomllib
from pathlib import Path


class PrivacyGuardError(RuntimeError):
    pass


def private_reference_pattern(repository: str) -> re.Pattern[str]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise PrivacyGuardError("invalid configured Backlog repository")
    owner, name = repository.split("/", 1)
    return re.compile(
        rf"(?:{re.escape(owner)}/{re.escape(name)}\s*#\s*[1-9][0-9]*"
        rf"|(?:https?://)?(?:www\.)?github\.com/{re.escape(owner)}/{re.escape(name)}/issues/[1-9][0-9]*"
        rf"|(?<![A-Za-z0-9_.\-/]){re.escape(name)}/issues/[1-9][0-9]*)",
        re.IGNORECASE,
    )


def candidate_paths(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, capture_output=True, check=False,
    )
    if result.returncode:
        raise PrivacyGuardError("cannot list candidate files")
    return [root / name.decode("utf-8", errors="surrogateescape") for name in result.stdout.split(b"\0") if name]


def violations(root: Path, repository: str) -> list[str]:
    pattern = private_reference_pattern(repository)
    hits: list[str] = []
    for path in candidate_paths(root):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise PrivacyGuardError("cannot read a candidate file") from exc
        if b"\0" in raw:
            continue
        try:
            content = raw.decode("utf-8")
        except UnicodeError:
            continue
        relative = path.relative_to(root).as_posix()
        if pattern.search(relative) or pattern.search(content):
            hits.append(hashlib.sha256(relative.encode("utf-8")).hexdigest()[:12])
    return sorted(set(hits))


def publication_text_violation(root: Path, repository: str, extra_text: list[str]) -> bool:
    pattern = private_reference_pattern(repository)
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True, check=False)
    commits = subprocess.run(
        ["git", "log", "--format=%B", "origin/main..HEAD"], cwd=root, capture_output=True, text=True, check=False,
    )
    if branch.returncode or commits.returncode:
        raise PrivacyGuardError("cannot inspect candidate branch and commit messages")
    return any(pattern.search(value) for value in [branch.stdout, commits.stdout, *extra_text])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--repository", help="Private Backlog repository for checkouts without a local source contract")
    parser.add_argument("--text", action="append", default=[], help="Additional proposed public text, such as a PR title or body")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.repository:
            repository = args.repository
        else:
            config = tomllib.loads((root / ".dev-platform.toml").read_text(encoding="utf-8"))
            repository = config["development_backlog"]["repository"]
        if not isinstance(repository, str):
            raise PrivacyGuardError("missing configured Backlog repository")
        hits = violations(root, repository)
        text_hit = publication_text_violation(root, repository, args.text)
    except (OSError, KeyError, tomllib.TOMLDecodeError, PrivacyGuardError) as exc:
        parser.exit(2, f"private-reference guard cannot run: {exc}\n")
    if hits or text_hit:
        detail = f"{len(hits)} candidate file(s)" + (" and public branch/commit/PR text" if text_hit else "")
        parser.exit(1, f"private-reference guard found direct Issue identifiers in {detail}; opaque file IDs: {', '.join(hits[:10])}\n")
    print("private-reference guard: current candidate files contain no supported direct private Issue references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
