from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    ".dev-platform.toml",
    "dev-platform/checks.toml",
    "docs/engineering/openspec-workflow.md",
    "scripts/agent_board.py",
    "scripts/start_worktree.py",
    "scripts/select_checks.py",
    "scripts/merge_to_main.py",
    "scripts/agent_friction.py",
]


def ok(label: str) -> None:
    print(f"[ok]   {label}")


def warn(label: str) -> None:
    print(f"[warn] {label}")


def fail(label: str) -> None:
    print(f"[fail] {label}")


def main() -> int:
    root = Path.cwd().resolve()
    failures = 0

    if sys.version_info >= (3, 11):
        ok(f"Python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        fail("Python 3.11+ is required (tomllib is used by platform scripts)")
        failures += 1

    if shutil.which("git"):
        ok("git is installed")
    else:
        fail("git is not installed")
        failures += 1

    probe = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root, text=True, capture_output=True)
    if probe.returncode == 0:
        ok("inside a Git repository")
    else:
        fail("not inside a Git repository")
        failures += 1

    for relative in REQUIRED_FILES:
        if (root / relative).exists():
            ok(relative)
        else:
            fail(f"missing {relative}")
            failures += 1

    if shutil.which("openspec"):
        ok("OpenSpec CLI is installed")
    else:
        warn("OpenSpec CLI is not installed on this machine")

    ignored = subprocess.run(["git", "check-ignore", "-q", ".claude/agents-board.json"], cwd=root)
    if ignored.returncode == 0:
        ok(".claude machine-local state is ignored")
    else:
        fail(".claude machine-local state is not ignored")
        failures += 1

    local_rules = subprocess.run(["git", "check-ignore", "-q", "AGENTS.local.md"], cwd=root)
    if local_rules.returncode == 0:
        ok("AGENTS.local.md is ignored")
    else:
        fail("AGENTS.local.md is not ignored")
        failures += 1

    if failures:
        print(f"Doctor found {failures} blocking issue(s).")
        return 1
    print("Doctor: platform contract looks healthy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
