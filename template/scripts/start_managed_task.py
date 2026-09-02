#!/usr/bin/env python3
"""Safely start and materialize a managed OpenSpec task outside integration main."""
from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from _platform_common import (
    atomic_write_text,
    current_worktree_root,
    locked_json,
    machine_path,
    profile,
    read_platform_config,
    run_git,
    utc_now,
)
from managed_task import (
    ManagedTaskError,
    Package,
    canonical_provenance_candidates,
    discover_task,
    import_task,
    read_task_state,
    resolve_canonical_provenance,
    write_task_state,
)
from managed_project_status import ManagedProjectStatusError, reconcile
from start_task import StartedTask, cleanup_started_task, start_task
from start_task import admission_reason, admit_task


START_TRANSACTION_DIR = ".managed-start-transactions"


class ManagedAdmissionWait(RuntimeError):
    """Managed package/worktree are preserved while a hard claim is active."""


def _transaction_path(worktrees_root: Path, change: str) -> Path:
    return worktrees_root / START_TRANSACTION_DIR / f"{change}.json"


@contextmanager
def managed_start_transaction(root: Path, package: Package) -> Iterator[tuple[dict[str, object], bool]]:
    """Persist and lock one managed start before any board/project mutation.

    The transaction is machine-local and task-scoped. The per-change lock
    serializes only repeated starts of the exact same managed change; unrelated
    managed tasks retain independent lifecycle state.
    """
    worktrees_root = machine_path("worktrees", root)
    worktree = (worktrees_root / package.change).resolve()
    branch = f"agent/{package.change}"
    path = _transaction_path(worktrees_root, package.change)
    completed = False

    def _fresh_transaction() -> dict[str, object]:
        return {
            "version": 1,
            "state": "creating",
            "attempt_id": uuid.uuid4().hex,
            "source_issue": package.source_issue,
            "target_repository": package.target_repository,
            "change": package.change,
            "package_revision": package.revision,
            "branch": branch,
            "worktree": str(worktree),
            "created_at": utc_now(),
        }

    with locked_json(path) as data:
        created = "source_issue" not in data

        expected = {
            "version": 1,
            "state": "creating",
            "source_issue": package.source_issue,
            "target_repository": package.target_repository,
            "change": package.change,
            "package_revision": package.revision,
            "branch": branch,
            "worktree": str(worktree),
        }

        if not created:
            mismatches = [key for key, value in expected.items() if data.get(key) != value]
            if (
                mismatches == ["package_revision"]
                and data.get("state") == "creating"
                and _managed_start_left_no_task_state(root, worktree, branch)
            ):
                # The prior attempt failed before creating any task worktree,
                # branch or board entry and only the package revision changed.
                # Supersede the proven-empty stale transaction in place.
                created = True
            elif mismatches:
                raise ManagedTaskError(
                    "existing managed-start transaction does not match the requested package "
                    f"({', '.join(mismatches)}); inspect {path} before retrying"
                )

        if created:
            data.clear()
            data.update(_fresh_transaction())

        mismatches = [key for key, value in expected.items() if data.get(key) != value]
        if mismatches:
            raise ManagedTaskError(
                "existing managed-start transaction does not match the requested package "
                f"({', '.join(mismatches)}); inspect {path} before retrying"
            )
        if not isinstance(data.get("attempt_id"), str) or not data["attempt_id"]:
            raise ManagedTaskError("managed-start transaction is missing its attempt identity")

        # locked_json normally persists at context exit. Persist once before
        # yielding too, so a crash during worktree/board creation cannot leave
        # partial lifecycle state without the transaction that owns it.
        atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        try:
            yield data, created
        except ManagedAdmissionWait:
            # WAIT deliberately retains the worktree/package, so the owning
            # transaction must stay too.
            raise
        except Exception:
            # Roll back only a transaction we can prove left no task state.
            # If the proof itself is unreliable (e.g. ambiguous board), fail
            # closed and keep the transaction for conservative recovery.
            try:
                empty = _managed_start_left_no_task_state(root, worktree, branch)
            except Exception:
                empty = False
            if empty:
                path.unlink(missing_ok=True)
            raise
        else:
            completed = True

    if completed:
        path.unlink(missing_ok=True)


