#!/usr/bin/env python3
"""Bounded structural check for documentation/instruction content.

This backs the `docs-semantic` risk class: a semantic-preserving wording
refactor to `AGENTS.md`, `docs/**`, `openspec/**` prose or a rendered template
must not by itself need the full Python suite, but it must still fail on a
broken local link destination or a dropped heading anchor.

Deliberately narrow: relative link destinations must exist, and `#fragment`
references must resolve to an actual heading in the target (or current) file
using a GitHub-compatible slug. External links and code-fence contents are not
checked. Duplicate-heading disambiguation suffixes (`-1`, `-2`, ...) are not
modeled; a fragment that matches the base slug of a duplicated heading is
accepted.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$", re.MULTILINE)
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
EXCLUDED_DIRS = {".git", "node_modules", ".claude"}


def slugify(heading: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def heading_slugs(text: str) -> set[str]:
    stripped = FENCE_RE.sub("", text)
    return {slugify(match.group(2)) for match in HEADING_RE.finditer(stripped)}


def strip_code(text: str) -> str:
    without_fences = FENCE_RE.sub("", text)
    return re.sub(r"`[^`]*`", "", without_fences)


def iter_markdown_files(root: Path):
    # Exclusion must be checked against the path *relative to root*, not the
    # absolute path: a task worktree commonly lives under a path like
    # .claude/worktrees/<slug>/, and matching on path.parts against the
    # absolute path would exclude every file just because an ancestor
    # directory outside the repository happens to be named .claude.
    for pattern in ("*.md", "*.md.jinja"):
        for path in sorted(root.rglob(pattern)):
            relative = path.relative_to(root)
            if any(part in EXCLUDED_DIRS for part in relative.parts):
                continue
            yield path


def check_file(root: Path, path: Path, cache: dict[Path, set[str]]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    own_slugs = heading_slugs(text)
    problems: list[str] = []

    for match in LINK_RE.finditer(strip_code(text)):
        target = match.group(1).strip()
        if not target or "://" in target or target.startswith(("mailto:", "tel:")):
            continue
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        dest, _, fragment = target.partition("#")

        if not dest:
            if fragment and fragment.lower() not in own_slugs:
                problems.append(f"{path.relative_to(root)}: broken self anchor '#{fragment}'")
            continue

        if dest.startswith("/"):
            resolved = (root / dest.lstrip("/")).resolve()
        else:
            resolved = (path.parent / dest).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue  # outside the repository; not this check's concern
        if not resolved.exists():
            problems.append(f"{path.relative_to(root)}: broken link destination '{dest}'")
            continue

        if fragment and resolved.is_file() and resolved.suffix in {".md", ".jinja"}:
            if resolved not in cache:
                try:
                    cache[resolved] = heading_slugs(resolved.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    cache[resolved] = set()
            if fragment not in cache[resolved]:
                problems.append(f"{path.relative_to(root)}: broken anchor '{dest}#{fragment}'")

    return problems


def main() -> int:
    # template/scripts/check_docs_links.py -> repo root is parents[2]
    root = Path(__file__).resolve().parents[2]
    cache: dict[Path, set[str]] = {}
    problems: list[str] = []
    for path in iter_markdown_files(root):
        problems.extend(check_file(root, path, cache))

    if problems:
        print(f"{len(problems)} documentation link/anchor problem(s) found:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Documentation link/anchor check: no problems found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
