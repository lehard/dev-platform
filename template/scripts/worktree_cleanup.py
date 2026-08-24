from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from _platform_common import atomic_write_text, machine_path, main_root, read_platform_config, run_git


DEFAULT_AGE_DAYS = 7
MAX_GLOBAL_CLEANUP_CANDIDATES = 50
PENDING_REASONS = {"dirty", "not-merged"}
DEFERRED_CLEANUP_VERSION = 1


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


@dataclass(frozen=True)
class DeferredCleanupTarget:
    """The immutable Git identity required to recover one deferred worktree."""

    path: str
    branch: str
    head: str

    @classmethod
    def from_entry(cls, entry: dict[str, str]) -> "DeferredCleanupTarget":
        return cls(path=entry["path"], branch=entry["branch"], head=entry["head"])

    def as_entry(self) -> dict[str, str]:
        return {"path": self.path, "branch": self.branch, "head": self.head}


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


def deferred_cleanup_path(root: Path, config: dict) -> Path:
    relative = str(
        config.get("paths", {}).get(
            "pending_completed_worktree_cleanup", ".claude/pending-completed-worktree-cleanup.json"
        )
    )
    return root / relative


def _read_deferred_cleanup(root: Path, config: dict) -> list[dict[str, str]]:
    path = deferred_cleanup_path(root, config)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Refusing deferred worktree cleanup because {path} is invalid JSON: {exc}") from exc
    if payload.get("version") != DEFERRED_CLEANUP_VERSION or not isinstance(payload.get("entries"), list):
        raise SystemExit(f"Refusing deferred worktree cleanup because {path} has an unsupported format.")
    entries: list[dict[str, str]] = []
    paths: set[str] = set()
    for entry in payload["entries"]:
        if not isinstance(entry, dict) or not all(isinstance(entry.get(key), str) and entry[key] for key in ("path", "branch", "head")):
            raise SystemExit(f"Refusing deferred worktree cleanup because {path} contains an invalid entry.")
        normalized = {key: entry[key] for key in ("path", "branch", "head")}
        if normalized["path"] in paths:
            raise SystemExit(f"Refusing deferred worktree cleanup because {path} contains ambiguous duplicate worktree entries.")
        paths.add(normalized["path"])
        entries.append(normalized)
    return entries


def _write_deferred_cleanup(root: Path, config: dict, entries: Sequence[dict[str, str]]) -> None:
    path = deferred_cleanup_path(root, config)
    if not entries:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    payload = {"version": DEFERRED_CLEANUP_VERSION, "entries": list(entries)}
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def defer_completed_task(root: Path, worktree: Path, branch: str) -> tuple[Path, DeferredCleanupTarget]:
    """Persist one exact, terminally-delivered worktree for later safe cleanup.

    This is called only after finish has established remote merge, local main
    reconciliation, and managed-project completion.  It records the current
    Git identity so recovery never turns a generic path into a deletion target.
    """
    config = read_platform_config(root)
    resolved_worktree = worktree.resolve()
    managed_root = machine_path("worktrees", root)
    if not _path_within(resolved_worktree, managed_root):
        raise SystemExit(f"Refusing to defer cleanup outside the managed worktree directory: {resolved_worktree}")
    match = next((item for item in _list_worktrees(root) if item.path == resolved_worktree), None)
    if match is None or match.branch != branch:
        raise SystemExit(f"Refusing to defer cleanup for an unregistered or branch-mismatched worktree: {resolved_worktree}")
    entries = _read_deferred_cleanup(root, config)
    entry = {"path": str(resolved_worktree), "branch": branch, "head": match.head}
    retained = [item for item in entries if item["path"] != entry["path"]]
    retained.append(entry)
    _write_deferred_cleanup(root, config, retained)
    return deferred_cleanup_path(root, config), DeferredCleanupTarget.from_entry(entry)


def targeted_cleanup_command(target: DeferredCleanupTarget) -> str:
    return shlex.join(
        [
            "python3",
            "scripts/worktree_cleanup.py",
            "cleanup",
            "--worktree",
            target.path,
            "--branch",
            target.branch,
            "--head",
            target.head,
        ]
    )


def _deferred_entry_is_safe(
    root: Path,
    entry: dict[str, str],
    *,
    managed_root: Path,
    active_board: set[Path],
    active_cwds: set[Path] | None,
) -> tuple[Worktree | None, str | None]:
    path = Path(entry["path"]).resolve()
    if not _path_within(path, managed_root):
        return None, "outside-managed-directory"
    if active_cwds is None:
        return None, "process-check-unavailable"
    if any(_path_within(cwd, path) for cwd in active_cwds):
        return None, "active-process"
    if path in active_board:
        return None, "active-board"
    match = next((item for item in _list_worktrees(root) if item.path == path), None)
    if match is None:
        return None, None
    if match.branch != entry["branch"] or match.head != entry["head"]:
        return None, "identity-mismatch"
    if match.locked or match.prunable:
        return None, "locked" if match.locked else "prunable-metadata"
    status = _worktree_status(match)
    if status.returncode != 0:
        return None, "status-check-failed"
    if status.stdout.strip():
        return None, "dirty"
    return match, None


