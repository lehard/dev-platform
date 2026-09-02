#!/usr/bin/env python3
"""Containment observation and legacy fallback for write-capable delegation.

See openspec/specs/platform-delegation/spec.md and the active
wire-runtime-delegation-containment change for the contract. A delegation is
platform-contained when it has a valid assigned worktree, a proven native or
fallback boundary, and the post-delegation comparison below. Native runtime
containment is the preferred prevention layer; this module observes it and
retains the smallest compatibility fallback. ``run_guarded_delegation`` is a
backwards-compatible name, while new native callers should use
``run_observed_delegation`` to avoid implying that a second custom guard is
what protects the filesystem.

Guarded flow, always in this order:

    validate assigned_worktree -> determine enforcement tier -> pre-snapshot ->
    launch child with cwd=assigned_worktree -> post-snapshot (always) ->
    classify -> record friction on violation -> return/raise

Enforcement tiers are honest, not aspirational:

- HARD means a proven pre-write boundary exists before the child can mutate
  protected repository paths outside `assigned_worktree`: for Codex, a real
  OS writable-root sandbox (Landlock/Seatbelt, exposed via
  `codex --sandbox workspace-write`) whose known additional temporary writable
  roots do not overlap the integration or assigned-worktree topology;
  for Claude, a platform-installed PreToolUse hook denying Write/Edit/
  NotebookEdit targets outside `assigned_worktree`, valid only when no
  shell-capable tool is also enabled for the same delegated session.
- DETECTION_ONLY means the only enforcement is this module's own post-hoc
  comparison. Detection-only delegation refuses to start while the
  integration checkout already has uncommitted state, since it cannot tell
  apart pre-existing dirt from writer-caused damage the way a hard-contained
  run's post-check still can.

This module never stashes/resets/cleans/deletes anything in the integration
copy. It does not vendor OpenSpec-generated Claude/Codex skills, and any
runtime settings it writes for a guarded Claude child are ephemeral temp-
directory files, never a project-tracked path.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import platform
import select
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

try:  # Codex's proven workspace-write boundary is currently POSIX-only.
    import fcntl
except ImportError:  # pragma: no cover - exercised only on unsupported Windows hosts.
    fcntl = None  # type: ignore[assignment]

from delegation_containment import (
    ContainmentError,
    ContainmentResult,
    check_containment,
    format_violation_message,
    record_containment_friction,
    resolve_assigned_worktree,
    snapshot,
)


class EnforcementTier(str, Enum):
    HARD = "hard"
    DETECTION_ONLY = "detection-only"


@dataclass(frozen=True)
class EnforcementDecision:
    tier: EnforcementTier
    mechanism: str
    detail: str


# Bounded classification of why a launched delegation ended abnormally. Kept as
# a small closed vocabulary so a route receipt can distinguish an external
# launcher interruption from a steady-state timeout or any other launcher-side
# failure without carrying an unbounded exception blob.
ABNORMAL_EXTERNAL_INTERRUPT = "external-interrupt"
ABNORMAL_TIMEOUT = "timeout"
ABNORMAL_OTHER = "other"


@dataclass(frozen=True)
class RetainedWork:
    """Bounded state of the assigned worktree's own uncommitted work.

    This never carries a diff or file contents: only whether partial work is
    present and how many paths it touches, so an abnormal receipt can say that
    an interrupted executor left recoverable work without leaking its content.
    ``state`` is ``present``, ``absent`` or ``unknown`` (worktree status could
    not be read); ``changed_path_count`` is ``-1`` when unknown.
    """

    state: str
    changed_path_count: int

    def as_dict(self) -> dict[str, object]:
        return {"state": self.state, "changed_path_count": self.changed_path_count}


@dataclass(frozen=True)
class GuardedRunResult:
    launched: bool
    returncode: int | None
    tier: EnforcementTier
    mechanism: str
    containment: ContainmentResult
    violation: bool
    message: str | None
    writer_state: str = "released"
    abnormal_kind: str | None = None
    retained_work: RetainedWork | None = None


class GuardedChildError(ContainmentError):
    """The delegated child did not complete normally (exec failure, timeout, cancellation).

    The post-delegation containment check still ran before this was raised; `result`
    carries its outcome so callers do not lose containment information just because
    the child itself failed.
    """

    def __init__(self, message: str, result: GuardedRunResult) -> None:
        super().__init__(message)
        self.result = result


class WriterOwnershipError(ContainmentError):
    """A local worktree already has a live or ambiguous delegated writer."""


class LauncherInterrupted(BaseException):
    """An external termination/interruption signal reached the launcher while a
    delegated writer was live.

    Raised from a scoped signal handler so the interpreter does not exit
    immediately on the default disposition; instead the signal is funnelled
    through the same bounded process-group terminate-and-reap path used for
    timeouts and cancellation, which is the only place writer ownership is
    released or marked ambiguous. Subclasses ``BaseException`` (like
    ``KeyboardInterrupt``) so an unrelated ``except Exception`` cannot swallow
    it before cleanup runs.
    """

    def __init__(self, signum: int) -> None:
        try:
            name = signal.Signals(signum).name
        except ValueError:  # pragma: no cover - non-standard signal number
            name = f"signal {signum}"
        self.signum = signum
        self.signal_name = name
        super().__init__(f"launcher received {name} while a delegated writer was live")


# External interruptions the launcher converts into controlled cleanup while a
# delegated writer is live. SIGINT is included so an interactive Ctrl-C is
# classified the same way as an orchestrator-sent termination rather than
# taking the default KeyboardInterrupt path with a different receipt shape.
_LAUNCHER_INTERRUPT_SIGNALS: tuple[int, ...] = tuple(
    getattr(signal, _name)
    for _name in ("SIGTERM", "SIGHUP", "SIGINT", "SIGQUIT")
    if hasattr(signal, _name)
)


class _ScopedInterruptHandlers:
    """Install fail-safe signal handling only while a delegated writer is live.

    Outside the armed window the launcher keeps its inherited signal
    disposition. ``disarm`` restores the previous handlers and is safe to call
    more than once. Signal handlers can only be installed from the main thread
    of the main interpreter; when armed from any other thread this is a no-op
    and the pre-existing ``except BaseException`` cleanup path remains the only
    safety net (unchanged behavior for embedded/test callers).
    """

    def __init__(self, signals: tuple[int, ...] = _LAUNCHER_INTERRUPT_SIGNALS) -> None:
        self._signals = signals
        self._previous: dict[int, object] = {}

    def arm(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return

        def _handler(received: int, _frame: object) -> None:
            raise LauncherInterrupted(received)

        for signum in self._signals:
            try:
                self._previous[signum] = signal.signal(signum, _handler)
            except (ValueError, OSError):  # pragma: no cover - signal slot unavailable on this host
                self._previous.pop(signum, None)

    def disarm(self) -> None:
        while self._previous:
            signum, handler = self._previous.popitem()
            if handler is None:
                # The prior handler was not installed from Python and cannot be
                # reinstated; leave the interpreter default in place rather than
                # raising during cleanup.
                continue
            try:
                signal.signal(signum, handler)  # type: ignore[arg-type]
            except (ValueError, OSError, TypeError):  # pragma: no cover - restoration best effort
                pass


_WRITER_LOCK_NAME = "delegated-writer.lock"
_WRITER_STATE_NAME = "delegated-writer.json"
_CLEANUP_GRACE_SECONDS = 2.0


def _writer_paths(assigned_worktree: Path) -> tuple[Path, Path]:
    """Keep lifecycle metadata in this worktree's Git admin area, not its tree.

    A lock/receipt is runtime state.  Leaving it below ``.claude`` would make
    every successful delegated run create an untracked task change and could
    itself interfere with a task's clean-state checks.
    """
    dot_git = assigned_worktree / ".git"
    if dot_git.is_dir():
        git_dir = dot_git.resolve()
    else:
        try:
            marker = dot_git.read_text(encoding="utf-8").strip()
            prefix, location = marker.split(":", 1)
            if prefix != "gitdir" or not location.strip():
                raise ValueError("missing gitdir marker")
            candidate = Path(location.strip())
            git_dir = (dot_git.parent / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        except (OSError, ValueError) as exc:
            raise WriterOwnershipError(
                f"cannot locate Git admin directory for assigned worktree {assigned_worktree}; refusing writer launch"
            ) from exc
    directory = git_dir / "dev-platform"
    return directory / _WRITER_LOCK_NAME, directory / _WRITER_STATE_NAME


def _write_writer_state(path: Path, payload: dict[str, object]) -> None:
    """Replace the small ownership receipt while its advisory lock is held."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _process_group_state(pgid: int) -> str:
    """Return absent, live, or ambiguous without ever guessing from a PID reuse."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return "absent"
    except PermissionError:
        return "ambiguous"
    except OSError as exc:
        return "absent" if exc.errno == errno.ESRCH else "ambiguous"
    return "live"


@dataclass
class _WriterOwnership:
    """A per-worktree, process-lifetime lock plus a crash-visible receipt.

    ``flock`` serializes local launchers while they are alive.  The receipt is
    deliberately retained if a launcher dies between spawning and reaping its
    child: a later launcher must fail closed rather than treating a vanished
    parent as proof that the writer also vanished.
    """

    assigned_worktree: Path
    lock_path: Path
    state_path: Path
    handle: object
    launch_id: str
    released: bool = False

    @classmethod
    def acquire(cls, assigned_worktree: Path) -> "_WriterOwnership":
        if fcntl is None:
            raise WriterOwnershipError(
                "local single-writer ownership requires a POSIX advisory lock; refusing write-capable delegation"
            )
        lock_path, state_path = _writer_paths(assigned_worktree)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise WriterOwnershipError(
                f"delegated writer for assigned worktree {assigned_worktree} is already active; "
                "refusing a second write-capable launch"
            ) from exc

        try:
            if state_path.exists():
                try:
                    prior = json.loads(state_path.read_text(encoding="utf-8"))
                    prior_pgid = prior["process_group"]
                except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise WriterOwnershipError(
                        f"delegated writer ownership for {assigned_worktree} is ambiguous; inspect "
                        f"{state_path} before another launch"
                    ) from exc
                if not isinstance(prior_pgid, int) or prior_pgid <= 0:
                    raise WriterOwnershipError(
                        f"delegated writer ownership for {assigned_worktree} is ambiguous; inspect "
                        f"{state_path} before another launch"
                    )
                prior_state = _process_group_state(prior_pgid)
                if prior_state != "absent":
                    adjective = "still active" if prior_state == "live" else "ambiguous"
                    raise WriterOwnershipError(
                        f"previous delegated writer for {assigned_worktree} is {adjective} "
                        f"(process group {prior_pgid}); refusing a second write-capable launch"
                    )
                state_path.unlink()

            ownership = cls(assigned_worktree, lock_path, state_path, handle, uuid.uuid4().hex)
            # A crash in the small interval before a spawned child's pid is
            # recorded remains intentionally ambiguous rather than unsafe.
            ownership._write({"state": "launching", "launch_id": ownership.launch_id})
            return ownership
        except Exception:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
            raise

    def _write(self, values: dict[str, object]) -> None:
        _write_writer_state(
            self.state_path,
            {
                "version": 1,
                "assigned_worktree": str(self.assigned_worktree),
                "launcher_pid": os.getpid(),
                "launch_id": self.launch_id,
                **values,
            },
        )

    def mark_running(self, process: subprocess.Popen[str]) -> int:
        # New sessions make the known child pid the process-group id, so an
        # abnormal path can terminate its relevant descendants as one unit.
        pgid = process.pid
        self._write({"state": "running", "child_pid": process.pid, "process_group": pgid})
        return pgid

    def mark_ambiguous(self, pgid: int | None, reason: str) -> None:
        values: dict[str, object] = {"state": "ambiguous", "reason": reason}
        if pgid is not None:
            values["process_group"] = pgid
        self._write(values)
        self._unlock()

    def release(self) -> None:
        try:
            self.state_path.unlink()
        except FileNotFoundError:
            pass
        self._unlock()

    def _unlock(self) -> None:
        if not self.released:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.released = True


def _classify_abnormal(exc: BaseException) -> str:
    """Map an abnormal launcher return to the bounded receipt vocabulary."""
    if isinstance(exc, LauncherInterrupted):
        return ABNORMAL_EXTERNAL_INTERRUPT
    if isinstance(exc, subprocess.TimeoutExpired):
        return ABNORMAL_TIMEOUT
    return ABNORMAL_OTHER


def _assigned_worktree_retained_work(assigned_worktree: Path) -> RetainedWork:
    """Summarize, without content, the partial work an interrupted writer left.

    Read-only. A failed or unreadable ``git status`` is reported as ``unknown``
    rather than silently treated as "no retained work", so a receipt never
    understates what a later recovery step must consider.
    """
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=assigned_worktree,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return RetainedWork("unknown", -1)
    if completed.returncode != 0:
        return RetainedWork("unknown", -1)
    changed = [line for line in completed.stdout.splitlines() if line.strip()]
    return RetainedWork("present" if changed else "absent", len(changed))


def _terminate_and_reap(process: subprocess.Popen[str], pgid: int) -> bool:
    """Boundedly terminate the launched process tree and prove its group is gone."""
    if _process_group_state(pgid) == "absent":
        try:
            process.wait(timeout=0)
        except subprocess.TimeoutExpired:
            pass
        return True

    for sig, grace in ((signal.SIGTERM, _CLEANUP_GRACE_SECONDS), (signal.SIGKILL, _CLEANUP_GRACE_SECONDS)):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            return False
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            # Reap our direct child as soon as it exits.  Otherwise its zombie
            # can keep the process group observable and turn successful
            # cleanup into a needless ambiguous ownership record.
            try:
                process.wait(timeout=0)
            except subprocess.TimeoutExpired:
                pass
            if _process_group_state(pgid) == "absent":
                return True
            time.sleep(0.05)
    return _process_group_state(pgid) == "absent"


def _stream_output(
    process: subprocess.Popen[str], stdout_line_hook: Callable[[str], None], timeout: float | None
) -> int:
    """Forward complete output lines while enforcing the launch deadline.

    Codex's structured event stream is newline-delimited.  Polling its pipe
    keeps a silent/stalled stream from bypassing the timeout while preserving
    the single observed child path used for provenance extraction.
    """
    assert process.stdout is not None
    deadline = time.monotonic() + timeout if timeout is not None else None
    while True:
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout)
            wait_for = min(remaining, 0.1)
        else:
            wait_for = 0.1
        readable, _, _ = select.select([process.stdout], [], [], wait_for)
        if readable:
            line = process.stdout.readline()
            if line:
                stdout_line_hook(line.rstrip("\n"))
                continue
            # EOF proves every writer of the merged pipe has closed it, but
            # the direct child can still need one scheduler turn to become
            # waitable.  The configured deadline has already been enforced
            # while reading; waiting here avoids turning that benign reaping
            # race into a false abnormal return.
            return process.wait()
        if process.poll() is not None:
            return process.wait(timeout=0)


class _ReadinessError(RuntimeError):
    """The launched child never reached its declared ready state in time."""


def _await_readiness(
    process: subprocess.Popen[str],
    ready_probe: Callable[[], bool] | None,
    ready_deadline: float | None,
) -> None:
    """Block until the child signals readiness, bounded by its own deadline.

    A steady-state ``timeout`` measures how long a *running, ready* child may
    take.  Some children (and every deterministic test of the cleanup path)
    need a distinct, bounded window to publish the state a later assertion
    depends on -- a spawned descendant, a pid file, an open port.  Measuring
    the steady-state deadline from launch instead conflates process-start
    scheduling delay with a real stall.  When ``ready_probe`` is supplied the
    steady-state clock only starts after it returns true.

    The probe is expected to become true quickly and before the child emits
    more than a pipe buffer of output; that holds for the pid/descendant
    handshakes this is used for.
    """
    if ready_probe is None:
        return
    deadline = time.monotonic() + (ready_deadline if ready_deadline is not None else _CLEANUP_GRACE_SECONDS)
    while True:
        if ready_probe():
            return
        if process.poll() is not None:
            raise _ReadinessError(
                f"delegated child exited (returncode {process.returncode}) before signalling readiness"
            )
        if time.monotonic() >= deadline:
            raise _ReadinessError(
                f"delegated child (pid {process.pid}) did not signal readiness within "
                f"{deadline if ready_deadline is None else ready_deadline:g}s"
            )
        time.sleep(0.02)


# --------------------------------------------------------------------------
# Core guarded entrypoint -- runtime-agnostic.
# --------------------------------------------------------------------------


def run_observed_delegation(
    *,
    integration_root: Path,
    assigned_worktree: str | Path,
    argv: list[str],
    tier_decision: EnforcementDecision,
    env: dict[str, str] | None = None,
    task: str | None = None,
    timeout: float | None = None,
    stdout_line_hook: Callable[[str], None] | None = None,
    ready_probe: Callable[[], bool] | None = None,
    ready_deadline: float | None = None,
    route_containment_friction: bool = True,
) -> GuardedRunResult:
    """Run one delegated child under a native/fallback containment contract.

    Always validates assigned_worktree first (fail closed before any launch), always
    snapshots before launch, always launches with cwd=assigned_worktree, and always
    snapshots again -- even if the child raises, times out, or is cancelled -- before
    returning or raising. Never mutates integration_root itself.

    ``stdout_line_hook``, when given, receives each stdout/stderr line as the
    child produces it (merged, so live output ordering is preserved) instead
    of letting the child inherit the parent's stdout directly. Callers use
    this to both forward output for live visibility and opportunistically
    parse structured runtime events (for example Codex's ``--json`` event
    stream) without adding a second execution path.

    ``ready_probe``, when given, is polled after launch until it returns true;
    the steady-state ``timeout`` is only measured from that point, and a child
    that never becomes ready within ``ready_deadline`` (default: the cleanup
    grace window) is reaped and reported as an abnormal return. This keeps a
    slow process start from being misread as a stall and lets cleanup-path
    tests synchronize on the descendant state they assert about.

    ``route_containment_friction`` defaults to True and must stay that way for
    every production caller, so a real containment violation still routes through
    agent_friction.py's normal GitHub gate. Pass False only from hermetic test
    fixtures that intentionally provoke a synthetic violation.
    """
    resolved_worktree = resolve_assigned_worktree(integration_root, assigned_worktree)

    if tier_decision.tier is EnforcementTier.DETECTION_ONLY:
        dirty_precheck = snapshot(integration_root)
        if dirty_precheck.paths:
            dirty_paths = ", ".join(sorted(dirty_precheck.paths))
            raise ContainmentError(
                f"detection-only delegation ({tier_decision.mechanism}) refused to start: "
                f"integration checkout already has uncommitted state ({dirty_paths}). "
                "A detection-only writer cannot prove it did not touch pre-existing dirty "
                "state, so it must not launch until integration is clean."
            )
        before = dirty_precheck
    else:
        before = snapshot(integration_root)

    ownership = _WriterOwnership.acquire(resolved_worktree)
    child_launched = False
    launch_exception: BaseException | None = None
    completed: subprocess.CompletedProcess[str] | None = None
    process: subprocess.Popen[str] | None = None
    process_group: int | None = None
    writer_state = "released"
    # Fail-safe signal handling is armed only once a write-capable child is
    # live and disarmed before this function returns, so an external
    # termination of the launcher is funnelled through the same bounded
    # terminate-and-reap path as a timeout instead of orphaning the writer.
    interrupt_handlers = _ScopedInterruptHandlers()
    try:
        if stdout_line_hook is not None:
            process = subprocess.Popen(
                argv, cwd=resolved_worktree, env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, start_new_session=True,
            )
            child_launched = True
            process_group = ownership.mark_running(process)
            interrupt_handlers.arm()
            _await_readiness(process, ready_probe, ready_deadline)
            returncode = _stream_output(process, stdout_line_hook, timeout)
            process.stdout.close()
            completed = subprocess.CompletedProcess(argv, returncode)
        else:
            process = subprocess.Popen(argv, cwd=resolved_worktree, env=env, text=True, start_new_session=True)
            child_launched = True
            process_group = ownership.mark_running(process)
            interrupt_handlers.arm()
            _await_readiness(process, ready_probe, ready_deadline)
            returncode = process.wait(timeout=timeout)
            completed = subprocess.CompletedProcess(argv, returncode)
        # A completed leader alone is not enough: a descendant holding its
        # session/process group remains a write-capable orphan.  Treat that as
        # abnormal and resolve it before this worktree is reusable.
        if process_group is not None and _process_group_state(process_group) != "absent":
            launch_exception = RuntimeError(
                f"delegated child exited but writer process group {process_group} is still live"
            )
            if _terminate_and_reap(process, process_group):
                ownership.release()
            else:
                writer_state = "ambiguous"
                ownership.mark_ambiguous(process_group, "process group survived normal child return")
        else:
            ownership.release()
    except BaseException as exc:
        # Timeout, cancellation, a streaming failure, or another abnormal
        # parent return after Popen must resolve the whole launched tree, not
        # merely the immediate child.  If resolution cannot be proven, keep a
        # durable ambiguous receipt so later launchers fail closed.
        launch_exception = exc
        if child_launched and process is not None and process_group is not None:
            if _terminate_and_reap(process, process_group):
                ownership.release()
            else:
                writer_state = "ambiguous"
                ownership.mark_ambiguous(process_group, f"abnormal return: {exc!r}")
        else:
            ownership.release()
    finally:
        interrupt_handlers.disarm()
        if process is not None and process.stdout is not None:
            process.stdout.close()
        after = snapshot(integration_root)
        containment = check_containment(before, after)

    violation = containment.violated
    message = format_violation_message(resolved_worktree, containment) if violation else None
    if violation:
        record_containment_friction(
            integration_root, resolved_worktree, containment, task=task, enforcement_tier=tier_decision.tier.value,
            route=route_containment_friction,
        )

    abnormal_kind = _classify_abnormal(launch_exception) if launch_exception is not None else None
    # A bounded retained-work summary is only meaningful once a child actually
    # ran and then ended abnormally; a clean completion or an unlaunched exec
    # failure has no interrupted partial diff to hand off.
    retained_work = (
        _assigned_worktree_retained_work(resolved_worktree)
        if launch_exception is not None and child_launched
        else None
    )

    result = GuardedRunResult(
        launched=child_launched,
        returncode=completed.returncode if completed is not None else None,
        tier=tier_decision.tier,
        mechanism=tier_decision.mechanism,
        containment=containment,
        violation=violation,
        message=message,
        writer_state=writer_state,
        abnormal_kind=abnormal_kind,
        retained_work=retained_work,
    )

    if launch_exception is not None:
        retained_note = (
            f", retained work {retained_work.state}" if retained_work is not None else ""
        )
        raise GuardedChildError(
            f"delegated child did not complete normally ({launch_exception!r}); "
            f"abnormal kind {abnormal_kind}, containment {'VIOLATION' if violation else 'clean'} and "
            f"writer lifecycle {writer_state}{retained_note} recorded before this error was raised.",
            result,
        ) from launch_exception

    return result


def run_guarded_delegation(
    *,
    integration_root: Path,
    assigned_worktree: str | Path,
    argv: list[str],
    tier_decision: EnforcementDecision,
    env: dict[str, str] | None = None,
    task: str | None = None,
    timeout: float | None = None,
    ready_probe: Callable[[], bool] | None = None,
    ready_deadline: float | None = None,
    route_containment_friction: bool = True,
) -> GuardedRunResult:
    """Compatibility alias for callers that still use the former guard name."""
    return run_observed_delegation(
        integration_root=integration_root,
        assigned_worktree=assigned_worktree,
        argv=argv,
        tier_decision=tier_decision,
        env=env,
        task=task,
        timeout=timeout,
        ready_probe=ready_probe,
        ready_deadline=ready_deadline,
        route_containment_friction=route_containment_friction,
    )


# --------------------------------------------------------------------------
# Codex adapter: real OS writable-root sandbox when the installed runtime supports it.
# --------------------------------------------------------------------------

CODEX_SANDBOX_FLAG = "--sandbox"
CODEX_SANDBOX_MODE = "workspace-write"
CODEX_CD_FLAG = "--cd"
_HARD_SANDBOX_OS = ("Darwin", "Linux")


def _codex_help_text(binary: str) -> str:
    try:
        # A real `codex exec --help` answers in milliseconds; this timeout only
        # guards against a genuinely hung process. It must stay generous enough
        # to survive legitimate CPU contention from concurrent mandatory test
        # groups (see dev-platform/checks.toml [test_groups]) -- a tighter bound
        # previously caused this to time out under contention and downgrade to
        # "sandbox-flag-unsupported" instead of reporting the real mechanism.
        completed = subprocess.run(
            [binary, "exec", "--help"], text=True, capture_output=True, check=False, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout + completed.stderr


def _normalized_path(path: str | Path) -> Path:
    """Normalize filesystem paths with the same realpath semantics as the guard."""
    return Path(path).expanduser().resolve()


def _codex_runtime_temp_roots() -> tuple[Path, ...]:
    """Return only the extra Codex workspace-write roots established by evidence.

    Codex workspace-write can also allow system temporary roots. `/tmp` is the
    observed portable root and `$TMPDIR` is included explicitly because Python's
    tempfile resolver can be cached before an environment override is applied.
    The current tempfile root covers the platform-selected temporary location.
    """
    candidates: list[str | Path] = ["/tmp"]
    if configured := os.environ.get("TMPDIR"):
        candidates.append(configured)
    try:
        candidates.append(tempfile.gettempdir())
    except (OSError, RuntimeError):
        # An unreadable temp configuration means we retain the proven `/tmp`
        # root; callers still fail closed if a required path cannot be resolved.
        pass

    roots: list[Path] = []
    for candidate in candidates:
        try:
            resolved = _normalized_path(candidate)
        except OSError:
            continue
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _codex_temp_root_overlap(
    integration_root: str | Path,
    assigned_worktree: str | Path,
    runtime_temp_roots: tuple[str | Path, ...] | None,
) -> tuple[str, Path, Path] | None:
    """Return the first protected repository path overlapping an extra root."""
    roots = runtime_temp_roots if runtime_temp_roots is not None else _codex_runtime_temp_roots()
    normalized_roots = tuple(_normalized_path(root) for root in roots)
    protected_paths = (
        ("integration_root", _normalized_path(integration_root)),
        ("assigned_worktree", _normalized_path(assigned_worktree)),
    )
    for label, protected_path in protected_paths:
        for root in normalized_roots:
            if _path_is_within(protected_path, root):
                return label, protected_path, root
    return None


def determine_codex_tier(
    *,
    codex_bin: str | None = None,
    require_hard: bool = False,
    platform_system: str | None = None,
    integration_root: str | Path | None = None,
    assigned_worktree: str | Path | None = None,
    runtime_temp_roots: tuple[str | Path, ...] | None = None,
) -> EnforcementDecision:
    """Decide the enforcement tier for a platform-controlled Codex delegation.

    Empirically checks the installed codex binary's own --help output for the
    workspace-write sandbox flag rather than assuming a fixed CLI surface, since
    the interface can evolve. HARD additionally requires a normalized repository
    topology that does not overlap known runtime-added temporary writable roots.
    If require_hard is set and hard containment cannot be established, this
    fails closed (raises) instead of silently downgrading.
    """
    binary = shutil.which(codex_bin) if codex_bin else shutil.which("codex")
    system = platform_system or platform.system()

    if binary is None:
        decision = EnforcementDecision(
            EnforcementTier.DETECTION_ONLY,
            "detection-only:codex-binary-not-found",
            "codex executable not found on PATH; cannot establish a workspace-write sandbox.",
        )
    elif system not in _HARD_SANDBOX_OS:
        decision = EnforcementDecision(
            EnforcementTier.DETECTION_ONLY,
            f"detection-only:unsupported-os:{system}",
            f"No supported OS sandbox (Seatbelt/Landlock) is known for platform {system!r}.",
        )
    else:
        help_text = _codex_help_text(binary)
        if CODEX_SANDBOX_FLAG not in help_text or CODEX_SANDBOX_MODE not in help_text:
            decision = EnforcementDecision(
                EnforcementTier.DETECTION_ONLY,
                "detection-only:sandbox-flag-unsupported",
                "Installed codex build does not advertise a workspace-write sandbox flag in `codex exec --help`.",
            )
        elif integration_root is None or assigned_worktree is None:
            decision = EnforcementDecision(
                EnforcementTier.DETECTION_ONLY,
                "detection-only:topology-unavailable",
                "Codex repository topology was not supplied, so temp-root overlap cannot be ruled out.",
            )
        else:
            try:
                overlap = _codex_temp_root_overlap(integration_root, assigned_worktree, runtime_temp_roots)
            except OSError as exc:
                decision = EnforcementDecision(
                    EnforcementTier.DETECTION_ONLY,
                    "detection-only:topology-unresolvable",
                    f"Codex repository topology could not be normalized: {exc}",
                )
            else:
                if overlap is not None:
                    label, protected_path, temp_root = overlap
                    decision = EnforcementDecision(
                        EnforcementTier.DETECTION_ONLY,
                        "detection-only:runtime-temp-root-overlap",
                        f"{label} {protected_path} resolves inside Codex runtime-writable temp root {temp_root}.",
                    )
                else:
                    decision = EnforcementDecision(
                        EnforcementTier.HARD,
                        "codex-workspace-write-sandbox",
                        f"codex {CODEX_SANDBOX_FLAG} {CODEX_SANDBOX_MODE} on {system}; "
                        "protected repository paths are outside known runtime-added temp roots.",
                    )

    if require_hard and decision.tier is not EnforcementTier.HARD:
        raise ContainmentError(
            f"hard containment was required for this Codex delegation but could not be established: {decision.detail}"
        )
    return decision


def build_codex_argv(
    codex_bin: str,
    assigned_worktree: Path,
    tier: EnforcementTier,
    prompt_args: list[str],
) -> list[str]:
    """Build the codex CLI argv for the resolved tier.

    Hard tier supplies only the assigned worktree through Codex flags and
    deliberately omits --add-dir for any other repository path. Runtime-known
    temporary roots are assessed separately by determine_codex_tier.
    """
    argv = [codex_bin, "exec"]
    if tier is EnforcementTier.HARD:
        argv += [CODEX_SANDBOX_FLAG, CODEX_SANDBOX_MODE, CODEX_CD_FLAG, str(assigned_worktree)]
    argv += prompt_args
    return argv


# --------------------------------------------------------------------------
# Claude adapter: hook-assisted prevention for structured write tools, truthful
# about the shell boundary.
# --------------------------------------------------------------------------

_GUARD_SCRIPT_TEMPLATE = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    # Ephemeral PreToolUse guard generated by delegated_write_guard.py. Not a
    # tracked project file -- regenerated fresh for each guarded delegation.
    import json
    import sys
    from pathlib import Path

    ASSIGNED_WORKTREE = Path({assigned_worktree!r}).resolve()
    TARGET_KEYS = ("file_path", "path", "notebook_path")


    def _decision(permission_decision, reason=None):
        payload = {{
            "hookSpecificOutput": {{
                "hookEventName": "PreToolUse",
                "permissionDecision": permission_decision,
            }}
        }}
        if reason is not None:
            payload["hookSpecificOutput"]["permissionDecisionReason"] = reason
        json.dump(payload, sys.stdout)


    def main() -> int:
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError:
            _decision("allow")
            return 0
        tool_input = payload.get("tool_input") or {{}}
        target = next((tool_input[key] for key in TARGET_KEYS if key in tool_input), None)
        if target is None:
            _decision("allow")
            return 0
        resolved = Path(target)
        if not resolved.is_absolute():
            resolved = ASSIGNED_WORKTREE / resolved
        resolved = resolved.resolve()
        try:
            resolved.relative_to(ASSIGNED_WORKTREE)
        except ValueError:
            _decision("deny", f"{{resolved}} is outside the assigned worktree {{ASSIGNED_WORKTREE}}")
            return 0
        _decision("allow")
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    """
)


