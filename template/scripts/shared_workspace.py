#!/usr/bin/env python3
"""Bounded POSIX permission checks for a managed shared workspace.

Only dev-platform state and Git's common directory are covered.  Application
files, credentials and paths outside the registered checkout are deliberately
out of scope.
"""
from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, ContextManager, Iterable

try:
    import grp
except ImportError:  # pragma: no cover - Windows has no POSIX groups
    grp = None  # type: ignore[assignment]


ENV_GROUP = "DEV_PLATFORM_SHARED_GROUP"
DIRECTORY_MODE = stat.S_IRWXG | stat.S_ISGID
FILE_MODE = stat.S_IRGRP | stat.S_IWGRP
GIT_TREES = ("objects", "refs", "logs", "worktrees")
GIT_FILES = ("config", "FETCH_HEAD", "HEAD", "index", "ORIG_HEAD", "packed-refs", "shallow")
LIFECYCLE_PATH_DEFAULTS = {
    "worktrees": ".claude/worktrees",
    "agent_board": ".claude/agents-board.json",
    "main_merge_lock": ".claude/main-merge.lock",
    "pending_worktrees": ".claude/pending-worktrees.md",
    "pending_completed_worktree_cleanup": ".claude/pending-completed-worktree-cleanup.json",
    "friction_log": ".claude/agent-friction.jsonl",
    "friction_state": ".claude/agent-friction-state.json",
    "friction_reports": ".claude/reports/process-improvement",
}
RECURSIVE_LIFECYCLE_PATHS = {"friction_reports", "model_routing"}

# Stable, rarely-changing shared-repository configuration. Bootstrap/adoption
# and explicit repair own the write; ordinary lifecycle preflight only verifies
# it so that independent tasks never contend on ``.git/config.lock``.
SHARED_REPOSITORY_KEY = "core.sharedRepository"
SHARED_REPOSITORY_VALUE = "group"
MAIN_MERGE_LOCK_DEFAULT = ".claude/main-merge.lock"
# A registered path can disappear between discovery and inspection when Git runs
# ephemeral maintenance (lock files, temporary packs). Re-scan a bounded number
# of times before giving up rather than reporting a false persistent failure.
EPHEMERAL_RESCAN_ATTEMPTS = 3
_REPAIR_LOCK_TIMEOUT_SECONDS = 30.0


class SharedWorkspaceError(RuntimeError):
    """The collaboration contract cannot safely be checked or repaired."""


@dataclass(frozen=True)
class SharedGroup:
    gid: int
    name: str
    source: str


@dataclass(frozen=True)
class Finding:
    path: Path
    message: str
    repairable: bool


def posix_available() -> bool:
    return os.name == "posix" and hasattr(os, "chown") and grp is not None


def cooperative_umask() -> None:
    """Ensure platform-created files start group writable where POSIX applies."""
    if posix_available():
        os.umask(0o002)


def _group_for_gid(gid: int, source: str) -> SharedGroup:
    try:
        return SharedGroup(gid=gid, name=grp.getgrgid(gid).gr_name, source=source)
    except KeyError as exc:
        raise SharedWorkspaceError(f"shared group gid {gid} is not resolvable on this machine") from exc


def resolve_shared_group(root: Path) -> SharedGroup:
    if not posix_available():
        raise SharedWorkspaceError("POSIX group-mode enforcement is unavailable on this filesystem/platform")
    override = os.environ.get(ENV_GROUP, "").strip()
    if not override:
        return _group_for_gid(root.stat().st_gid, "checkout owner")
    try:
        entry = grp.getgrgid(int(override)) if override.isdecimal() else grp.getgrnam(override)
    except KeyError as exc:
        raise SharedWorkspaceError(f"{ENV_GROUP}={override!r} does not name a local group") from exc
    memberships = set(os.getgroups()) | {os.getegid()}
    if os.geteuid() != 0 and entry.gr_gid not in memberships:
        raise SharedWorkspaceError(f"{ENV_GROUP}={override!r} is not a group of the current user")
    return SharedGroup(gid=entry.gr_gid, name=entry.gr_name, source=ENV_GROUP)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise SharedWorkspaceError(f"cannot resolve Git common directory: {detail or 'git failed'}")
    return result.stdout.strip()