def _registered_worktrees(root: Path) -> set[Path]:
    result = run_git(["worktree", "list", "--porcelain"], cwd=root, check=False)
    if result.returncode != 0:
        raise ManagedTaskError("managed-start recovery cannot inspect registered Git worktrees")
    registered: set[Path] = set()
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            registered.add(Path(line.removeprefix("worktree ")).resolve())
    return registered


def _branch_exists(root: Path, branch: str) -> bool:
    result = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root, check=False)
    return result.returncode == 0


def _branch_has_no_unique_commits(root: Path, branch: str, main_branch: str) -> bool:
    result = run_git(["rev-list", "--count", f"{main_branch}..{branch}"], cwd=root, check=False)
    if result.returncode != 0:
        raise ManagedTaskError(f"managed-start recovery cannot compare partial branch {branch!r} with {main_branch!r}")
    try:
        return int(result.stdout.strip()) == 0
    except ValueError as exc:
        raise ManagedTaskError("managed-start recovery received an unreadable branch comparison") from exc


def _dirty_paths(worktree: Path) -> list[str]:
    result = run_git(["status", "--porcelain", "--untracked-files=all"], cwd=worktree, check=False)
    if result.returncode != 0:
        raise ManagedTaskError(f"managed-start recovery cannot inspect partial worktree {worktree}")
    return [line[3:] for line in result.stdout.splitlines() if len(line) >= 4]


def _partial_path_is_owned(path: str, change: str) -> bool:
    prefix = f"openspec/changes/{change}/"
    return path == ".managed-task-state.json" or path == prefix.rstrip("/") or path.startswith(prefix)


def _board_item_for_identity(root: Path, worktree: Path, branch: str) -> dict[str, object] | None:
    try:
        path = machine_path("agent_board", root)
    except KeyError:
        return None
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagedTaskError(f"managed-start recovery cannot read agent board {path}") from exc
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        raise ManagedTaskError("managed-start recovery found an invalid agent board")
    matches = [
        item
        for item in items
        if isinstance(item, dict)
        and Path(str(item.get("worktree", ""))).expanduser().resolve() == worktree.resolve()
        and str(item.get("branch", "")) == branch
    ]
    if len(matches) > 1:
        raise ManagedTaskError(
            f"managed-start recovery found multiple board entries for {branch} at {worktree}; refusing ambiguous cleanup"
        )
    if not matches:
        return None
    item = matches[0]
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id:
        raise ManagedTaskError("managed-start recovery found a board entry without a usable id")
    return item


def _managed_start_left_no_task_state(root: Path, worktree: Path, branch: str) -> bool:
    """True only when the exact worktree path, branch ref and board entry are all absent.

    Shared by transaction failure cleanup and stale-transaction retry supersession.
    Any ambiguous board state raises through ``_board_item_for_identity`` rather than
    reporting emptiness.
    """
    if worktree.exists():
        return False
    if _branch_exists(root, branch):
        return False
    if _board_item_for_identity(root, worktree, branch) is not None:
        return False
    return True


