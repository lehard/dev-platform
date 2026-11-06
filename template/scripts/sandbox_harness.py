#!/usr/bin/env python3
"""Credential-free disposable checkouts and result validation for the sandboxed Claude writer.

The writer process never holds a Git credential and its checkout stays data: every git command
after it ran uses a harness-owned clone, and only its result commits are imported.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import stat
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from _platform_common import credential_free_env
import disposable_repository_sandbox

HEAD = re.compile(r"[0-9a-f]{40}")
# Hardening for every harness git invocation (never trust repo-local hooks or fsmonitor, never recurse into
# submodules). ``diff.ignoreSubmodules`` is deliberately not set here: it would hide gitlinks from result validation.
SAFE_GIT = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "submodule.recurse=false")
# Harness merges and commits never depend on an ambient git identity (CI runners have none).
HARNESS_IDENTITY = ("-c", "user.name=Lifecycle harness", "-c", "user.email=lifecycle@localhost")
EVIDENCE_NAMES = ("verification.md", "automated-checks.json")
# Files the harness itself installs into a writer checkout; never candidate content.
INSTALLED_FILES = (".dev-platform.toml", disposable_repository_sandbox.MARKER)
SOURCE_CONTRACT = Path("dev-platform") / "source-contract.toml"


class WorkerError(RuntimeError):
    pass



def scratch_home(root: Path, home_files: list[str] | tuple[str, ...] = (), *, source_home: Path | None = None) -> Path:
    """Create a scratch HOME holding only the LLM CLI's own login files (relative to the real HOME)."""
    source = source_home or Path.home()
    home = root / "llm-home"
    home.mkdir(parents=True, exist_ok=True)
    for relative in home_files:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or path.parts[:2] in ((".config", "gh"),) or path.parts[:1] == (".ssh",):
            raise WorkerError(f"refusing to copy {relative} into the LLM home")
        if (source / path).is_file():
            (home / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / path, home / path)
    return home


def live_group_members(pgid: int) -> list[str]:
    """The ``ps`` rows (``pid stat``) of the members of process group ``pgid`` that are not zombies."""
    listing = subprocess.run(["ps", "-A", "-o", "pid=,pgid=,stat="], capture_output=True, text=True, check=True)
    live = []
    for row in listing.stdout.splitlines():
        pid, group, state = row.split()
        if int(group) == pgid and not state.startswith("Z"):
            live.append(f"{pid} {state}")
    return live


def kill_process_group(pgid: int) -> None:
    """SIGKILL a whole process group; only a group with no live member left is tolerated.

    macOS refuses (EPERM) to signal a group whose remaining members are all zombies awaiting their
    reaper, for example killed grandchildren not yet reaped by launchd. EPERM is accepted only after
    ``ps`` proves no non-zombie member is left; a live member that refuses SIGKILL fails loudly.
    """
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # no member is left
    except PermissionError as error:
        live = live_group_members(pgid)
        if live:
            raise WorkerError(f"cannot SIGKILL process group {pgid}; live members remain: {', '.join(live)}") from error


def run_in_session(command: list[str], *, capture_output: bool = False, check: bool = False,
                   timeout: float | None = None, on_start: Callable[[], None] | None = None,
                   **popen: Any) -> subprocess.CompletedProcess:
    """``subprocess.run`` in a new session whose whole process group is killed when the leader exits.

    A writer cannot leave a same-group background process running past its own exit (to tamper with
    harness clones later), nor hold the output pipes open: once the leader has exited the group is
    killed and the remaining output drained. On timeout or any error the group is killed too. A child
    that starts its own session escapes the group; only an OS sandbox contains that.
    """
    if capture_output:
        popen.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process = subprocess.Popen(command, start_new_session=True, **popen)
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        if on_start is not None:
            on_start()  # the process exists: a caller may now record an observed launch
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if process.poll() is not None:
                    kill_process_group(process.pid)  # the leader exited; a group member still holds a pipe
                elif deadline is not None and time.monotonic() >= deadline:
                    kill_process_group(process.pid)
                    process.communicate()
                    raise subprocess.TimeoutExpired(command, timeout) from None
    finally:
        kill_process_group(process.pid)
        if process.poll() is None:
            process.wait()
    if check and process.returncode:
        raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def writer_tmp(root: Path) -> Path:
    """A fresh writer temporary directory beside, never above, the harness clones of ``root``."""
    tmp = root / "llm-tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    return tmp