def _deferred_entry_cleanup_candidate(
    root: Path,
    entry: dict[str, str],
    *,
    managed_root: Path,
    active_board: set[Path],
    active_cwds: set[Path] | None,
) -> tuple[Worktree | None, str | None]:
    worktree, unsafe_reason = _deferred_entry_is_safe(
        root, entry, managed_root=managed_root, active_board=active_board, active_cwds=active_cwds
    )
    if unsafe_reason is not None:
        return None, unsafe_reason
    current = run_git(["rev-parse", "--verify", f"refs/heads/{entry['branch']}"], cwd=root, check=False)
    if current.returncode == 0 and current.stdout.strip() != entry["head"]:
        return None, "branch-identity-mismatch"
    if worktree is not None and current.returncode != 0:
        return None, "branch-missing"
    return worktree, None


def _deferred_cleanup_plan(root: Path, config: dict) -> dict[str, list[dict[str, str]]]:
    entries = _read_deferred_cleanup(root, config)
    managed_root = machine_path("worktrees", root)
    active_board = _active_board_paths(root, config)
    active_cwds = _active_cwds()
    candidates: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    for entry in entries:
        _, unsafe_reason = _deferred_entry_cleanup_candidate(
            root, entry, managed_root=managed_root, active_board=active_board, active_cwds=active_cwds
        )
        if unsafe_reason is None:
            candidates.append(entry)
        else:
            blocked.append({"path": entry["path"], "error": unsafe_reason})
    return {"candidates": candidates, "blocked": blocked}


def _cleanup_deferred_completed_tasks(
    root: Path,
    config: dict,
    *,
    target: DeferredCleanupTarget | None = None,
    prune: bool = False,
) -> tuple[list[str], list[dict[str, str]], bool]:
    entries = _read_deferred_cleanup(root, config)
    if target is not None:
        entries = [entry for entry in entries if entry == target.as_entry()]
        if not entries:
            return [], [], False
    managed_root = machine_path("worktrees", root)
    active_board = _active_board_paths(root, config)
    active_cwds = _active_cwds()
    removed: list[str] = []
    errors: list[dict[str, str]] = []
    retained: list[dict[str, str]] = []
    all_entries = _read_deferred_cleanup(root, config)
    selected_entries = {tuple(sorted(entry.items())) for entry in entries}
    for entry in all_entries:
        if tuple(sorted(entry.items())) not in selected_entries:
            retained.append(entry)
            continue
        worktree, unsafe_reason = _deferred_entry_cleanup_candidate(
            root, entry, managed_root=managed_root, active_board=active_board, active_cwds=active_cwds
        )
        if unsafe_reason is not None:
            errors.append({"path": entry["path"], "error": unsafe_reason})
            retained.append(entry)
            continue
        if worktree is not None:
            result = run_git(["worktree", "remove", str(worktree.path)], cwd=root, check=False)
            if result.returncode != 0:
                errors.append({"path": entry["path"], "error": (result.stderr.strip() or result.stdout.strip() or "worktree remove failed")[-500:]})
                retained.append(entry)
                continue
        current = run_git(["rev-parse", "--verify", f"refs/heads/{entry['branch']}"], cwd=root, check=False)
        if current.returncode == 0:
            if current.stdout.strip() != entry["head"]:
                errors.append({"path": entry["path"], "error": "branch-identity-mismatch"})
                retained.append(entry)
                continue
            deleted = run_git(["branch", "-D", entry["branch"]], cwd=root, check=False)
            if deleted.returncode != 0:
                errors.append({"path": entry["path"], "error": (deleted.stderr.strip() or deleted.stdout.strip() or "branch cleanup failed")[-500:]})
                retained.append(entry)
                continue
        removed.append(entry["path"])
    _write_deferred_cleanup(root, config, retained)
    if removed and prune:
        run_git(["worktree", "prune"], cwd=root, check=False)
    return removed, errors, True


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
    atomic_write_text(path, "\n".join(lines))
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


def _normalized_target(target: DeferredCleanupTarget) -> DeferredCleanupTarget:
    raw_path = Path(target.path)
    if not raw_path.is_absolute():
        raise SystemExit("Targeted deferred cleanup requires an absolute --worktree path.")
    return DeferredCleanupTarget(path=str(raw_path.resolve()), branch=target.branch, head=target.head)