def render_pretooluse_guard_script(assigned_worktree: Path) -> str:
    return _GUARD_SCRIPT_TEMPLATE.format(assigned_worktree=str(assigned_worktree))


@dataclass(frozen=True)
class ClaudeGuard:
    guard_dir: Path
    hook_script: Path
    settings_path: Path


def write_claude_guard(assigned_worktree: Path, *, guard_dir: Path | None = None) -> ClaudeGuard:
    """Write an ephemeral PreToolUse hook + settings.json denying writes outside assigned_worktree.

    Always written under a fresh temp directory unless the caller explicitly provides
    guard_dir; never touches a project-tracked settings path.
    """
    directory = guard_dir or Path(tempfile.mkdtemp(prefix="dev-platform-guard-"))
    directory.mkdir(parents=True, exist_ok=True)
    hook_script = directory / "pretooluse_guard.py"
    hook_script.write_text(render_pretooluse_guard_script(assigned_worktree), encoding="utf-8")
    hook_script.chmod(hook_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit|NotebookEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"{sys.executable} {hook_script}",
                        }
                    ],
                }
            ]
        }
    }
    settings_path = directory / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return ClaudeGuard(guard_dir=directory, hook_script=hook_script, settings_path=settings_path)


def determine_claude_tier(*, shell_enabled: bool) -> EnforcementDecision:
    """Decide the enforcement tier for a platform-controlled Claude Code delegation.

    Structured Write/Edit/NotebookEdit targets can be resolved and denied before the
    write occurs by a PreToolUse hook -- a real pre-write enforcement point -- so a
    session restricted to those tools is HARD. Arbitrary shell access defeats that
    boundary (a shell command can write via `cat`, `sed -i`, `mv`, ...), so any
    shell-capable session is DETECTION_ONLY regardless of the hook being installed.
    """
    if shell_enabled:
        return EnforcementDecision(
            EnforcementTier.DETECTION_ONLY,
            "detection-only:claude-shell-capable",
            "Arbitrary shell-capable Claude delegation has no proven OS filesystem sandbox; "
            "command-text inspection alone is not hard containment.",
        )
    return EnforcementDecision(
        EnforcementTier.HARD,
        "claude-structured-write-hook",
        "Write/Edit/NotebookEdit targets are resolved and denied before the write via a "
        "platform-installed PreToolUse hook; no shell-capable tool is enabled for this session.",
    )