def integration_root(root: Path) -> Path:
    """Resolve the checkout containing the Git common directory, never a task cwd."""
    candidate = root.resolve()
    common = Path(_git(candidate, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = (candidate / common).resolve()
    return common.parent.resolve()


def git_common_dir(root: Path) -> Path:
    common = Path(_git(root, "rev-parse", "--git-common-dir"))
    return common.resolve() if common.is_absolute() else (root / common).resolve()


def _safe_root(path: Path) -> Path:
    resolved = path.resolve()
    home = Path.home().resolve()
    if resolved in {Path("/"), home}:
        raise SharedWorkspaceError(f"refusing broad shared-workspace operation at {resolved}")
    return resolved


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _walk_tree(path: Path, boundary: Path) -> Iterable[Path]:
    if not path.exists():
        return []
    if path.is_symlink() or not _within(path, boundary):
        raise SharedWorkspaceError(f"refusing symlink or boundary escape: {path}")
    entries: list[Path] = [path]
    for current, directories, files in os.walk(path, followlinks=False):
        current_path = Path(current)
        if current_path.is_symlink() or not _within(current_path, boundary):
            raise SharedWorkspaceError(f"refusing symlink or boundary escape: {current_path}")
        for name in [*directories, *files]:
            item = current_path / name
            if item.is_symlink():
                raise SharedWorkspaceError(f"refusing symlink in shared metadata: {item}")
            entries.append(item)
    return entries


def _registered_claude_path(integration: Path, relative: str) -> Path:
    """Resolve one configured platform path without trusting foreign entries.

    The configuration may register lifecycle state only below ``.claude``.
    Unknown siblings are deliberately never resolved or enumerated: tool
    runtimes are free to use that ignored directory for their own state.
    """
    candidate = integration / relative
    try:
        local = candidate.relative_to(integration)
    except ValueError as exc:
        raise SharedWorkspaceError(f"registered lifecycle path is outside the integration checkout: {relative}") from exc
    if not local.parts or local.parts[0] != ".claude":
        raise SharedWorkspaceError(f"registered lifecycle path is outside .claude: {relative}")
    if candidate.is_symlink() or not _within(candidate, integration):
        raise SharedWorkspaceError(f"refusing symlink or boundary escape in registered lifecycle path: {candidate}")
    return candidate


def _configured_paths_table(integration: Path) -> dict[str, object]:
    config_path = integration / ".dev-platform.toml"
    if not config_path.is_file():
        return {}
    try:
        with config_path.open("rb") as handle:
            loaded = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        # Configuration validation supplies the actionable diagnostic. Callers
        # here remain safely bounded to their defaults.
        return {}
    paths = loaded.get("paths", {})
    return paths if isinstance(paths, dict) else {}


def _configured_relative_path(integration: Path, key: str, default: str) -> str:
    value = _configured_paths_table(integration).get(key, default)
    if not isinstance(value, str) or not value:
        return default
    return value


def _lifecycle_paths(integration: Path) -> list[tuple[str, Path]]:
    """Return the reviewed lifecycle allowlist, never all ``.claude`` children."""
    configured = _configured_paths_table(integration)
    result: list[tuple[str, Path]] = []
    for key, default in LIFECYCLE_PATH_DEFAULTS.items():
        value = configured.get(key, default)
        if not isinstance(value, str) or not value:
            value = default
        path = _registered_claude_path(integration, value)
        result.append((key, path))
        # ``locked_json`` and friction logging create these sidecar locks.
        if key in {"agent_board", "friction_log"}:
            result.append((key, _registered_claude_path(integration, value + ".lock")))
    result.append(("model_routing", _registered_claude_path(integration, ".claude/model-routing")))
    return result


def registered_paths(root: Path) -> tuple[Path, Path, list[Path]]:
    """Return only the roots that platform operations are permitted to repair."""
    integration = _safe_root(integration_root(root))
    common = git_common_dir(integration)
    if not _within(common, integration.parent):
        raise SharedWorkspaceError(f"Git common directory is outside the registered checkout: {common}")
    paths: list[Path] = [integration]
    claude = integration / ".claude"
    if claude.exists():
        if claude.is_symlink() or not _within(claude, integration):
            raise SharedWorkspaceError(f"refusing symlink or boundary escape in registered lifecycle path: {claude}")
        paths.append(claude)
    for key, path in _lifecycle_paths(integration):
        if not path.exists():
            continue
        # Worktree directories are platform administration state, but their
        # contents are complete project checkouts and remain out of scope.
        if key in RECURSIVE_LIFECYCLE_PATHS:
            paths.extend(_walk_tree(path, integration))
        else:
            paths.append(path)
    paths.append(common)
    for name in GIT_TREES:
        paths.extend(_walk_tree(common / name, common))
    for name in GIT_FILES:
        candidate = common / name
        if candidate.exists():
            if candidate.is_symlink() or not _within(candidate, common):
                raise SharedWorkspaceError(f"refusing symlink or boundary escape: {candidate}")
            paths.append(candidate)
    return integration, common, list(dict.fromkeys(paths))


def _immutable_git_object(path: Path) -> bool:
    """Git object contents are immutable; group read is sufficient and safer."""
    if path.is_dir():
        return False
    parts = path.parts
    try:
        index = parts.index("objects")
    except ValueError:
        return False
    if index + 1 >= len(parts):
        return False
    return bool(re.fullmatch(r"[0-9a-f]{2}", parts[index + 1])) or parts[index + 1] == "pack"


def _expected_bits(path: Path) -> int:
    if path.is_dir():
        return DIRECTORY_MODE
    return stat.S_IRGRP if _immutable_git_object(path) else FILE_MODE


def _describe(path: Path, group: SharedGroup) -> str | None:
    info = path.stat()
    mode = stat.S_IMODE(info.st_mode)
    missing = _expected_bits(path) & ~info.st_mode
    if info.st_gid != group.gid:
        return f"gid={info.st_gid}, expected group {group.name} ({group.gid})"
    if missing:
        expected = "rwx+setgid" if path.is_dir() else ("r" if _immutable_git_object(path) else "rw")
        return f"mode={mode:04o}, missing group {expected}"
    return None


def _repair(path: Path, group: SharedGroup) -> None:
    info = path.stat()
    try:
        if info.st_gid != group.gid:
            os.chown(path, -1, group.gid)
        mode = stat.S_IMODE(path.stat().st_mode)
        desired = mode | _expected_bits(path)
        if desired != mode:
            path.chmod(desired)
    except PermissionError as exc:
        mode = stat.S_IMODE(info.st_mode)
        action = f"chgrp {group.name} {path} && chmod {'g+rwxs' if path.is_dir() else 'g+rw'} {path}"
        raise SharedWorkspaceError(f"unrepairable shared path {path} (gid={info.st_gid}, mode={mode:04o}); owner must run: {action}") from exc


def ensure_shared_path(path: Path, *, group: SharedGroup | None = None) -> None:
    """Apply the contract to one already-registered platform-owned path."""
    if not posix_available():
        return
    if path.is_symlink():
        raise SharedWorkspaceError(f"refusing symlink in shared state: {path}")
    # Unit/recovery callers can operate on a staged platform state directory
    # before a checkout is initialized; deriving from that directory retains
    # the same group contract without requiring Git discovery.
    group = group or resolve_shared_group(path.parent)
    _repair(path, group)


def read_shared_repository(integration: Path) -> str | None:
    """Return the configured ``core.sharedRepository`` value, or ``None`` when unset."""
    result = subprocess.run(
        ["git", "config", "--get", SHARED_REPOSITORY_KEY],
        cwd=integration,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        return None
    return result.stdout.strip() or None


def shared_repository_grants_group(value: str | None) -> bool:
    """True when the configured value gives the sharing group read/write access.

    Git accepts symbolic names, a small integer alias or an explicit octal mode.
    """
    if value is None:
        return False
    token = value.strip().lower()
    if token in {"group", "true", "1", "all", "world", "everybody", "2"}:
        return True
    try:
        mode = int(token, 8)
    except ValueError:
        return False
    return mode & 0o060 == 0o060


def configure_shared_repository(integration: Path) -> None:
    """Persist the stable shared-repository mode.

    Only bootstrap/adoption and an explicit repair path mutate this value; the
    ordinary lifecycle verifies it without rewriting an already-correct setting.
    """
    result = subprocess.run(
        ["git", "config", SHARED_REPOSITORY_KEY, SHARED_REPOSITORY_VALUE],
        cwd=integration,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip() or "git failed"
        raise SharedWorkspaceError(f"could not set {SHARED_REPOSITORY_KEY}={SHARED_REPOSITORY_VALUE}: {detail}")


def verify_shared_repository(integration: Path) -> Finding | None:
    """Read-only check that the shared-repository mode grants group access."""
    value = read_shared_repository(integration)
    if shared_repository_grants_group(value):
        return None
    observed = value if value is not None else "unset"
    return Finding(
        git_common_dir(integration) / "config",
        f"{SHARED_REPOSITORY_KEY}={observed}; expected a value granting group access (e.g. {SHARED_REPOSITORY_VALUE})",
        True,
    )


def _audit_permissions(root: Path, *, fix: bool) -> tuple[SharedGroup, list[Finding]]:
    """Audit registered POSIX permissions, tolerating an ephemeral path vanishing.

    A registered path that disappears between discovery and inspection triggers a
    bounded re-scan.  A permission, ownership, symlink or foreign-state finding on
    a path that still exists is durable and is always reported.
    """
    group: SharedGroup | None = None
    findings: list[Finding] = []
    for attempt in range(EPHEMERAL_RESCAN_ATTEMPTS):
        last_attempt = attempt == EPHEMERAL_RESCAN_ATTEMPTS - 1
        _integration, _common, paths = registered_paths(root)
        group = resolve_shared_group(_integration)
        findings = []
        restart = False
        for path in paths:
            try:
                detail = _describe(path, group)
                if detail is None:
                    continue
                if fix:
                    _repair(path, group)
                    detail = _describe(path, group)
                    if detail is None:
                        continue
            except FileNotFoundError:
                # The path is gone.  Re-scan from a fresh allowlist unless this is
                # the last attempt, where a still-missing path constrains nothing.
                if not last_attempt:
                    restart = True
                    break
                continue
            findings.append(Finding(path, detail, True))
        if not restart:
            break
    assert group is not None
    return group, findings


def audit(root: Path, *, fix: bool = False) -> tuple[SharedGroup | None, list[Finding]]:
    if not posix_available():
        return None, [Finding(root, "POSIX group-mode enforcement unavailable; no changes made", False)]
    return _audit_permissions(root, fix=fix)


def _default_integration_serializer(integration: Path) -> ContextManager[object]:
    """Reuse the existing serialized integration boundary for a rare repair."""
    from integration_state import serialized_integration

    relative = _configured_relative_path(integration, "main_merge_lock", MAIN_MERGE_LOCK_DEFAULT)
    return serialized_integration(
        integration, {"paths": {"main_merge_lock": relative}}, _REPAIR_LOCK_TIMEOUT_SECONDS
    )


def _repair_shared_repository(
    integration: Path,
    serializer: Callable[[Path], ContextManager[object]] | None,
) -> None:
    factory = serializer or _default_integration_serializer
    with factory(integration):
        # Re-check under serialization: a concurrent holder may already have
        # repaired the value, in which case this task must not rewrite it.
        if verify_shared_repository(integration) is None:
            return
        configure_shared_repository(integration)
        remaining = verify_shared_repository(integration)
    if remaining is not None:
        raise SharedWorkspaceError(
            f"shared-repository repair did not take effect: {remaining.path}: {remaining.message}"
        )


def preflight(
    root: Path,
    *,
    fix: bool = True,
    serializer: Callable[[Path], ContextManager[object]] | None = None,
) -> None:
    """Verify platform-owned collaboration state before a mutating lifecycle step.

    POSIX permissions on registered paths are repaired in place when ``fix`` is
    set.  Stable ``core.sharedRepository`` configuration is only verified; a
    required repair is serialized through the existing integration boundary and
    rechecked before the lifecycle continues.
    """
    cooperative_umask()
    group, findings = audit(root, fix=fix)
    if group is None:
        return
    if findings:
        details = "; ".join(f"{item.path}: {item.message}" for item in findings[:5])
        raise SharedWorkspaceError(f"shared-workspace preflight failed for group {group.name}: {details}")
    integration = _safe_root(integration_root(root))
    repository_finding = verify_shared_repository(integration)
    if repository_finding is None:
        return
    if not fix:
        raise SharedWorkspaceError(
            f"shared-workspace preflight failed for group {group.name}: "
            f"{repository_finding.path}: {repository_finding.message}"
        )
    _repair_shared_repository(integration, serializer)


def atomic_write_text(path: Path, text: str, *, group: SharedGroup | None = None) -> None:
    """Atomically publish a platform state file without regressing it to 0600."""
    cooperative_umask()
    path.parent.mkdir(parents=True, exist_ok=True)
    if posix_available():
        # Package validation also uses this writer in a short-lived directory
        # before it becomes a Git checkout.  The same group-derived contract is
        # still safe there without asking Git to resolve an integration root.
        group = group or resolve_shared_group(path.parent)
        _repair(path.parent, group)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        if posix_available() and group is not None:
            os.chown(temporary, -1, group.gid)
            os.chmod(temporary, stat.S_IMODE(Path(temporary).stat().st_mode) | FILE_MODE)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or repair bounded dev-platform shared-workspace permissions.")
    parser.add_argument("command", choices=("check", "fix"))
    args = parser.parse_args()
    fix = args.command == "fix"
    try:
        group, findings = audit(Path.cwd(), fix=fix)
    except SharedWorkspaceError as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 2
    if group is None:
        print("[warn] POSIX group-mode enforcement unavailable; no changes made")
        return 0
    findings = list(findings)
    try:
        integration = _safe_root(integration_root(Path.cwd()))
        repository_finding = verify_shared_repository(integration)
        if repository_finding is not None and fix:
            # An explicit operator repair may configure the stable value directly.
            configure_shared_repository(integration)
            repository_finding = verify_shared_repository(integration)
        if repository_finding is not None:
            findings.append(repository_finding)
    except SharedWorkspaceError as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            print(f"[fail] {finding.path}: {finding.message}")
        return 1
    print(f"[ok] shared workspace is group-writable for {group.name} ({group.source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