def recover_incomplete_managed_start(
    root: Path,
    package: Package,
    transaction: dict[str, object],
) -> bool:
    """Repair only safe non-canonical state belonging to this exact task.

    Recovery never runs a global prune and never touches a sibling task.
    Deletion is allowed only for the exact registered worktree/branch named by
    the transaction, with no unique commits and no unrelated dirty paths.
    """
    worktree = Path(str(transaction["worktree"])).resolve()
    branch = str(transaction["branch"])
    main_branch = str(read_platform_config(root).get("main_branch", "main"))
    path_exists = worktree.exists()
    branch_exists = _branch_exists(root, branch)
    board_item = _board_item_for_identity(root, worktree, branch)

    if not path_exists and not branch_exists and board_item is None:
        return False

    if path_exists and canonical_provenance_candidates(worktree, package.change):
        return False

    if not path_exists:
        raise ManagedTaskError(
            f"managed-start recovery found branch/board state for {branch} but no exact worktree {worktree}; "
            "refusing to guess cleanup ownership"
        )

    state = read_task_state(worktree)
    if state is not None and (
        state["source_issue"].lower() != package.source_issue.lower() or state["change"] != package.change
    ):
        raise ManagedTaskError(
            f"partial managed worktree {worktree} carries task state for "
            f"{state['source_issue']} ({state['change']}), not {package.source_issue} ({package.change})"
        )

    if worktree not in _registered_worktrees(root):
        raise ManagedTaskError(
            f"non-canonical path {worktree} is not an exact registered Git worktree; "
            "ownership cannot be proven automatically, so it was left untouched"
        )

    actual = run_git(["branch", "--show-current"], cwd=worktree, check=False)
    actual_branch = actual.stdout.strip() if actual.returncode == 0 else ""
    if actual_branch != branch:
        raise ManagedTaskError(
            f"partial managed worktree {worktree} is registered on {actual_branch or 'DETACHED'}, "
            f"not expected branch {branch}; refusing cleanup"
        )
    if not branch_exists:
        raise ManagedTaskError(
            f"partial managed worktree {worktree} has expected checkout branch {branch} but the local branch ref is missing"
        )
    if not _branch_has_no_unique_commits(root, branch, main_branch):
        raise ManagedTaskError(
            f"partial managed branch {branch} contains commits not present on {main_branch}; "
            "refusing destructive retry cleanup"
        )

    unexpected = [path for path in _dirty_paths(worktree) if not _partial_path_is_owned(path, package.change)]
    if unexpected:
        raise ManagedTaskError(
            f"partial managed worktree {worktree} has unrelated dirty paths "
            f"({', '.join(unexpected[:5])}); refusing cleanup"
        )

    if board_item is not None:
        expected_task = f"Managed task {package.source_issue}"
        task = str(board_item.get("task", ""))
        if task != expected_task:
            raise ManagedTaskError(
                f"exact board entry for {branch} belongs to {task!r}, not {expected_task!r}; refusing cleanup"
            )
        board_id = str(board_item["id"])
    else:
        board_id = None

    started = StartedTask(profile="multi-agent", branch=branch, task_root=worktree, board_id=board_id)
    cleanup_started_task(root, started)

    if worktree.exists():
        raise ManagedTaskError(f"managed-start recovery could not remove partial worktree {worktree}")
    if _branch_exists(root, branch):
        raise ManagedTaskError(f"managed-start recovery could not remove partial branch {branch}")
    if _board_item_for_identity(root, worktree, branch) is not None:
        raise ManagedTaskError(f"managed-start recovery could not remove the exact board entry for {branch}")

    print(f"Recovered incomplete managed start for {package.source_issue}; sibling task state was left untouched.")
    return True


def _resume_existing_managed_task(
    root: Path,
    package: Package,
    existing_root: Path,
    scope: str,
) -> tuple[StartedTask, str, bool]:
    resolve_canonical_provenance(existing_root, source_issue=package.source_issue, change=package.change)
    # Bounded migration for tasks created before task-level state was
    # introduced. It records identity only and never reimports the transport
    # package over the repository-local change.
    write_task_state(existing_root, package)
    branch = run_git(["branch", "--show-current"], cwd=existing_root).stdout.strip()
    if not branch:
        raise ManagedTaskError(f"existing managed task worktree is detached: {existing_root}")
    started = StartedTask(profile="multi-agent", branch=branch, task_root=existing_root)
    decision = admit_task(root, started, scope if scope else None)
    desired_status = "Blocked" if decision["decision"] == "WAIT" else "In progress"
    reconciliation = reconcile(existing_root, desired_status, source_issue=package.source_issue)
    if reconciliation is None:
        raise ManagedProjectStatusError("managed resume lost its source Issue identity")
    print(
        f"Managed Project status {'updated' if reconciliation.changed else 'already current'}: "
        f"{package.source_issue} -> {desired_status}"
    )
    if decision["decision"] == "WAIT":
        raise ManagedAdmissionWait(admission_reason(decision))
    return started, package.prepared_against, True


