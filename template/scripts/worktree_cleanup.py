from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from _platform_common import machine_path, main_root, read_platform_config, run_git


DEFAULT_AGE_DAYS = 7
PENDING_REASONS = {"dirty", "not-merged"}


@dataclass(frozen=True)
class Worktree:
    path: Path
    head: str
    branch: str | None
    locked: bool = False
    prunable: bool = False


@dataclass(frozen=True)
class Decision:
    path: str
    branch: str
    head: str
    eligible: bool
    reason: str
    age_days: float | None = None
    detail: str | None = None


def _path_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _list_worktrees(root: Path) -> list[Worktree]:
    completed = subprocess.run(
        ["git", "worktree", "list", "--porcelain", "-z"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.decode(errors="replace").strip() or "git worktree list failed")
    result: list[Worktree] = []
    raw = completed.stdout.decode(errors="surrogateescape")
    for record in raw.split("\0\0"):
        if not record.strip("\0"):
            continue
        values: dict[str, str] = {}
        flags: set[str] = set()
        for field in record.strip("\0").split("\0"):
            key, sep, value = field.partition(" ")
            if sep:
                values[key] = value
            else:
                flags.add(key)
        path = values.get("worktree")
        head = values.get("HEAD")
        if not path or not head:
            raise SystemExit("git worktree returned an incomplete record")
        branch_ref = values.get("branch")
        branch = branch_ref.removeprefix("refs/heads/") if branch_ref else None
        result.append(
            Worktree(
                path=Path(path).resolve(),
                head=head,
                branch=branch,
                locked="locked" in flags or "locked" in values,
                prunable="prunable" in flags or "prunable" in values,
            )
        )
    return result


def _active_board_paths(root: Path, config: dict) -> set[Path]:
    relative = str(config.get("paths", {}).get("agent_board", ".claude/agents-board.json"))
    path = root / relative
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Refusing cleanup because agent board is invalid JSON: {exc}") from exc
    active: set[Path] = set()
    for item in payload.get("items", []):
        raw = item.get("worktree")
        if raw:
            active.add(Path(raw).expanduser().resolve())
    return active


def _active_cwds() -> set[Path] | None:
    executable = shutil.which("lsof")
    if not executable:
        return None
    completed = subprocess.run(
        [executable, "-a", "-d", "cwd", "-Fn"],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if completed.returncode not in {0, 1}:
        return None
    paths: set[Path] = set()
    for line in completed.stdout.splitlines():
        if line.startswith("n/"):
            try:
                paths.add(Path(line[1:]).resolve())
            except OSError:
                continue
    return paths


def _worktree_status(worktree: Worktree) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={worktree.path}", "status", "--porcelain", "--untracked-files=normal"],
        cwd=worktree.path,
        text=True,
        capture_output=True,
        check=False,
    )


def _activity_timestamp(root: Path, worktree: Worktree) -> float:
    values = [worktree.path.stat().st_mtime]
    result = run_git(["show", "-s", "--format=%ct", worktree.head], cwd=root)
    values.append(float(result.stdout.strip()))
    return max(values)


def classify(
    root: Path,
    worktree: Worktree,
    *,
    managed_root: Path,
    main_branch: str,
    active_board: set[Path],
    active_cwds: set[Path] | None,
    older_than_days: int,
    now: float,
) -> Decision:
    common = {
        "path": str(worktree.path),
        "branch": worktree.branch or "(detached)",
        "head": worktree.head,
    }
    if worktree.path == root.resolve():
        return Decision(**common, eligible=False, reason="integration-copy")
    if not _path_within(worktree.path, managed_root):
        return Decision(**common, eligible=False, reason="outside-managed-directory")
    if worktree.locked:
        return Decision(**common, eligible=False, reason="locked")
    if worktree.prunable:
        return Decision(**common, eligible=False, reason="prunable-metadata")
    if worktree.path in active_board:
        return Decision(**common, eligible=False, reason="active-board")
    if active_cwds is None:
        return Decision(**common, eligible=False, reason="process-check-unavailable")
    if any(_path_within(cwd, worktree.path) for cwd in active_cwds):
        return Decision(**common, eligible=False, reason="active-process")
    status = _worktree_status(worktree)
    if status.returncode != 0:
        detail = (status.stderr.strip() or status.stdout.strip())[-500:]
        return Decision(**common, eligible=False, reason="status-check-failed", detail=detail)
    if status.stdout.strip():
        return Decision(**common, eligible=False, reason="dirty")
    merged = run_git(["merge-base", "--is-ancestor", worktree.head, f"refs/heads/{main_branch}"], cwd=root, check=False)
    if merged.returncode == 1:
        return Decision(**common, eligible=False, reason="not-merged")
    if merged.returncode != 0:
        return Decision(**common, eligible=False, reason="merge-check-failed")
    try:
        age_days = max(0.0, (now - _activity_timestamp(root, worktree)) / 86400)
    except (OSError, ValueError) as exc:
        return Decision(**common, eligible=False, reason="activity-check-failed", detail=str(exc)[-500:])
    if age_days < older_than_days:
        return Decision(**common, eligible=False, reason="too-new", age_days=round(age_days, 2))
    return Decision(**common, eligible=True, reason="merged-clean-inactive", age_days=round(age_days, 2))


def scan(root: Path, older_than_days: int, *, active_cwds: set[Path] | None = None, now: float | None = None) -> list[Decision]:
    if older_than_days < 1:
        raise SystemExit("--older-than-days must be at least 1")
    config = read_platform_config(root)
    main_branch = str(config.get("main_branch", "main"))
    managed_root = machine_path("worktrees", root)
    board = _active_board_paths(root, config)
    process_paths = _active_cwds() if active_cwds is None else active_cwds
    current_time = time.time() if now is None else now
    return [
        classify(
            root,
            worktree,
            managed_root=managed_root,
            main_branch=main_branch,
            active_board=board,
            active_cwds=process_paths,
            older_than_days=older_than_days,
            now=current_time,
        )
        for worktree in _list_worktrees(root)
    ]


def pending_report_path(root: Path, config: dict) -> Path:
    relative = str(config.get("paths", {}).get("pending_worktrees", ".claude/pending-worktrees.md"))
    return root / relative


def write_pending_report(root: Path, decisions: Sequence[Decision]) -> Path:
    config = read_platform_config(root)
    path = pending_report_path(root, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = sorted(
        (item for item in decisions if item.reason in PENDING_REASONS),
        key=lambda item: item.path,
    )
    lines = [
        "# Pending agent worktrees",
        "",
        "Generated by `scripts/worktree_cleanup.py`. This is machine-local coordination state, not a backlog.",
        "",
    ]
    if not pending:
        lines.append("No inactive dirty or unmerged managed worktrees were found.")
    else:
        lines += ["| branch | worktree | reason |", "|---|---|---|"]
        for item in pending:
            lines.append(f"| `{item.branch}` | `{item.path}` | {item.reason} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def summary(decisions: Sequence[Decision]) -> dict[str, object]:
    reasons: dict[str, int] = {}
    for item in decisions:
        reasons[item.reason] = reasons.get(item.reason, 0) + 1
    return {
        "checked": len(decisions),
        "eligible": sum(1 for item in decisions if item.eligible),
        "pending": sum(1 for item in decisions if item.reason in PENDING_REASONS),
        "reason_counts": dict(sorted(reasons.items())),
    }


def cleanup(root: Path, older_than_days: int) -> dict[str, object]:
    removed: list[str] = []
    errors: list[dict[str, str]] = []
    initial = scan(root, older_than_days)
    for candidate in initial:
        if not candidate.eligible:
            continue
        refreshed = scan(root, older_than_days)
        current = next((item for item in refreshed if item.path == candidate.path), None)
        if current is None or not current.eligible:
            errors.append({"path": candidate.path, "error": "candidate-no-longer-safe"})
            continue
        result = run_git(["worktree", "remove", candidate.path], cwd=root, check=False)
        if result.returncode != 0:
            errors.append({"path": candidate.path, "error": (result.stderr.strip() or result.stdout.strip())[-500:]})
            continue
        removed.append(candidate.path)
    if removed:
        run_git(["worktree", "prune"], cwd=root, check=False)
    final = scan(root, older_than_days)
    report = write_pending_report(root, final)
    return {
        "status": "completed" if not errors else "completed-with-errors",
        **summary(final),
        "removed": removed,
        "errors": errors,
        "pending_report": str(report),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely diagnose and clean platform-managed agent worktrees.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("scan", "cleanup"):
        command = sub.add_parser(name)
        command.add_argument("--older-than-days", type=int, default=DEFAULT_AGE_DAYS)
    args = parser.parse_args()
    root = main_root()
    if args.command == "cleanup":
        payload = cleanup(root, args.older_than_days)
    else:
        decisions = scan(root, args.older_than_days)
        report = write_pending_report(root, decisions)
        payload = {"status": "scan", **summary(decisions), "pending_report": str(report), "decisions": [asdict(item) for item in decisions]}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
