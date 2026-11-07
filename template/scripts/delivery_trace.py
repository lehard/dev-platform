#!/usr/bin/env python3
"""The trace finish leaves on the head it publishes, and the required check that reads it.

The trace is a commit trailer holding the tree of its own commit. The commit hash covers the
message, so the trace is bound to the head; the tree catches an amend or rebase that keeps the
message. The check reads Git only. See docs/decisions/0011-finish-bypass-guard.md.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

TRAILER = "Dev-Platform-Finish"
NEXT_COMMAND = (
    "Next: run `python3 scripts/dogfood_task.py finish` from the task worktree; with no task yet, "
    "start one with `python3 scripts/dogfood_task.py start <slug> --task TEXT --scope PATHS`."
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL)
    if result.returncode:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def _settings(root: Path) -> dict:
    """``[settings]`` of the check configuration; a project without that file has none, as for its cheap gates."""
    from _platform_common import read_platform_config
    from lifecycle_preflight import load_checks_config

    if not (root / read_platform_config(root)["paths"]["checks"]).exists():
        return {}
    return load_checks_config(root).get("settings", {})


def enabled(root: Path) -> bool:
    """Whether this repository writes the trace; a project without the setting does not."""
    value = _settings(root).get("delivery_trace", False)
    if not isinstance(value, bool):
        raise SystemExit(f"[settings] delivery_trace must be a boolean, got {value!r}.")
    return value


def refusal(root: Path, head: str) -> str | None:
    """Why ``head`` carries no valid trace, or None when it does."""
    tree = _git(root, "rev-parse", f"{head}^{{tree}}")
    values = _git(root, "log", "-1", f"--format=%(trailers:key={TRAILER},valueonly)", head).splitlines()
    if not values:
        return f"head {head} carries no {TRAILER} trailer: it did not pass through finish."
    if len(values) > 1:
        return f"head {head} carries {len(values)} {TRAILER} trailers, expected one."
    if values[0] != tree:
        return f"head {head} carries the trace of tree {values[0]} but its tree is {tree}: the head changed after finish."
    return None


def stamp(root: Path) -> None:
    """Add an empty commit with a valid trace; the subject stays, because the PR title comes from the head."""
    subject = _git(root, "log", "-1", "--format=%s")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    _git(root, "commit", "--allow-empty", "-m", subject, "-m", f"{TRAILER}: {tree}")
    print(f"Recorded the {TRAILER} trace for tree {tree}.")


def ensure(root: Path) -> None:
    """Make the head carry a valid trace where this repository enables it; a traced head stays as it is."""
    if enabled(root) and refusal(root, "HEAD") is not None:
        stamp(root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refuse a pull request head that did not pass through finish.")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check the exact pull request head")
    check.add_argument("--head", required=True, help="the pull request head commit, not the checked-out merge commit")
    args = parser.parse_args()
    reason = refusal(Path.cwd(), args.head)
    if reason is None:
        print(f"Head {args.head} carries a valid {TRAILER} trace.")
        return 0
    print(f"::error title=Pull request bypassed finish::{reason} {NEXT_COMMAND}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