def run_llm(command: list[str], checkout: Path, *, tmp: Path, env: dict[str, str] | None = None,
            runner: Callable[..., Any] = run_in_session, timeout: int | None = None,
            home: Path | None = None, runtime_tmp: Path | None = None,
            extra_env: dict[str, str] | None = None) -> Any:
    """Run the LLM command in a checkout with no credential, a scratch home, a dedicated ``TMPDIR`` and no stdin.

    The inherited ``TMPDIR`` would make the harness work directory writable to a sandboxed writer, so the
    writer gets ``tmp`` (from ``writer_tmp``) instead. The runner must contain the writer's process group.
    ``runtime_tmp`` (sandboxed launch only) gives the outer process a different, short ``TMPDIR`` while
    the writer receives ``tmp`` through the inner command; ``extra_env`` is added after the credential-free
    filter and is reserved for the scoped writer credential.
    """
    if runner is subprocess.run:
        raise WorkerError("the writer runner must kill its process group; use run_in_session")
    clean = credential_free_env(dict(os.environ if env is None else env), home)
    outer = tmp if runtime_tmp is None else runtime_tmp
    clean.update(TMPDIR=str(outer), TMP=str(outer), TEMP=str(outer))
    if extra_env:
        clean.update(extra_env)
    return runner(command, cwd=checkout, env=clean, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                  check=False, timeout=timeout)


def prepare_checkout(source: str, root: str, name: str, head: str, *, contract_from: Path | None = None) -> Path:
    """Disposable checkout detached at the exact head (local sources reuse the sandbox helper).

    ``contract_from`` names the trusted installed contract to give a checkout that commits
    none, instead of the head's own public contract (a historical head may predate it).
    """
    if Path(source).is_absolute() and Path(source).is_dir():
        create = disposable_repository_sandbox.create
        path = create(source, root, name)
        with (path / ".git" / "info" / "exclude").open("a", encoding="utf-8") as handle:
            handle.write("\n.dev-platform-disposable-repository.json\n")  # sandbox marker is not candidate content
        steps = [["checkout", "--detach", head]]
    else:
        path = Path(root) / name
        steps = [["clone", "--no-local", "--no-checkout", source, str(path)]]
        if re.fullmatch(r"[0-9a-f]{40}", head):
            # A merged PR's branch may be deleted while its head commit stays reachable only
            # through the pull ref, which a clone does not fetch: fetch that exact commit.
            steps.append(["fetch", "--quiet", "origin", head])
        steps.append(["checkout", "--detach", head])
    for step in steps:
        done = subprocess.run(["git", *SAFE_GIT, *step], cwd=path if path.exists() else root, text=True,
                              capture_output=True, check=False, stdin=subprocess.DEVNULL)
        if done.returncode:
            raise WorkerError(f"git {step[0]} failed for {head}: {done.stderr.strip()}")
    install_source_contract(path, contract_from)
    return path


