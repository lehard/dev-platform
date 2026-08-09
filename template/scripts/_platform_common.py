from __future__ import annotations

import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


def run_git(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=check)


def current_worktree_root() -> Path:
    result = run_git(["rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip()).resolve()


def main_root() -> Path:
    root = current_worktree_root()
    common = run_git(["rev-parse", "--git-common-dir"], cwd=root).stdout.strip()
    common_path = Path(common)
    if not common_path.is_absolute():
        common_path = (root / common_path).resolve()
    return common_path.parent


def read_platform_config(root: Path | None = None) -> dict[str, Any]:
    root = root or current_worktree_root()
    path = root / ".dev-platform.toml"
    if not path.exists():
        return {"main_branch": "main", "workflow_profile": "standard", "harness_mode": "platform", "publish_mode": "pr", "paths": {"worktrees": ".claude/worktrees", "agent_board": ".claude/agents-board.json", "friction_log": ".claude/agent-friction.jsonl", "checks": "dev-platform/checks.toml"}}
    import tomllib
    with path.open("rb") as fh:
        return tomllib.load(fh)


def machine_path(key: str, root: Path | None = None) -> Path:
    root = root or main_root()
    config = read_platform_config(current_worktree_root())
    relative = config.get("paths", {}).get(key)
    if not relative:
        raise KeyError(f"Missing paths.{key} in .dev-platform.toml")
    return (root / relative).resolve()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def remote_ref(remote: str, branch: str) -> str:
    return f"refs/remotes/{remote}/{branch}"


def fetch_main(root: Path, remote: str, branch: str) -> str:
    run_git(["fetch", "--prune", remote, branch], cwd=root)
    result = run_git(["rev-parse", remote_ref(remote, branch)], cwd=root)
    return result.stdout.strip()


def ref_sha(root: Path, ref: str) -> str | None:
    result = run_git(["rev-parse", "--verify", ref], cwd=root, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def relation(root: Path, left: str, right: str) -> str:
    left_sha = ref_sha(root, left)
    right_sha = ref_sha(root, right)
    if not left_sha or not right_sha:
        return "missing"
    if left_sha == right_sha:
        return "equal"
    left_is_ancestor = run_git(["merge-base", "--is-ancestor", left, right], cwd=root, check=False).returncode == 0
    right_is_ancestor = run_git(["merge-base", "--is-ancestor", right, left], cwd=root, check=False).returncode == 0
    if left_is_ancestor:
        return "behind"
    if right_is_ancestor:
        return "ahead"
    return "diverged"


def require_origin(root: Path, remote: str = "origin") -> None:
    result = run_git(["remote", "get-url", remote], cwd=root, check=False)
    if result.returncode != 0:
        raise SystemExit(f"Git remote {remote!r} is required for sync/publish.")


def profile(config: dict[str, Any]) -> str:
    return str(config.get("workflow_profile", "standard"))


def harness_mode(config: dict[str, Any]) -> str:
    return str(config.get("harness_mode", "platform"))


def publish_mode(config: dict[str, Any]) -> str:
    return str(config.get("publish_mode", "pr"))


@contextmanager
def locked_json(path: Path) -> Iterator[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc
            else:
                data = {"version": 1, "items": []}
            yield data
            fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                    json.dump(data, tmp, ensure_ascii=False, indent=2)
                    tmp.write("\n")
                os.replace(tmp_name, path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
