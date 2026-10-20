"""Sandboxed writer launch: an LLM writer run under sandbox-runtime (``srt``) with a generated OS profile.

The profile is generated from the writer's own paths and the protected integration paths. Every
prerequisite is checked explicitly and a missing one raises; there is no unsandboxed fallback.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from _platform_common import credential_free_env

SANDBOX_RUNTIME_VERSION = "0.0.79"
ANTHROPIC_HOSTS = ["api.anthropic.com", "claude.ai", "platform.claude.com"]
DENY_READ_HOME = ["~/.ssh", "~/.config/gh", "~/.gitconfig", "~/.git-credentials", "~/.netrc", "~/.aws", "~/.gnupg",
                  "~/Library/Keychains", "~/.claude", "~/.claude.json", "~/.config/dev-platform",
                  "~/Library/Application Support", "~/.npmrc", "~/.docker"]
DENY_WRITE_HOME = ["~/.claude", "~/.claude.json", "~/.config", "~/.ssh"]
TOKEN_SETTING = "[independent_review.login.claude] token_file"
TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"


class SandboxedWriterError(RuntimeError):
    pass


def require_macos() -> None:
    if sys.platform != "darwin":
        raise SandboxedWriterError(
            f"the sandboxed writer is proven only on macOS; refusing to launch on platform {sys.platform!r}")


def srt_launcher() -> list[str]:
    if shutil.which("npx") is None:
        raise SandboxedWriterError("npx is not on PATH; it is required to run the pinned sandbox runtime")
    return ["npx", "--yes", f"@anthropic-ai/sandbox-runtime@{SANDBOX_RUNTIME_VERSION}"]


def require_writer_cli(name: str = "claude") -> str:
    found = shutil.which(name)
    if found is None:
        raise SandboxedWriterError(f"the writer CLI {name!r} is not on PATH")
    return found


def _real(path: Path | str) -> str:
    return os.path.realpath(os.path.expanduser(str(path)))


def _git(root: Path, *args: str) -> str:
    from lifecycle_workers import SAFE_GIT  # one hardening definition for every harness git call

    env = {key: value for key, value in credential_free_env(dict(os.environ)).items()
           if key != TOKEN_ENV and not key.startswith("GIT_DIR") and key not in {"GIT_WORK_TREE", "GIT_COMMON_DIR"}}
    done = subprocess.run(["git", *SAFE_GIT, "-C", str(root), *args], text=True, capture_output=True,
                          check=False, stdin=subprocess.DEVNULL, env=env)
    if done.returncode:
        raise SandboxedWriterError(f"git {' '.join(args)} failed in {root}: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout.strip()


def protected_paths(integration_root: Path) -> list[str]:
    root = _real(integration_root)
    common = Path(_git(Path(root), "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = Path(root) / common
    paths = [root, _real(common)]
    for line in _git(Path(root), "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            paths.append(_real(line[len("worktree "):]))
    return list(dict.fromkeys(paths))


def local_remote_paths(integration_root: Path) -> list[str]:
    """Realpaths of every local (path or ``file://``) fetch/push URL of the integration repository's remotes."""
    from urllib.parse import urlsplit

    paths = []
    for remote in _git(integration_root, "remote").split():
        for url in _git(integration_root, "remote", "get-url", "--all", remote).splitlines() + \
                _git(integration_root, "remote", "get-url", "--push", "--all", remote).splitlines():
            parsed = urlsplit(url)
            if parsed.scheme == "file":
                paths.append(_real(parsed.path))
            elif not parsed.scheme and url.startswith("/"):
                paths.append(_real(url))
    return list(dict.fromkeys(paths))


def _inside(path: str, parent: str) -> bool:
    return path == parent or path.startswith(parent.rstrip("/") + "/")


def _operator_path(operator_home: Path, entry: str) -> str:
    if not entry.startswith("~/"):
        raise SandboxedWriterError(f"home-relative profile entry {entry!r} must start with ~/")
    return os.path.realpath(os.path.join(operator_home, entry[2:]))


def build_profile(*, checkout: Path, home: Path, tmp: Path, protected: list[str], operator_home: Path,
                  token_file: Path, extra_deny_write: tuple[str, ...] | list[str] = (),
                  platform_root: Path) -> dict[str, Any]:
    """The srt settings for one writer launch, with every path absolute.

    The sandbox runs with ``HOME`` set to the scratch home, so home-relative deny entries are resolved
    here against the operator's real home rather than left as ``~/...`` for the sandbox to expand.
    """
    operator_home = Path(_real(operator_home))
    allow = [_real(checkout), _real(home), _real(tmp)]
    if _real(home) == str(operator_home):
        raise SandboxedWriterError(f"the writer home {home} must be a scratch home, not the operator home")
    protected = [_real(p) for p in protected]
    platform = _real(platform_root)
    token = _real(token_file)
    deny_write = [*protected, *[_real(p) for p in extra_deny_write],
                  *[_operator_path(operator_home, entry) for entry in DENY_WRITE_HOME], token, platform]
    deny_read = [*[_operator_path(operator_home, entry) for entry in DENY_READ_HOME], *protected,
                 *[_real(p) for p in extra_deny_write], token, platform]
    deny_write, deny_read = list(dict.fromkeys(deny_write)), list(dict.fromkeys(deny_read))
    for path in allow:
        for denied in deny_write + deny_read:
            if _inside(path, denied) or _inside(denied, path):
                raise SandboxedWriterError(f"writable path {path} overlaps the protected path {denied}")
    return {"network": {"allowedDomains": list(ANTHROPIC_HOSTS), "deniedDomains": []},
            "filesystem": {"allowWrite": allow,
                           "denyWrite": deny_write,
                           "denyRead": deny_read}}


def write_profile(profile: dict[str, Any], profile_path: Path) -> Path:
    target = Path(_real(profile_path))
    for root in profile["filesystem"]["allowWrite"]:
        if _inside(str(target), root):
            raise SandboxedWriterError(f"profile path {target} is inside the writable root {root}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profile, indent=2, sort_keys=True))
    return target


def claude_token_file(config: dict[str, Any]) -> Path:
    try:
        token_file = config["independent_review"]["login"]["claude"]["token_file"]
    except (KeyError, TypeError):
        raise SandboxedWriterError(f"operator setting {TOKEN_SETTING} is missing") from None
    if not isinstance(token_file, str) or not token_file.strip():
        raise SandboxedWriterError(f"operator setting {TOKEN_SETTING} must be a non-empty path")
    return Path(os.path.expanduser(token_file))


def read_claude_token(config: dict[str, Any]) -> str:
    path = claude_token_file(config)
    try:
        info = path.stat()
    except OSError as error:
        raise SandboxedWriterError(f"token file {path} named by {TOKEN_SETTING} is not readable: {error.strerror}") from None
    if not stat.S_ISREG(info.st_mode):
        raise SandboxedWriterError(f"token file {path} is not a regular file")
    if info.st_mode & 0o077:
        raise SandboxedWriterError(f"token file {path} is accessible by group or others; its mode must be 0600")
    value = path.read_text().strip()
    if not value:
        raise SandboxedWriterError(f"token file {path} is empty")
    return value


def sandboxed_command(argv: list[str], *, launcher: list[str], profile_path: Path) -> list[str]:
    """srt re-joins its argv into one shell string, so the writer argv travels as one ``bash -c`` script."""
    return [*launcher, "--settings", str(profile_path), "bash", "-c", shlex.join(argv)]


def srt_tmp() -> Path:
    path = Path(f"/private/tmp/dp-srt-{os.getuid()}")
    if not path.exists():
        path.mkdir(mode=0o700)
        os.chmod(path, 0o700)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise SandboxedWriterError(f"{path} exists but is not a directory owned by the current user")
    return path


def sandboxed_env(base_env: dict[str, str], *, home: Path, token: str, writer_tmp: Path) -> dict[str, str]:
    """The srt process environment.

    srt (0.0.79) ignores ``TMPDIR``/``CLAUDE_CODE_TMPDIR`` assigned inside the sandboxed command and sets the
    writer's ``TMPDIR`` from the ``CLAUDE_CODE_TMPDIR`` it inherits, so the writer tmp is passed here; the
    outer ``TMPDIR`` stays short for srt's own Unix socket (proven by the BR-576 acceptance probes).
    """
    env = credential_free_env(dict(base_env), home)
    env.pop(TOKEN_ENV, None)
    short = str(srt_tmp())
    env.update(TMPDIR=short, TMP=short, TEMP=short, CLAUDE_CODE_TMPDIR=str(writer_tmp))
    env[TOKEN_ENV] = token
    return env


def operator_home() -> Path:
    """The operator's real home from the account database, independent of an inherited ``HOME``."""
    import pwd

    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def launch_sandboxed_writer(argv: list[str], checkout: Path, *, integration_root: Path, platform_root: Path,
                            workdir: Path, home: Path, tmp: Path, config: dict[str, Any],
                            runner: Callable[..., Any] | None = None, timeout: int | None = None) -> Any:
    import lifecycle_workers

    runner = lifecycle_workers.run_in_session if runner is None else runner
    require_macos()
    launcher = srt_launcher()
    require_writer_cli(argv[0] if argv else "claude")
    token = read_claude_token(config)
    profile = build_profile(checkout=checkout, home=home, tmp=tmp, protected=protected_paths(integration_root),
                            operator_home=operator_home(), token_file=claude_token_file(config),
                            extra_deny_write=local_remote_paths(integration_root), platform_root=platform_root)
    profile_path = write_profile(profile, Path(workdir) / "srt-settings.json")
    command = sandboxed_command(argv, launcher=launcher, profile_path=profile_path)
    env = sandboxed_env(os.environ, home=home, token=token, writer_tmp=tmp)
    runtime_tmp = Path(env["TMPDIR"])
    return lifecycle_workers.run_llm(command, checkout, tmp=tmp, env={k: v for k, v in env.items() if k != TOKEN_ENV},
                                     runner=runner, timeout=timeout, home=home, runtime_tmp=runtime_tmp,
                                     extra_env={TOKEN_ENV: token})
