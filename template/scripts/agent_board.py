from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _platform_common import (
    current_worktree_root,
    locked_json,
    machine_path,
    main_root,
    read_platform_config,
    run_git,
    utc_now,
)


DEFAULT_STALE_HOURS = 72
MAX_OVERLAP_DIAGNOSTICS = 5
MAX_ADMISSION_DIAGNOSTICS = 5
MAX_ACKNOWLEDGED_PATHS = 20


class HardScopeOverlap(RuntimeError):
    """A newly observed, unacknowledged hard file overlap blocks costly work."""


def board_path(root: Path | None = None) -> Path:
    return machine_path("agent_board", root or main_root())


def _branch_exists(branch: str, root: Path) -> bool:
    result = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root, check=False)
    return result.returncode == 0


def _heartbeat_is_stale(raw: str | None, stale_hours: int) -> bool:
    if not raw:
        return True
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return value < datetime.now(timezone.utc) - timedelta(hours=stale_hours)


def _checked_out_branch(worktree: Path) -> str | None:
    result = run_git(["branch", "--show-current"], cwd=worktree, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _registered_worktrees(root: Path) -> set[Path]:
    """Return only the exact roots Git considers registered worktrees."""
    result = run_git(["worktree", "list", "--porcelain"], cwd=root, check=False)
    if result.returncode != 0:
        raise SystemExit("Agent board registration blocked: unable to inspect registered Git worktrees.")
    registered: set[Path] = set()
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            registered.add(Path(line.removeprefix("worktree ")).resolve())
    return registered


def validate_worktree_identity(raw_worktree: str, branch: str, root: Path) -> Path:
    """Prove a board entry names one non-integration registered worktree.

    The absolute-path check deliberately happens before any Git subprocess or
    board-file access, so an ambiguous CLI value has no side effects.
    """
    supplied = Path(raw_worktree).expanduser()
    if not supplied.is_absolute():
        raise SystemExit(
            "Agent board registration blocked: --worktree must be an absolute registered worktree path; "
            "relative paths are ambiguous."
        )
    worktree = supplied.resolve()
    integration = root.resolve()
    if worktree == integration:
        raise SystemExit("Agent board registration blocked: integration main cannot be registered as an agent worktree.")
    if not worktree.exists():
        raise SystemExit(f"Agent board registration blocked: worktree does not exist: {worktree}")
    if worktree not in _registered_worktrees(integration):
        raise SystemExit(
            "Agent board registration blocked: --worktree must name an exact registered Git worktree root, "
            f"not {worktree}."
        )
    actual_branch = _checked_out_branch(worktree)
    if actual_branch != branch:
        raise SystemExit(
            "Agent board registration blocked: declared branch/worktree mismatch; "
            f"declared {branch!r}, worktree has {actual_branch!r}."
        )
    if not _branch_exists(branch, integration):
        raise SystemExit(f"Agent board registration blocked: declared branch does not exist: {branch!r}.")
    return worktree


def _normalized_scope_paths(scope: str, root: Path) -> set[str]:
    """Normalize declared repository paths without exposing external paths."""
    paths: set[str] = set()
    for raw in re.split(r"[,\n]", scope):
        value = raw.strip()
        if not value:
            continue
        candidate = Path(value).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
        try:
            relative = resolved.relative_to(root.resolve())
        except ValueError:
            # A board diagnostic must never turn an external machine path into
            # shared coordination state or output.
            continue
        normalized = relative.as_posix()
        if normalized and normalized != ".":
            paths.add(normalized)
    return paths


def _concrete_declared_scope_paths(scope: str, root: Path) -> set[str]:
    """Return only declared paths that can safely be treated as file claims.

    Scope is deliberately permissive because it is also used for advisory
    diagnostics.  Admission is stricter: directories, globs and other broad
    values must never become a hard blocker.  Existing files are concrete even
    without an extension (for example ``Makefile``); a non-existing path with
    a suffix is a useful declaration of a planned file.
    """
    concrete: set[str] = set()
    for raw in re.split(r"[,\n]", scope):
        value = raw.strip()
        if not value or any(token in value for token in ("*", "?", "[", "]")):
            continue
        candidate = Path(value).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
        try:
            relative = resolved.relative_to(root.resolve())
        except ValueError:
            continue
        if resolved.is_dir():
            continue
        normalized = relative.as_posix()
        if normalized and normalized != "." and (resolved.is_file() or relative.suffix):
            concrete.add(normalized)
    return concrete


def _factual_scope_paths(worktree: Path, root: Path, main_branch: str) -> set[str]:
    result = run_git(["diff", "--name-only", f"{main_branch}...HEAD"], cwd=worktree, check=False)
    if result.returncode != 0:
        return set()
    return _normalized_scope_paths(result.stdout, root)


def _claim_candidates(item: dict, root: Path, main_branch: str) -> set[str]:
    """Resolve concrete paths a task is asking to claim at admission time."""
    candidates = _concrete_declared_scope_paths(str(item.get("scope", "")), root)
    raw_worktree = item.get("worktree", "")
    if raw_worktree:
        candidates |= _factual_scope_paths(Path(str(raw_worktree)).expanduser().resolve(), root, main_branch)
    return candidates


def _owned_claim_paths(item: dict, root: Path, main_branch: str) -> set[str]:
    """Resolve concrete paths currently owned by an admitted active task."""
    stored = item.get("claims", [])
    claims = _normalized_scope_paths("\n".join(stored), root) if isinstance(stored, list) else set()
    raw_worktree = item.get("worktree", "")
    if raw_worktree:
        claims |= _factual_scope_paths(Path(str(raw_worktree)).expanduser().resolve(), root, main_branch)
    return claims


def _overlap_path(left: str, right: str) -> str | None:
    if left == right:
        return left
    if left.startswith(right + "/"):
        return left
    if right.startswith(left + "/"):
        return right
    return None


def scope_overlap_diagnostics(
    root: Path,
    worktree: Path,
    branch: str,
    scope: str,
    items: list[dict],
) -> list[tuple[str, str, str]]:
    """Return bounded repo-relative conflicts with valid other board entries."""
    config = read_platform_config(root)
    main_branch = str(config.get("main_branch", "main"))
    current_paths = _normalized_scope_paths(scope, root) | _factual_scope_paths(worktree, root, main_branch)
    if not current_paths:
        return []

    conflicts: list[tuple[str, str, str]] = []
    for item in items:
        item_worktree = Path(str(item.get("worktree", ""))).expanduser().resolve()
        if item_worktree == worktree.resolve() or item.get("branch") == branch:
            continue
        if _status(item, root, main_branch=main_branch, stale_hours=DEFAULT_STALE_HOURS):
            continue
        other_paths = _normalized_scope_paths(str(item.get("scope", "")), root)
        other_paths |= _factual_scope_paths(item_worktree, root, main_branch)
        for current in sorted(current_paths):
            for other in sorted(other_paths):
                overlap = _overlap_path(current, other)
                if overlap is not None:
                    conflict = (str(item.get("id", "unknown")), str(item.get("task", "active task")), overlap)
                    if conflict not in conflicts:
                        conflicts.append(conflict)
                    if len(conflicts) >= MAX_OVERLAP_DIAGNOSTICS:
                        return conflicts
    return conflicts


def _print_overlap_warning(conflicts: list[tuple[str, str, str]]) -> None:
    if not conflicts:
        return
    print("Scope-overlap warning: coordinate or serialize work before costly validation or publication.", file=sys.stderr)
    for item_id, task, path in conflicts:
        print(f"- {item_id} ({task}): {path}", file=sys.stderr)


def _acknowledged_overlap(current: dict, other_id: str, path: str) -> bool:
    """Whether ``current`` holds bounded evidence authorizing this exact pair.

    An acknowledgment authorizes only the concrete (conflicting task identity,
    path) pair recorded at acknowledgment time.  A new path or a different
    conflicting task identity is never covered, even if the same operator
    reason would obviously apply -- that judgment requires a new decision.
    """
    acknowledgments = current.get("acknowledgments", [])
    if not isinstance(acknowledgments, list):
        return False
    for ack in acknowledgments:
        if not isinstance(ack, dict):
            continue
        if str(ack.get("with_id", "")) != other_id:
            continue
        paths = ack.get("paths", [])
        if isinstance(paths, list) and path in paths:
            return True
    return False


def _admission_conflicts(
    root: Path,
    current: dict,
    items: list[dict],
    *,
    main_branch: str,
) -> list[tuple[str, str, str]]:
    """Find bounded hard conflicts against valid active claims.

    This function is called while ``locked_json`` holds the board lock.  The
    caller records a successful claim in the same critical section, making the
    read-and-claim decision race-safe on one machine.  It is also reused
    read-only, outside the lock, to recheck evolving factual scope before
    costly validation and again before publication.
    """
    current_claims = _claim_candidates(current, root, main_branch)
    if not current_claims:
        return []
    conflicts: list[tuple[str, str, str]] = []
    current_worktree = Path(str(current.get("worktree", ""))).expanduser().resolve()
    current_branch = str(current.get("branch", ""))
    for item in items:
        if item is current:
            continue
        if Path(str(item.get("worktree", ""))).expanduser().resolve() == current_worktree:
            continue
        if str(item.get("branch", "")) == current_branch:
            continue
        if _status(item, root, main_branch=main_branch, stale_hours=DEFAULT_STALE_HOURS):
            continue
        item_id = str(item.get("id", "unknown"))
        for path in sorted(current_claims & _owned_claim_paths(item, root, main_branch)):
            if _acknowledged_overlap(current, item_id, path):
                continue
            conflict = (item_id, str(item.get("task", "active task")), path)
            if conflict not in conflicts:
                conflicts.append(conflict)
            if len(conflicts) >= MAX_ADMISSION_DIAGNOSTICS:
                return conflicts
    return conflicts


def _admit_item(root: Path, current: dict, items: list[dict], *, main_branch: str) -> dict:
    conflicts = _admission_conflicts(root, current, items, main_branch=main_branch)
    if conflicts:
        current["admission"] = {"decision": "WAIT", "conflicts": [list(conflict) for conflict in conflicts], "at": utc_now()}
        return {"decision": "WAIT", "conflicts": [list(conflict) for conflict in conflicts]}
    claims = sorted(_claim_candidates(current, root, main_branch))
    current["claims"] = claims
    current["admission"] = {"decision": "RUN", "at": utc_now()}
    return {"decision": "RUN", "claims": claims}


def _worktree_clean(worktree: Path) -> bool:
    result = run_git(["status", "--porcelain", "--untracked-files=normal"], cwd=worktree, check=False)
    return result.returncode == 0 and not result.stdout.strip()


def _merged_into(root: Path, branch: str, main_branch: str) -> bool:
    result = run_git(["merge-base", "--is-ancestor", f"refs/heads/{branch}", f"refs/heads/{main_branch}"], cwd=root, check=False)
    return result.returncode == 0


def _status(item: dict, root: Path, *, main_branch: str, stale_hours: int) -> list[str]:
    problems: list[str] = []
    raw_worktree = item.get("worktree", "")
    worktree = Path(raw_worktree).expanduser().resolve() if raw_worktree else None
    branch = str(item.get("branch", ""))
    if worktree is None or not worktree.exists():
        problems.append("worktree-missing")
    elif branch:
        actual = _checked_out_branch(worktree)
        if actual != branch:
            problems.append("branch-path-mismatch")
    if not branch or not _branch_exists(branch, root):
        problems.append("branch-missing")
    elif branch != main_branch and _merged_into(root, branch, main_branch):
        problems.append("merged-branch")
    if _heartbeat_is_stale(item.get("heartbeat"), stale_hours):
        problems.append("stale-heartbeat")
    return problems


def cmd_list(_: argparse.Namespace) -> int:
    path = board_path()
    if not path.exists():
        print("No active agent board.")
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not items:
        print("No active agent work.")
        return 0
    for item in items:
        print(f"{item['id']}  {item['branch']}  {item['task']}")
        print(f"  worktree: {item['worktree']}")
        print(f"  scope: {item.get('scope') or '-'}")
        print(f"  heartbeat: {item.get('heartbeat')}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    root = main_root()
    branch = args.branch
    worktree = validate_worktree_identity(args.worktree, branch, root)
    path = board_path()

    with locked_json(path) as data:
        items = data.setdefault("items", [])
        for item in items:
            if Path(item.get("worktree", "")).resolve() == worktree:
                raise SystemExit(f"Worktree already registered: {worktree}")
            if item.get("branch") == branch:
                raise SystemExit(f"Branch already registered: {branch}")
        conflicts = scope_overlap_diagnostics(root, worktree, branch, args.scope or "", items)
        item_id = args.id or uuid.uuid4().hex[:10]
        items.append(
            {
                "id": item_id,
                "task": args.task,
                "scope": args.scope or "",
                "branch": branch,
                "worktree": str(worktree),
                "pid": os.getpid(),
                "started_at": utc_now(),
                "heartbeat": utc_now(),
            }
        )
    _print_overlap_warning(conflicts)
    print(item_id)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    path = board_path()
    with locked_json(path) as data:
        item = next((x for x in data.setdefault("items", []) if x.get("id") == args.id), None)
        if item is None:
            raise SystemExit(f"Unknown board id: {args.id}")
        if args.task is not None:
            item["task"] = args.task
        if args.scope is not None:
            item["scope"] = args.scope
        item["heartbeat"] = utc_now()
    return 0


def _find_item(items: list[dict], worktree: Path, branch: str) -> dict | None:
    return next(
        (
            item
            for item in items
            if Path(str(item.get("worktree", ""))).expanduser().resolve() == worktree.resolve()
            and str(item.get("branch", "")) == branch
        ),
        None,
    )


def cmd_admit(args: argparse.Namespace) -> int:
    """Atomically admit an already registered task or return a resumable WAIT."""
    root = main_root()
    worktree = validate_worktree_identity(args.worktree, args.branch, root)
    path = board_path(root)
    config = read_platform_config(root)
    main_branch = str(config.get("main_branch", "main"))
    with locked_json(path) as data:
        items = data.setdefault("items", [])
        current = _find_item(items, worktree, args.branch)
        if current is None:
            raise SystemExit(f"Agent admission blocked: no registered board entry for {worktree}.")
        if args.scope is not None:
            current["scope"] = args.scope
        current["heartbeat"] = utc_now()
        decision = _admit_item(root, current, items, main_branch=main_branch)
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_acknowledge(args: argparse.Namespace) -> int:
    """Record bounded evidence that a currently observed hard overlap is safe.

    Authorization is narrow by construction: only paths this task and
    ``--with-id`` are proven to currently both claim can be acknowledged, and
    only for that exact conflicting task identity.  A later unrelated path or
    a different conflicting task always needs its own decision.
    """
    root = main_root()
    worktree = validate_worktree_identity(args.worktree, args.branch, root)
    path = board_path(root)
    config = read_platform_config(root)
    main_branch = str(config.get("main_branch", "main"))
    reason = (args.reason or "").strip()
    if not reason:
        raise SystemExit("Agent board acknowledgment blocked: --reason must be a non-empty bounded justification.")
    requested = sorted({value.strip() for value in (args.path or []) if value.strip()})
    if not requested:
        raise SystemExit("Agent board acknowledgment blocked: at least one --path is required.")
    if len(requested) > MAX_ACKNOWLEDGED_PATHS:
        raise SystemExit(f"Agent board acknowledgment blocked: at most {MAX_ACKNOWLEDGED_PATHS} paths per acknowledgment.")
    with locked_json(path) as data:
        items = data.setdefault("items", [])
        current = _find_item(items, worktree, args.branch)
        if current is None:
            raise SystemExit(f"Agent board acknowledgment blocked: no registered board entry for {worktree}.")
        other = next((item for item in items if str(item.get("id", "")) == args.with_id and item is not current), None)
        if other is None:
            raise SystemExit(f"Agent board acknowledgment blocked: unknown conflicting board id {args.with_id!r}.")
        if _status(other, root, main_branch=main_branch, stale_hours=DEFAULT_STALE_HOURS):
            raise SystemExit(f"Agent board acknowledgment blocked: {args.with_id} is not a currently active task.")
        overlap = _claim_candidates(current, root, main_branch) & _owned_claim_paths(other, root, main_branch)
        unproven = [value for value in requested if value not in overlap]
        if unproven:
            raise SystemExit(
                "Agent board acknowledgment blocked: not a currently conflicting path with "
                f"{args.with_id}: {', '.join(unproven)}."
            )
        acknowledgments = current.setdefault("acknowledgments", [])
        acknowledgments.append(
            {
                "with_id": other.get("id"),
                "with_task": other.get("task", ""),
                "paths": requested,
                "reason": reason,
                "at": utc_now(),
            }
        )
    print(json.dumps({"acknowledged": requested, "with_id": args.with_id}, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    path = board_path()
    if not path.exists():
        return 0
    with locked_json(path) as data:
        items = data.setdefault("items", [])
        before = len(items)
        items[:] = [item for item in items if item.get("id") != args.id]
        if len(items) == before and not args.quiet:
            print(f"Board id not found: {args.id}")
    return 0


def _safe_to_remove(item: dict, problems: list[str]) -> bool:
    if "worktree-missing" in problems:
        return True
    if "merged-branch" not in problems:
        return False
    raw = item.get("worktree")
    if not raw:
        return True
    path = Path(raw).expanduser()
    return path.exists() and _worktree_clean(path)


def cmd_doctor(args: argparse.Namespace) -> int:
    root = main_root()
    path = board_path()
    if not path.exists():
        print("agent-board: ok (empty)")
        return 0
    config = read_platform_config(root)
    main_branch = str(config.get("main_branch", "main"))

    with locked_json(path) as data:
        items = data.setdefault("items", [])
        bad: list[tuple[dict, list[str]]] = []
        for item in items:
            problems = _status(item, root, main_branch=main_branch, stale_hours=args.stale_hours)
            if problems:
                bad.append((item, problems))

        if args.fix and bad:
            removable = {item["id"] for item, problems in bad if _safe_to_remove(item, problems)}
            items[:] = [item for item in items if item.get("id") not in removable]
            if removable:
                print("Removed safely stale entries:", ", ".join(sorted(removable)))
            bad = [(item, problems) for item, problems in bad if item.get("id") not in removable]

    if not bad:
        print("agent-board: ok")
        return 0
    for item, problems in bad:
        print(f"{item.get('id')}: {', '.join(problems)}")
    return 1


def find_id_for_current_worktree() -> str | None:
    path = board_path()
    if not path.exists():
        return None
    worktree = current_worktree_root()
    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data.get("items", []):
        if Path(item.get("worktree", "")).resolve() == worktree:
            return item.get("id")
    return None


def warn_current_worktree_scope_overlap(root: Path, worktree: Path, branch: str) -> None:
    """Emit an advisory conflict diagnostic at the pre-publication boundary."""
    path = board_path(root)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    items = data.get("items", [])
    if not isinstance(items, list):
        return
    scope = ""
    for item in items:
        if Path(str(item.get("worktree", ""))).expanduser().resolve() == worktree.resolve():
            scope = str(item.get("scope", ""))
            break
    _print_overlap_warning(scope_overlap_diagnostics(root, worktree, branch, scope, items))


def hard_scope_conflicts(root: Path, worktree: Path, branch: str) -> list[tuple[str, str, str]]:
    """Recompute current factual hard overlap against still-active claims.

    Read-only.  Reused before costly protected validation and again
    immediately before publication so a concrete file overlap introduced
    after admission is not silently carried through to expensive or delivery
    work.  Acknowledged pairs and stale/completed sibling claims are excluded,
    matching ``_admission_conflicts`` used at admission time.  A platform
    config that never wires up ``paths.agent_board`` (a profile that does not
    use multi-agent coordination) has no board to recheck, so it is treated
    the same as a missing board file rather than as an error.
    """
    try:
        path = board_path(root)
    except KeyError:
        return []
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("items", [])
    if not isinstance(items, list):
        return []
    config = read_platform_config(root)
    main_branch = str(config.get("main_branch", "main"))
    current = _find_item(items, worktree, branch)
    if current is None:
        return []
    return _admission_conflicts(root, current, items, main_branch=main_branch)


def enforce_scope_gate(root: Path, worktree: Path, branch: str) -> None:
    """Block costly work when factual scope now hard-overlaps an active task."""
    conflicts = hard_scope_conflicts(root, worktree, branch)
    if not conflicts:
        return
    rendered = "; ".join(f"{item_id} ({task}): {path}" for item_id, task, path in conflicts)
    raise HardScopeOverlap(
        "Unacknowledged hard scope overlap with an active task blocks further costly validation/publication: "
        f"{rendered}. Verify the overlap is safe and acknowledge it with `agent_board.py acknowledge`, "
        "or wait for the sibling task to finish, then retry."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Machine-local registry of active agent worktrees.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("doctor")
    p.add_argument("--fix", action="store_true")
    p.add_argument("--stale-hours", type=int, default=DEFAULT_STALE_HOURS)
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("start")
    p.add_argument("--task", required=True)
    p.add_argument("--scope", default="")
    p.add_argument("--branch", required=True)
    p.add_argument("--worktree", required=True)
    p.add_argument("--id")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("update")
    p.add_argument("--id", required=True)
    p.add_argument("--task")
    p.add_argument("--scope")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("admit", help="atomically claim concrete scope for an active multi-agent task")
    p.add_argument("--branch", required=True)
    p.add_argument("--worktree", required=True)
    p.add_argument("--scope", default=None)
    p.set_defaults(func=cmd_admit)

    p = sub.add_parser("acknowledge", help="record bounded evidence acknowledging a verified-safe same-file overlap")
    p.add_argument("--branch", required=True)
    p.add_argument("--worktree", required=True)
    p.add_argument("--with-id", required=True, help="board id of the currently conflicting active task")
    p.add_argument("--path", action="append", default=[], help="exact repository-relative conflicting path (repeatable)")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_acknowledge)

    p = sub.add_parser("finish")
    p.add_argument("--id", required=True)
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_finish)

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    raise SystemExit(args.func(args))
