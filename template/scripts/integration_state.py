from __future__ import annotations

import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

from _platform_common import ensure_shared_path, fetch_main, resolve_shared_group, run_git


def _lock_path(config: dict) -> str:
    return str(config.get("paths", {}).get("main_merge_lock", ".claude/main-merge.lock")).replace("\\", "/")


def _status_records(root: Path) -> list[tuple[str, tuple[str, ...]]]:
    """Return porcelain-v1 records without losing paths containing whitespace."""
    raw = run_git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=root).stdout
    fields = raw.split("\0")
    records: list[tuple[str, tuple[str, ...]]] = []
    index = 0
    while index < len(fields):
        record = fields[index]
        index += 1
        if not record:
            continue
        state, path = record[:2], record[3:]
        paths = [path]
        # With -z, rename/copy records carry the source path in the following
        # NUL-delimited field (the destination appears in this record).
        if ("R" in state or "C" in state) and index < len(fields):
            paths.append(fields[index])
            index += 1
        records.append((state, tuple(paths)))
    return records


def dirty_paths(root: Path, config: dict) -> list[str]:
    """List all relevant dirty paths, excluding only the platform's lock file."""
    lock = _lock_path(config)
    paths = {
        path.replace("\\", "/")
        for _state, record_paths in _status_records(root)
        for path in record_paths
        if path.replace("\\", "/") != lock
    }
    return sorted(paths)


def integration_clean(root: Path, config: dict) -> bool:
    return not dirty_paths(root, config)


def _format_paths(paths: list[str]) -> str:
    return ", ".join(paths) if paths else "(none reported)"


@contextmanager
def serialized_integration(root: Path, config: dict, timeout_seconds: float) -> Iterator[None]:
    relative = _lock_path(config)
    path = (root / relative).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    group = resolve_shared_group(root)
    ensure_shared_path(path.parent, group=group)
    with path.open("a+", encoding="utf-8") as lock_file:
        ensure_shared_path(path, group=group)
        if fcntl is None:
            yield
            return
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SystemExit("Another agent is still integrating into the main branch. Retry after it finishes.") from None
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def guard_before_protected_merge(
    integration: Path,
    config: dict,
    remote: str,
    main_branch: str,
    timeout_seconds: float,
) -> Iterator[None]:
    """Keep a short lock only around the GitHub merge-intent mutation.

    Required-check and merge-queue waits intentionally occur outside this
    boundary. Fetching and observing after acquiring it closes the window in
    which another local task dirties integration while the PR waits remotely.
    """
    with serialized_integration(integration, config, timeout_seconds):
        fetch_main(integration, remote, main_branch)
        paths = dirty_paths(integration, config)
        if paths:
            raise SystemExit(
                "Integration copy has divergent uncommitted state before protected remote merge intent; "
                "GitHub was not mutated. Affected paths: " + _format_paths(paths)
            )
        yield


def local_state_matches_remote_target(root: Path, config: dict, remote_main: str) -> bool:
    """Prove that the complete worktree snapshot equals the remote target.

    A normal ``git diff <tree>`` ignores untracked files. That is insufficient
    after a remote merge: an untracked local file can legitimately be the exact
    file that the remote target now tracks. Build a disposable index from the
    target and stage the observed worktree into it, then compare its tree and
    modes to the target. The real index and worktree are never touched.
    """
    descriptor, temporary_index = tempfile.mkstemp(prefix="dev-platform-equivalence-index-")
    os.close(descriptor)
    os.unlink(temporary_index)
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = temporary_index
    try:
        def invoke(args: list[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *args], cwd=root, env=env, text=True, capture_output=True, check=False
            )

        if invoke(["read-tree", remote_main]).returncode != 0:
            return False
        if invoke(["add", "-A", "--", "."]).returncode != 0:
            return False
        return invoke(["diff", "--cached", "--quiet", remote_main, "--"]).returncode == 0
    finally:
        try:
            os.unlink(temporary_index)
        except FileNotFoundError:
            pass


def normalize_equivalent_remote_state(root: Path, remote_main: str) -> None:
    """Align branch and index without overwriting content proven equal to remote."""
    run_git(["reset", "--mixed", remote_main], cwd=root)