def build_claude_argv(claude_bin: str, guard: ClaudeGuard, extra_args: list[str]) -> list[str]:
    return [claude_bin, "--settings", str(guard.settings_path), *extra_args]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _split_argv(raw: list[str]) -> list[str]:
    if raw and raw[0] == "--":
        return raw[1:]
    return raw


def _cmd_codex(args: argparse.Namespace) -> int:
    integration_root = Path(args.integration_root).resolve()
    resolved_worktree = resolve_assigned_worktree(integration_root, args.assigned_worktree)
    try:
        tier_decision = determine_codex_tier(
            codex_bin=args.codex_bin,
            require_hard=args.require_hard,
            integration_root=integration_root,
            assigned_worktree=resolved_worktree,
        )
    except ContainmentError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    binary = args.codex_bin or shutil.which("codex") or "codex"
    argv = build_codex_argv(binary, resolved_worktree, tier_decision.tier, _split_argv(args.child_argv))
    return _run_and_report(integration_root, args.assigned_worktree, argv, tier_decision, args.task)


def _cmd_claude(args: argparse.Namespace) -> int:
    integration_root = Path(args.integration_root).resolve()
    resolved_worktree = resolve_assigned_worktree(integration_root, args.assigned_worktree)
    tier_decision = determine_claude_tier(shell_enabled=args.shell_enabled)
    guard = write_claude_guard(resolved_worktree)
    binary = args.claude_bin or shutil.which("claude") or "claude"
    argv = build_claude_argv(binary, guard, _split_argv(args.child_argv))
    return _run_and_report(integration_root, args.assigned_worktree, argv, tier_decision, args.task)