def global_cleanup_preview(root: Path, older_than_days: int) -> dict[str, object]:
    config = read_platform_config(root)
    deferred = _deferred_cleanup_plan(root, config)
    deferred_paths = {entry["path"] for entry in _read_deferred_cleanup(root, config)}
    decisions = scan(root, older_than_days)
    # A deferred record owns its exact path until it is safely removed or
    # deliberately repaired.  Do not let the generic old-worktree pass
    # reinterpret a stale or otherwise blocked deferred identity as an
    # unrelated candidate.
    ordinary_candidates = [asdict(item) for item in decisions if item.eligible and item.path not in deferred_paths]
    candidate_count = len(deferred["candidates"]) + len(ordinary_candidates)
    if candidate_count > MAX_GLOBAL_CLEANUP_CANDIDATES:
        return {
            "status": "refused",
            "scope": "all",
            "candidate_count": candidate_count,
            "maximum_candidates": MAX_GLOBAL_CLEANUP_CANDIDATES,
            "error": "too-many-candidates",
        }
    apply_command = ["python3", "scripts/worktree_cleanup.py", "cleanup", "--all", "--apply"]
    if older_than_days != DEFAULT_AGE_DAYS:
        apply_command += ["--older-than-days", str(older_than_days)]
    return {
        "status": "preview",
        "scope": "all",
        "candidate_count": candidate_count,
        "deferred": deferred,
        "ordinary_candidates": ordinary_candidates,
        "apply_command": shlex.join(apply_command),
    }


def _cleanup_all(root: Path, older_than_days: int) -> dict[str, object]:
    removed: list[str] = []
    errors: list[dict[str, str]] = []
    config = read_platform_config(root)
    deferred_removed, deferred_errors, _ = _cleanup_deferred_completed_tasks(root, config, prune=True)
    removed.extend(deferred_removed)
    errors.extend(deferred_errors)
    protected_deferred_paths = {entry["path"] for entry in _read_deferred_cleanup(root, config)}
    initial = scan(root, older_than_days)
    for candidate in initial:
        if candidate.path in protected_deferred_paths:
            continue
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
        "scope": "all",
        **summary(final),
        "removed": removed,
        "errors": errors,
        "pending_report": str(report),
    }


def _cleanup_target(root: Path, target: DeferredCleanupTarget) -> dict[str, object]:
    config = read_platform_config(root)
    target = _normalized_target(target)
    removed, errors, matched = _cleanup_deferred_completed_tasks(root, config, target=target)
    return {
        "status": "completed" if errors else ("already-cleaned" if not matched else "completed"),
        "scope": "target",
        "target": target.as_entry(),
        "matched": matched,
        "removed": removed,
        "errors": errors,
    }


def cleanup(
    root: Path,
    older_than_days: int,
    *,
    target: DeferredCleanupTarget | None = None,
    all: bool = False,
    apply: bool = False,
) -> dict[str, object]:
    if target is not None and all:
        raise SystemExit("Choose either one exact deferred target or --all, not both.")
    if target is not None and apply:
        raise SystemExit("--apply is only valid with --all.")
    if target is not None:
        return _cleanup_target(root, target)
    if not all:
        raise SystemExit("Refusing global cleanup without one exact deferred target or --all.")
    preview = global_cleanup_preview(root, older_than_days)
    if not apply or preview["status"] == "refused":
        return preview
    return _cleanup_all(root, older_than_days)


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely diagnose and clean platform-managed agent worktrees.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan_command = sub.add_parser("scan")
    scan_command.add_argument("--older-than-days", type=int, default=DEFAULT_AGE_DAYS)
    cleanup_command = sub.add_parser("cleanup")
    cleanup_command.add_argument("--older-than-days", type=int, default=DEFAULT_AGE_DAYS)
    cleanup_command.add_argument("--worktree", help="Exact absolute worktree path from finish recovery output.")
    cleanup_command.add_argument("--branch", help="Exact branch identity from finish recovery output.")
    cleanup_command.add_argument("--head", help="Exact Git head identity from finish recovery output.")
    cleanup_command.add_argument("--all", action="store_true", help="Preview all global cleanup candidates.")
    cleanup_command.add_argument("--apply", action="store_true", help="Apply a previously reviewed --all cleanup plan.")
    args = parser.parse_args()
    root = main_root()
    if args.command == "cleanup":
        target_values = (args.worktree, args.branch, args.head)
        if any(target_values) and not all(target_values):
            parser.error("targeted cleanup requires --worktree, --branch, and --head together")
        if args.all and any(target_values):
            parser.error("choose either --all or one exact --worktree/--branch/--head target")
        if args.apply and not args.all:
            parser.error("--apply requires --all")
        if not args.all and not all(target_values):
            parser.error("cleanup requires one exact --worktree/--branch/--head target or --all")
        target = DeferredCleanupTarget(*target_values) if all(target_values) else None
        payload = cleanup(root, args.older_than_days, target=target, all=args.all, apply=args.apply)
    else:
        decisions = scan(root, args.older_than_days)
        report = write_pending_report(root, decisions)
        payload = {"status": "scan", **summary(decisions), "pending_report": str(report), "decisions": [asdict(item) for item in decisions]}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