def _start_new_managed_task(
    root: Path,
    package: Package,
    reference: str,
    scope: str,
    acknowledge_source_issue_revision: str | None,
) -> tuple[StartedTask, str, bool]:
    started = start_task(
        root,
        package.change,
        task=f"Managed task {package.source_issue}",
        scope=scope or f"openspec/changes/{package.change}",
        admission=False,
    )
    try:
        imported, current_main, reused = import_task(
            started.task_root,
            reference,
            expected_revision=package.revision,
            acknowledge_source_issue_revision=acknowledge_source_issue_revision,
        )
        decision = admit_task(root, started, scope if scope else None)
        desired_status = "Blocked" if decision["decision"] == "WAIT" else "In progress"
        reconciliation = reconcile(
            started.task_root,
            desired_status,
            source_issue=package.source_issue,
        )
        if reconciliation is None:
            raise ManagedProjectStatusError("managed start lost its source Issue identity")
        print(
            f"Managed Project status {'updated' if reconciliation.changed else 'already current'}: "
            f"{package.source_issue} -> {desired_status}"
        )
        if decision["decision"] == "WAIT":
            raise ManagedAdmissionWait(admission_reason(decision))
    except ManagedAdmissionWait:
        # WAIT is a resumable state. Keep the registered worktree and the
        # canonical package so the next explicit invocation can re-check it.
        raise
    except Exception:
        cleanup_started_task(root, started)
        raise
    return started, current_main, reused


def start_managed_task(
    root: Path, reference: str, scope: str = "", *, acknowledge_source_issue_revision: str | None = None
) -> tuple[StartedTask, str, bool]:
    """Discover before task creation, then materialize in the task checkout only."""
    package = discover_task(root, reference)
    config = read_platform_config(root)
    if profile(config) != "multi-agent":
        return _start_new_managed_task(root, package, reference, scope, acknowledge_source_issue_revision)

    with managed_start_transaction(root, package) as (transaction, _created):
        existing_root = Path(str(transaction["worktree"])).resolve()
        if existing_root.is_dir() and canonical_provenance_candidates(existing_root, package.change):
            return _resume_existing_managed_task(root, package, existing_root, scope)

        recover_incomplete_managed_start(root, package, transaction)
        return _start_new_managed_task(root, package, reference, scope, acknowledge_source_issue_revision)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start a managed backlog task without writing to integration main.")
    parser.add_argument("issue", help="owner/repo#N or GitHub issue URL")
    parser.add_argument("--scope", default="", help="optional task scope for multi-agent board registration")
    parser.add_argument(
        "--acknowledge-source-issue-revision",
        metavar="BODY_SHA256",
        help="explicitly keep this package's existing scope despite source-Issue drift; "
        "value must equal the currently observed body_sha256 from the blocking diagnostic",
    )
    args = parser.parse_args()
    root = current_worktree_root()
    try:
        started, current_main, reused = start_managed_task(
            root, args.issue, args.scope,
            acknowledge_source_issue_revision=args.acknowledge_source_issue_revision,
        )
    except ManagedAdmissionWait as exc:
        print(f"Managed task waiting: {exc}")
        return 3
    except (ManagedTaskError, ManagedProjectStatusError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Managed task start blocked: {exc}")
        return 2
    print(f"Managed task {'reused' if reused else 'materialized'} in {started.task_root}")
    print(f"Branch: {started.branch}")
    if started.board_id:
        print(f"Board: {started.board_id}")
    print(f"Current origin/main: {current_main}")
    print("Next: perform semantic preflight in the task checkout, then use the OpenSpec lifecycle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
