from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from _platform_common import current_worktree_root, harness_mode, read_platform_config, run_git

try:
    from independent_review import require_review_evidence, review_is_required
except ModuleNotFoundError as exc:
    if exc.name != "independent_review":
        raise

    def review_is_required(root: Path, change: Path) -> bool:
        settings = read_platform_config(root).get("independent_review", {})
        return isinstance(settings, dict) and settings.get("enabled") is True and (change / ".managed-task.json").is_file()

    def require_review_evidence(root: Path, change: Path) -> None:
        if review_is_required(root, change):
            raise SystemExit(
                f"{change.name}: independent review is enabled but scripts/independent_review.py is missing; "
                "repair the incomplete platform update before archive readiness."
            )

TASK_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s+")
VERIFY_MARKER = "OpenSpec-Verify: PASS"
VERIFY_METHOD_PREFIX = "Verification-Method:"
AUTOMATED_EVIDENCE_PREFIX = "Automated-Checks-Evidence:"
AUTOMATED_EVIDENCE_FILE = "automated-checks.json"
INDEPENDENT_REVIEW_EVIDENCE_PREFIX = "Independent-Review-Evidence:"
INDEPENDENT_REVIEW_EVIDENCE_FILE = "independent-review-request.json"
VERIFICATION_RECEIPT_CONTRACT = "docs/engineering/openspec-workflow.md#verify-archive-then-publish"


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
    lines = [line.strip() for line in receipt.read_text(encoding="utf-8").splitlines()]
    has_marker = VERIFY_MARKER in lines
    has_method = any(line.startswith(VERIFY_METHOD_PREFIX) and line.split(":", 1)[1].strip() for line in lines)
    return has_marker and has_method


def require_automated_evidence(change: Path) -> None:
    receipt = change / "verification.md"
    lines = [line.strip() for line in receipt.read_text(encoding="utf-8").splitlines()]
    expected_marker = f"{AUTOMATED_EVIDENCE_PREFIX} {AUTOMATED_EVIDENCE_FILE}"
    if expected_marker not in lines:
        raise SystemExit(
            f"{change.name}: platform-owned verification must cite '{expected_marker}' so the receipt cannot claim checks that did not run. "
            f"Add that exact line to verification.md; see {VERIFICATION_RECEIPT_CONTRACT}."
        )
    path = change / AUTOMATED_EVIDENCE_FILE
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{change.name}: missing readable automated check evidence: {path}") from exc
    selection = evidence.get("selection")
    executed = evidence.get("executed_commands")
    if not isinstance(selection, dict) or selection.get("state") != "ready":
        raise SystemExit(f"{change.name}: automated evidence does not show valid applicable platform coverage")
    if evidence.get("outcome") != "success" or not isinstance(executed, list):
        raise SystemExit(f"{change.name}: automated evidence does not show successful executed commands")
    if len(executed) != selection.get("command_count") or not executed:
        raise SystemExit(f"{change.name}: automated evidence command count does not match the selected platform coverage")
    if any(item.get("outcome") != "success" for item in executed if isinstance(item, dict)):
        raise SystemExit(f"{change.name}: automated evidence contains a failed command")


def require_independent_review_receipt(change: Path) -> None:
    """Keep enabled independent-review evidence visible from verification.md."""
    root = change.parents[2]
    if not review_is_required(root, change):
        return
    expected = f"{INDEPENDENT_REVIEW_EVIDENCE_PREFIX} {INDEPENDENT_REVIEW_EVIDENCE_FILE}"
    lines = [line.strip() for line in (change / "verification.md").read_text(encoding="utf-8").splitlines()]
    if expected not in lines:
        raise SystemExit(
            f"{change.name}: independent review must cite '{expected}' in verification.md so the PASS receipt names its evidence."
        )


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


def require_ready(change: Path, *, platform_owned: bool = False) -> None:
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
    require_review_evidence(change.parents[2], change)
    require_independent_review_receipt(change)
    if platform_owned:
        require_automated_evidence(change)


def require_static_archive_readiness(change: Path, *, platform_owned: bool = False) -> None:
    """Check deterministic archive prerequisites before checks mutate evidence."""
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
    require_review_evidence(change.parents[2], change)
    require_independent_review_receipt(change)
    if platform_owned:
        expected = f"{AUTOMATED_EVIDENCE_PREFIX} {AUTOMATED_EVIDENCE_FILE}"
        lines = [line.strip() for line in (change / "verification.md").read_text(encoding="utf-8").splitlines()]
        if expected not in lines:
            raise SystemExit(
                f"{change.name}: platform-owned verification must cite '{expected}' before archive can run checks. "
                f"Add that exact line to verification.md; see {VERIFICATION_RECEIPT_CONTRACT}."
            )


def require_applicable_committed_diff(root: Path) -> None:
    """Reject uncommitted-only packages before selecting checks or writing evidence."""
    result = run_git(["diff", "--quiet", "origin/main...HEAD"], cwd=root, check=False)
    if result.returncode == 0:
        raise SystemExit(
            "OpenSpec archive requires an applicable committed diff against origin/main; "
            "uncommitted or untracked-only package state is not archiveable."
        )
    if result.returncode != 1:
        raise SystemExit("OpenSpec archive could not determine committed diff against origin/main.")


def run_checked(command: list[str], root: Path) -> None:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=root)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def archive_change(root: Path, name: str) -> int:
    change = root / "openspec" / "changes" / name
    platform_owned = harness_mode(read_platform_config(root)) == "platform"
    require_static_archive_readiness(change, platform_owned=platform_owned)
    if platform_owned:
        require_applicable_committed_diff(root)
    if platform_owned:
        evidence = change / AUTOMATED_EVIDENCE_FILE
        run_checked(
            ["python3", "scripts/select_checks.py", "--base", "origin/main", "--execute", "--evidence", str(evidence)],
            root,
        )
    require_ready(change, platform_owned=platform_owned)
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