def _run_and_report(
    integration_root: Path,
    assigned_worktree: str,
    argv: list[str],
    tier_decision: EnforcementDecision,
    task: str | None,
) -> int:
    print(f"enforcement tier: {tier_decision.tier.value} ({tier_decision.mechanism})", file=sys.stderr)
    try:
        result = run_guarded_delegation(
            integration_root=integration_root,
            assigned_worktree=assigned_worktree,
            argv=argv,
            tier_decision=tier_decision,
            task=task,
        )
    except GuardedChildError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ContainmentError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if result.violation:
        print(result.message, file=sys.stderr)
        return 1
    return result.returncode or 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded entrypoint for write-capable delegated execution.")
    sub = parser.add_subparsers(dest="runtime", required=True)

    codex = sub.add_parser("codex", help="Delegate to platform-controlled Codex with a hard writable-root sandbox.")
    codex.add_argument("--integration-root", required=True)
    codex.add_argument("--assigned-worktree", required=True)
    codex.add_argument("--task")
    codex.add_argument("--codex-bin")
    codex.add_argument("--require-hard", action="store_true")
    codex.add_argument("child_argv", nargs=argparse.REMAINDER)
    codex.set_defaults(func=_cmd_codex)

    claude = sub.add_parser("claude", help="Delegate to platform-controlled Claude Code with a structured-write hook guard.")
    claude.add_argument("--integration-root", required=True)
    claude.add_argument("--assigned-worktree", required=True)
    claude.add_argument("--task")
    claude.add_argument("--claude-bin")
    claude.add_argument("--shell-enabled", action="store_true", help="Session includes a shell-capable tool (Bash or equivalent); forces detection-only.")
    claude.add_argument("child_argv", nargs=argparse.REMAINDER)
    claude.set_defaults(func=_cmd_claude)

    return parser


if __name__ == "__main__":
    parsed = build_parser().parse_args()
    raise SystemExit(parsed.func(parsed))
