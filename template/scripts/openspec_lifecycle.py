from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

from _platform_common import current_worktree_root

TASK_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s+")
VERIFY_MARKER = "OpenSpec-Verify: PASS"
VERIFY_METHOD_PREFIX = "Verification-Method:"


def active_changes(root: Path) -> list[Path]:
    changes = root / "openspec" / "changes"
    if not changes.exists():
        return []
    return sorted(path for path in changes.iterdir() if path.is_dir() and path.name != "archive")


def task_state(change: Path) -> tuple[int, int]:
    tasks = change / "tasks.md"
    if not tasks.exists():
        return 0, 0
    total = incomplete = 0
    for line in tasks.read_text(encoding="utf-8").splitlines():
        match = TASK_RE.match(line)
        if not match:
            continue
        total += 1
        if match.group(1) == " ":
            incomplete += 1
    return total, incomplete


def verification_passed(change: Path) -> bool:
    receipt = change / "verification.md"
    if not receipt.exists():
        return False
    text = receipt.read_text(encoding="utf-8")
    has_method = any(line.strip().startswith(VERIFY_METHOD_PREFIX) and line.split(":", 1)[1].strip() for line in text.splitlines())
    return VERIFY_MARKER in text and has_method


def completed_active_changes(root: Path) -> list[str]:
    stale: list[str] = []
    for change in active_changes(root):
        total, incomplete = task_state(change)
        if total > 0 and incomplete == 0:
            stale.append(change.name)
    return stale


def check_hygiene(root: Path) -> int:
    stale = completed_active_changes(root)
    if not stale:
        print("OpenSpec lifecycle hygiene: OK")
        return 0
    print("OpenSpec lifecycle hygiene: BLOCKED")
    for name in stale:
        print(f"- {name}: all tasks are complete but the change is still active")
    print("Run /opsx:verify when available (or the documented equivalent semantic review), resolve findings, record the PASS receipt and method, then archive through scripts/openspec_lifecycle.py.")
    return 1


def require_ready(change: Path) -> None:
    if not change.exists() or not change.is_dir():
        raise SystemExit(f"Active OpenSpec change not found: {change.name}")
    total, incomplete = task_state(change)
    if total == 0:
        raise SystemExit(f"{change.name}: tasks.md has no task checkboxes; refusing automatic archive")
    if incomplete:
        raise SystemExit(f"{change.name}: {incomplete} of {total} task(s) remain incomplete")
    if not verification_passed(change):
        raise SystemExit(
            f"{change.name}: missing successful semantic verification receipt. "
            f"Run /opsx:verify when available (or an equivalent documented OpenSpec verification), resolve material findings, "
            f"then record '{VERIFY_MARKER}' and a '{VERIFY_METHOD_PREFIX} <method>' line in verification.md."
        )


def run_checked(command: list[str], root: Path) -> None:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=root)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def archive_change(root: Path, name: str) -> int:
    change = root / "openspec" / "changes" / name
    require_ready(change)
    executable = shutil.which("openspec")
    if not executable:
        raise SystemExit("OpenSpec CLI is required to archive a verified change")
    run_checked([executable, "validate", name, "--strict", "--no-interactive"], root)
    run_checked([executable, "archive", name, "--yes"], root)
    run_checked([executable, "validate", "--all", "--strict", "--no-interactive"], root)
    print(f"Archived verified OpenSpec change: {name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce the OpenSpec verify/archive completion contract.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="Fail if a completed change is still active.")
    archive = sub.add_parser("archive", help="Archive a completed, semantically verified change.")
    archive.add_argument("change")
    args = parser.parse_args()
    root = current_worktree_root()
    if args.command == "check":
        return check_hygiene(root)
    return archive_change(root, args.change)


if __name__ == "__main__":
    raise SystemExit(main())
