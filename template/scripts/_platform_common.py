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
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=check,
    )


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
        return {
            "main_branch": "main",
            "paths": {
                "worktrees": ".claude/worktrees",
                "agent_board": ".claude/agents-board.json",
                "friction_log": ".claude/agent-friction.jsonl",
                "checks": "dev-platform/checks.toml",
            },
        }

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