def install_source_contract(checkout: Path, contract_from: Path | None = None) -> None:
    """Give a clean checkout the committed contract, the way a fresh writer checkout needs it.

    A project commits `.dev-platform.toml`. The source repository does not (its installed
    contract carries operator-only sections) and commits its public part as
    `dev-platform/source-contract.toml` instead. A checkout with neither has no contract.
    With ``contract_from``, a checkout that commits no contract gets exactly that file.
    """
    if contract_from is not None and not contract_from.is_file():
        raise WorkerError(f"trusted platform contract {contract_from} is missing; cannot install it into {checkout}")
    contract = checkout / ".dev-platform.toml"
    if contract.exists():
        return
    if contract_from is not None:
        public = contract_from
    else:
        public = checkout / SOURCE_CONTRACT
        if not public.is_file():
            raise WorkerError(f"checkout {checkout} has neither .dev-platform.toml nor {SOURCE_CONTRACT}; no platform contract")
    shutil.copyfile(public, contract)
    # Installed, never candidate content: the source repository excludes it only locally.
    with (checkout / ".git" / "info" / "exclude").open("a", encoding="utf-8") as handle:
        handle.write("\n.dev-platform.toml\n")


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *SAFE_GIT, *args], cwd=repo, text=True, capture_output=True,
                          check=False, stdin=subprocess.DEVNULL)
    if done.returncode:
        raise WorkerError(f"git {' '.join(args)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def _forbidden(path: str) -> str | None:
    if path.startswith(".github/workflows/"):
        return "workflow edit"
    parts = path.split("/")
    if parts[:2] == ["openspec", "changes"]:
        name = parts[-1]
        if (name in EVIDENCE_NAMES or name.startswith("independent-review")
                or any(part in {"independent-reviews", "evidence"} for part in parts[3:])):
            return "lifecycle evidence edit"
    return None


def _refusal(reason: str, paths: list[str]) -> WorkerError:
    """One bounded refusal: the first offending path plus how many more there are."""
    more = f" (+{len(paths) - 1} more)" if len(paths) > 1 else ""
    return WorkerError(f"{reason}: {paths[0]}{more}")


def validate_writer_result(repo: Path, expected_head: str, result_head: str) -> list[str]:
    """Return the changed paths of an acceptable result or raise WorkerError."""
    for value in (expected_head, result_head):
        if not HEAD.fullmatch(value):
            raise WorkerError("invalid head")
    if result_head == expected_head:
        raise WorkerError("result has no new commits")
    done = subprocess.run(["git", *SAFE_GIT, "merge-base", "--is-ancestor", expected_head, result_head], cwd=repo,
                          capture_output=True, check=False, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise WorkerError("result is not a fast-forward from the expected head")
    fields = _git(repo, "diff", "--raw", "--no-renames", "-z", expected_head, result_head).split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    if len(fields) % 2:
        raise WorkerError("cannot parse the result diff")
    changed, gitlinks = [], []
    for meta, path in zip(fields[0::2], fields[1::2]):
        old_mode, new_mode = meta.lstrip(":").split(" ")[:2]
        if "160000" in (old_mode, new_mode):
            gitlinks.append(path)  # a submodule pointer is never a writer result
        changed.append(path)
    if gitlinks:
        raise _refusal("gitlink not allowed", gitlinks)
    refused = [path for path in changed if _forbidden(path)]
    if refused:
        raise _refusal(_forbidden(refused[0]), refused)
    return changed


def harness_git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    """Harness git for a harness-owned repository, with no credential and no operator git config.

    Every git command that runs after a writer or reviewer touched a checkout uses this (and only
    on a harness-owned clone), so configuration planted in the writer's checkout is never consulted.
    Ambient author/committer variables are dropped so a harness commit carries ``HARNESS_IDENTITY`` only.
    """
    env = {key: value for key, value in credential_free_env(dict(os.environ), repo.parent / "harness-home").items()
           if key not in {"GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
                          "CLAUDE_CODE_OAUTH_TOKEN"}}
    done = subprocess.run(["git", *SAFE_GIT, *args], cwd=repo, text=not binary, capture_output=True, check=False,
                          stdin=subprocess.DEVNULL, env=env)
    if done.returncode:
        detail = done.stderr.strip() or done.stdout.strip()
        if binary:
            detail = repr(detail)
        raise WorkerError(f"git {' '.join(args)} failed: {detail}")
    return done.stdout


def _walk_error(error: OSError) -> None:
    raise WorkerError(f"cannot read the working tree: {error}")


def tree_snapshot(path: Path) -> str:
    """A content digest of a working tree read from the filesystem only (no git, no filters), excluding the root ``.git``.

    Symlinks are hashed by their target text whatever they point to (never followed); a FIFO, socket or
    device is refused without being opened, so writer content can neither block nor hide from the digest.
    """
    import hashlib

    digest = hashlib.sha256()
    for directory, names, files in os.walk(path, onerror=_walk_error):
        here = Path(directory)
        links = [name for name in names if (here / name).is_symlink()]
        names[:] = sorted(name for name in names if name not in links and not (here == path and name == ".git"))
        for name in sorted(files + links):
            target = here / name
            relative = str(target.relative_to(path))
            mode = target.lstat().st_mode
            digest.update(relative.encode() + b"\0")
            if stat.S_ISLNK(mode):
                digest.update(b"L" + os.readlink(target).encode())
            elif stat.S_ISREG(mode):
                digest.update(b"F" + str(mode & 0o111).encode() + target.read_bytes())
            else:
                raise WorkerError(f"unsupported file type: {relative}")
    return digest.hexdigest()


def _harness_dir(target: Path, relative: Path) -> Path:
    """Create ``target/relative`` as real directories, replacing any symlink or file on the way."""
    current = target
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            current.unlink()
        if not current.exists():
            current.mkdir()
    return current


def _clear(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def check_import_source(source: Path, target: Path) -> None:
    """Refuse a writer tree the harness cannot import faithfully and safely, before anything is copied.

    Only the root ``.git`` directory may exist: a ``.git`` entry of any type anywhere else (gitfile, nested
    repository, symlink) would make harness git recurse into writer-controlled metadata and run its filters.
    Only regular files, directories and symlinks are importable. A name differing only in case from an
    existing harness entry that the writer tree no longer has (``src`` -> ``SRC``) would, on a case-insensitive
    filesystem, delete the existing entry, so it is refused too.
    """
    for directory, names, files in os.walk(source, onerror=_walk_error):
        here = Path(directory)
        base = here.relative_to(source)
        entries = names + files
        if not base.parts and ".git" in entries and (".git" not in names or (here / ".git").is_symlink()):
            raise WorkerError("git metadata replaced: .git")
        names[:] = sorted(name for name in names if base.parts or name != ".git")
        entries = [name for name in entries if base.parts or name != ".git"]
        existing_dir = target / base
        existing = (os.listdir(existing_dir) if existing_dir.is_dir() and not existing_dir.is_symlink() else [])
        for name in sorted(entries):
            relative = (base / name).as_posix()
            if name.lower() == ".git":
                raise WorkerError(f"nested git metadata: {relative}")
            mode = (here / name).lstat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode) or stat.S_ISLNK(mode)):
                raise WorkerError(f"unsupported file type: {relative}")
            if any(other != name and other.lower() == name.lower() and other not in entries for other in existing):
                raise WorkerError(f"case-only path collision: {relative}")


def import_worktree(source: Path, target: Path) -> None:
    """Make ``target``'s working tree match ``source``'s files without running git in ``source``.

    Only file content, executable bits and symlinks are copied; ``.git`` of either side is never read
    or written, so a writer's repository configuration, attributes drivers or hooks cannot execute.
    Symlinks (to files or directories) are recreated as links and never followed on either side, so
    writer content cannot be redirected outside the harness clone. ``check_import_source`` refuses
    nested git metadata, special files and case-only collisions first (``WorkerError``).
    """
    check_import_source(source, target)
    wanted: set[Path] = set()
    for directory, names, files in os.walk(source):
        base = Path(directory).relative_to(source)
        parent = _harness_dir(target, base)
        links = [name for name in names if (Path(directory) / name).is_symlink()]
        names[:] = sorted(name for name in names if name != ".git" and name not in links)
        for name in sorted(files + links):
            if not base.parts and name == ".git":
                continue
            relative, origin, copy = base / name, Path(directory) / name, parent / name
            wanted.add(relative)
            _clear(copy)
            if origin.is_symlink():
                os.symlink(os.readlink(origin), copy)
            elif origin.is_file():
                shutil.copyfile(origin, copy)
                copy.chmod(0o755 if origin.stat().st_mode & 0o111 else 0o644)
        for name in names:
            wanted.add(base / name)
    for directory, names, files in os.walk(target, topdown=False):
        here = Path(directory).relative_to(target)
        if here.parts and here.parts[0] == ".git":
            continue
        for name in files + [name for name in names if (Path(directory) / name).is_symlink()]:
            relative = here / name
            if relative not in wanted and relative.parts[0] != ".git":
                (Path(directory) / name).unlink()


def prepare_harness(source_repo: str, checkout: Path, root: Path, result_head: str, name: str = "harness") -> Path:
    """Import only result commits into a separate trusted clone for validation/push."""
    harness = root / name
    for step in (["clone", "--no-local", "--no-checkout", source_repo, str(harness)],
                 ["fetch", "--no-tags", str(checkout), result_head]):
        cwd = harness if step[0] == "fetch" else root
        proc = subprocess.run(["git", *SAFE_GIT, "-c", "protocol.file.allow=always", *step],
                              cwd=cwd, text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL)
        if proc.returncode:
            raise WorkerError(proc.stderr.strip()[:200])
    return harness


def worktree_changes(repo: Path) -> list[str]:
    """Every tracked modification, deletion and untracked (not ignored) path of a harness-owned clone."""
    out = harness_git(repo, "-c", "diff.ignoreSubmodules=all", "status", "--porcelain=v1", "-z",
                      "--untracked-files=all", "--no-renames", "--ignore-submodules=all")
    return sorted(entry[3:] for entry in out.split("\0") if entry)
