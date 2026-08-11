from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    from shared_workspace import SharedWorkspaceError, atomic_write_text, cooperative_umask, ensure_shared_path, preflight
except ModuleNotFoundError:  # Compatibility while an existing project is being upgraded by Copier.
    class SharedWorkspaceError(RuntimeError):
        pass

    def cooperative_umask() -> None:
        if os.name == "posix":
            os.umask(0o002)

    def ensure_shared_path(path: Path) -> None:
        return None

    def preflight(root: Path, *, fix: bool = True) -> None:
        cooperative_umask()

    def atomic_write_text(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


def run_git(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    cooperative_umask()
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
        return {
            "main_branch": "main",
            "workflow_profile": "standard",
            "harness_mode": "platform",
            "protected_main": True,
            "publish_mode": "pr",
            "pr_merge_mode": "auto",
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


def protected_main(config: dict[str, Any]) -> bool:
    # Legacy configs predate this key. Keep their old behavior until an explicit
    # reviewed rollout records the repository's protection contract.
    return bool(config.get("protected_main", False))


def publish_mode(config: dict[str, Any]) -> str:
    return str(config.get("publish_mode", "pr"))


def pr_merge_mode(config: dict[str, Any]) -> str:
    # Legacy PR projects were manual. New generated projects explicitly record auto.
    return str(config.get("pr_merge_mode", "manual"))


def _gh_auth_ok(root: Path, env: dict[str, str]) -> bool:
    auth = subprocess.run(
        ["gh", "auth", "status", "--hostname", "github.com"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return auth.returncode == 0


def _without_github_token_env(env: dict[str, str]) -> dict[str, str]:
    sanitized = env.copy()
    sanitized.pop("GH_TOKEN", None)
    sanitized.pop("GITHUB_TOKEN", None)
    return sanitized


def github_cli_env(root: Path) -> dict[str, str] | None:
    """Return a validated environment for gh without persisting or printing tokens.

    A valid explicit GH/GITHUB token keeps normal gh precedence. If an explicit
    token is stale, retry without token environment variables so a persistent gh
    keyring login can be used. If gh itself is still unauthenticated but git HTTPS
    credentials are already stored, reuse that credential only for this subprocess
    environment. This prevents stale shell/agent tokens from forcing repeated login.
    """
    if not shutil.which("gh"):
        return None

    env = os.environ.copy()
    if _gh_auth_ok(root, env):
        return env

    # gh gives GH_TOKEN/GITHUB_TOKEN precedence over its credential store. A stale
    # inherited token can therefore make `gh auth status` fail even though the
    # user's persistent keyring login is healthy. Validate the token-free path
    # before asking the user to authenticate again.
    sanitized = _without_github_token_env(env)
    if _gh_auth_ok(root, sanitized):
        return sanitized

    credential_env = sanitized.copy()
    credential_env["GIT_TERMINAL_PROMPT"] = "0"
    filled = subprocess.run(
        ["git", "credential", "fill"],
        cwd=root,
        env=credential_env,
        input="protocol=https\nhost=github.com\n\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if filled.returncode != 0:
        return None
    values: dict[str, str] = {}
    for line in filled.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    token = values.get("password")
    if not token:
        return None

    candidate = sanitized.copy()
    candidate["GH_TOKEN"] = token
    return candidate if _gh_auth_ok(root, candidate) else None


@contextmanager
def locked_json(path: Path) -> Iterator[dict[str, Any]]:
    cooperative_umask()
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_shared_path(path.parent)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        ensure_shared_path(lock_path)
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
            atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
