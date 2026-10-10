#!/usr/bin/env python3
"""Machine-wide pool coordinating heavy validation runs on one host.

Several agents and lifecycle workers on one machine routinely start full
validation at the same time.  Parallelism is capped only inside a single run, so
N runs use N times the workers and timeout-sensitive tests fail from contention.
This module is an opt-in counting pool built on kernel ``flock`` leases:

* ``DEV_PLATFORM_MACHINE_POOL`` names a machine-local TOML file with the keys
  ``directory``, ``tokens``, ``wait_timeout_seconds``, ``max_load_per_cpu`` and
  ``min_available_memory_mb``.  Unset is the declared unpooled mode (the run
  prints ``DEV_PLATFORM_MACHINE_POOL: not configured``); a set but missing or
  invalid configuration fails explicitly.
* ``directory/slot-<i>.lock`` is one token.  A lease holds an exclusive
  non-blocking ``flock`` on ``weight`` slot files for the run and passes the file
  descriptors to child processes (``pass_fds``), so the kernel releases a token
  only when every holder has exited, including after SIGKILL.
* Waiters take an exclusively locked ticket in ``directory/queue``.  Only the head
  ticket (``finalize`` before ``development``, then arrival) may acquire, all or
  nothing, while the per-CPU load and available memory admit the run.  A ticket
  whose lock is no longer held is dead and removed by the next waiter.
* A granted lease is exported as ``DEV_PLATFORM_MACHINE_POOL_LEASE``; a nested
  acquisition that sees it reuses the parent lease and acquires nothing.

``python3 scripts/machine_pool.py status`` is read-only.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import getpass
import json
import math
import os
import re
import secrets
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, MutableMapping

try:
    import fcntl
except ImportError:  # no flock on this platform; only a configured pool needs it and then fails explicitly
    fcntl = None  # type: ignore[assignment]

POOL_ENV = "DEV_PLATFORM_MACHINE_POOL"
LEASE_ENV = "DEV_PLATFORM_MACHINE_POOL_LEASE"
CHECK_CLASS_ENV = "DEV_PLATFORM_CHECK_CLASS"
# Every variable through which a process sees the pool; test processes run without them.
POOL_VARIABLES = (POOL_ENV, LEASE_ENV, CHECK_CLASS_ENV)
NOT_CONFIGURED_LINE = "DEV_PLATFORM_MACHINE_POOL: not configured"
# Priority classes; lower rank is admitted first.  An absent DEV_PLATFORM_CHECK_CLASS
# means `development` by contract.
CLASS_RANKS = {"finalize": 0, "development": 1}
DEFAULT_CLASS = "development"
CONFIG_KEYS = ("directory", "tokens", "wait_timeout_seconds", "max_load_per_cpu", "min_available_memory_mb")
QUEUE_DIRECTORY = "queue"
_TICKET_RE = re.compile(r"^(?P<rank>\d+)-(?P<time>\d+)-(?P<pid>\d+)-(?P<nonce>[0-9a-f]+)\.json$")
_TICKET_ATTEMPTS = 20


class PoolError(RuntimeError):
    """The machine pool cannot be used as configured; the run must not proceed unpooled."""


class PoolConfigError(PoolError):
    """The machine-local pool configuration is missing or invalid."""


class PoolTimeout(PoolError):
    """The wait for pool tokens exceeded the configured timeout."""


@dataclasses.dataclass(frozen=True)
class PoolConfig:
    path: Path
    directory: Path
    tokens: int
    wait_timeout_seconds: int
    max_load_per_cpu: float
    min_available_memory_mb: int

    @property
    def queue(self) -> Path:
        return self.directory / QUEUE_DIRECTORY

    def slot(self, index: int) -> Path:
        return self.directory / f"slot-{index}.lock"

    @property
    def admission_lock(self) -> Path:
        return self.directory / "admission.lock"


# ---------------------------------------------------------------- configuration


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def load_config(environ: MutableMapping[str, str] | None = None) -> PoolConfig | None:
    """Return the validated pool configuration, or ``None`` for the declared unpooled mode."""
    environ = os.environ if environ is None else environ
    if POOL_ENV not in environ:
        return None
    value = environ[POOL_ENV]
    if not value.strip():
        raise PoolConfigError(f"{POOL_ENV} is set but empty; name an absolute machine-local TOML file or unset it")
    path = Path(value)
    if not path.is_absolute():
        raise PoolConfigError(f"{POOL_ENV} must be an absolute path, got {value!r}")
    if not path.is_file():
        raise PoolConfigError(f"{POOL_ENV} names {path}, which is not an existing file")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise PoolConfigError(f"machine pool configuration {path} cannot be read: {exc}") from exc
    missing = [key for key in CONFIG_KEYS if key not in data]
    unknown = sorted(set(data) - set(CONFIG_KEYS))
    if missing:
        raise PoolConfigError(f"machine pool configuration {path} is missing required key(s): {', '.join(missing)}")
    if unknown:
        raise PoolConfigError(
            f"machine pool configuration {path} has unknown key(s): {', '.join(unknown)}; allowed: {', '.join(CONFIG_KEYS)}")

    def positive_int(key: str) -> int:
        item = data[key]
        if not _is_int(item) or item <= 0:
            raise PoolConfigError(f"machine pool configuration {path}: {key} must be a positive integer, got {item!r}")
        return item

    directory_value = data["directory"]
    if not isinstance(directory_value, str) or not directory_value.strip():
        raise PoolConfigError(f"machine pool configuration {path}: directory must be a non-empty string")
    directory = Path(directory_value)
    if not directory.is_absolute():
        raise PoolConfigError(f"machine pool configuration {path}: directory must be an absolute path, got {directory_value!r}")
    if not directory.is_dir():
        raise PoolConfigError(f"machine pool configuration {path}: directory {directory} is not an existing directory")
    if not os.access(directory, os.R_OK | os.W_OK | os.X_OK):
        raise PoolConfigError(f"machine pool configuration {path}: directory {directory} is not readable and writable by this account")
    load = data["max_load_per_cpu"]
    if isinstance(load, bool) or not isinstance(load, (int, float)) or not math.isfinite(load) or load <= 0:
        raise PoolConfigError(f"machine pool configuration {path}: max_load_per_cpu must be a finite positive number, got {load!r}")
    return PoolConfig(
        path=path,
        directory=directory,
        tokens=positive_int("tokens"),
        wait_timeout_seconds=positive_int("wait_timeout_seconds"),
        max_load_per_cpu=float(load),
        min_available_memory_mb=positive_int("min_available_memory_mb"),
    )


def resolve_class(environ: MutableMapping[str, str], explicit: str | None = None) -> str:
    """The priority class: explicit argument, then DEV_PLATFORM_CHECK_CLASS, else `development` by contract."""
    if explicit is not None:
        value = explicit
    elif CHECK_CLASS_ENV in environ:
        value = environ[CHECK_CLASS_ENV]
    else:
        return DEFAULT_CLASS
    if value not in CLASS_RANKS:
        raise PoolError(f"unknown check class {value!r} (from {'argument' if explicit is not None else CHECK_CLASS_ENV}); "
                        f"allowed: {', '.join(sorted(CLASS_RANKS, key=CLASS_RANKS.get))}")
    return value


# ------------------------------------------------------------------ measurements


def measure_load_per_cpu() -> float:
    cpus = os.cpu_count()
    if not cpus:
        raise PoolError("cannot measure load per CPU: os.cpu_count() reported no CPU count")
    try:
        load = os.getloadavg()[0]
    except OSError as exc:
        raise PoolError(f"cannot measure load average: {exc}") from exc
    return load / cpus


def parse_meminfo(text: str) -> float:
    """Available memory in MB from Linux ``/proc/meminfo`` content (``MemAvailable``)."""
    match = re.search(r"^MemAvailable:\s+(\d+)\s*kB\s*$", text, re.MULTILINE)
    if not match:
        raise PoolError("cannot measure available memory: /proc/meminfo has no parseable MemAvailable line")
    return int(match.group(1)) / 1024


def parse_vm_stat(text: str) -> float:
    """Available memory in MB from macOS ``vm_stat`` output (free + inactive + speculative pages)."""
    header = re.search(r"page size of (\d+) bytes", text)
    if not header:
        raise PoolError("cannot measure available memory: vm_stat output has no 'page size of N bytes' header")
    pages = 0
    for label in ("free", "inactive", "speculative"):
        match = re.search(rf"^Pages {label}:\s+(\d+)\.\s*$", text, re.MULTILINE)
        if not match:
            raise PoolError(f"cannot measure available memory: vm_stat output has no parseable 'Pages {label}' line")
        pages += int(match.group(1))
    return pages * int(header.group(1)) / (1024 * 1024)


def measure_available_memory_mb() -> float:
    if sys.platform.startswith("linux"):
        try:
            return parse_meminfo(Path("/proc/meminfo").read_text(encoding="utf-8"))
        except OSError as exc:
            raise PoolError(f"cannot measure available memory: /proc/meminfo cannot be read: {exc}") from exc
    if sys.platform == "darwin":
        try:
            done = subprocess.run(["vm_stat"], capture_output=True, text=True)
        except OSError as exc:
            raise PoolError(f"cannot measure available memory: vm_stat cannot be run: {exc}") from exc
        if done.returncode:
            raise PoolError(f"cannot measure available memory: vm_stat exited {done.returncode}: {done.stderr.strip()}")
        return parse_vm_stat(done.stdout)
    raise PoolError(f"cannot measure available memory: unsupported platform {sys.platform!r}")


def _emit(line: str) -> None:
    print(line, flush=True)


@dataclasses.dataclass(frozen=True)
class Hooks:
    """Injectable clock, poll interval and readers; the defaults are the real machine."""

    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    poll_interval: float = 1.0
    progress_interval: float = 60.0
    load_per_cpu: Callable[[], float] = measure_load_per_cpu
    available_memory_mb: Callable[[], float] = measure_available_memory_mb
    out: Callable[[str], None] = _emit


# --------------------------------------------------------------------- file layer


def _require_flock() -> None:
    if fcntl is None:
        raise PoolError("the machine pool needs fcntl.flock, which this platform does not provide")


def _try_lock(fd: int, path: Path, *, shared: bool = False) -> bool:
    _require_flock()
    try:
        fcntl.flock(fd, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    except OSError as exc:
        raise PoolError(f"cannot lock pool file {path}: {exc}") from exc
    return True


def _permission_error(path: Path, exc: OSError) -> PoolError:
    return PoolError(
        f"permission denied for pool file {path}: every participating account must be able to read and write the pool "
        f"directory and its files ({exc})")


def _share_mode(fd: int) -> None:
    """Make a file we created usable by other accounts regardless of our umask."""
    status = os.fstat(fd)
    if status.st_mode & 0o666 != 0o666 and status.st_uid == os.geteuid():
        os.fchmod(fd, status.st_mode | 0o666)


def _open_shared(path: Path, extra_flags: int = 0) -> int:
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | extra_flags, 0o666)
    except PermissionError as exc:
        raise _permission_error(path, exc) from exc
    except OSError as exc:
        if extra_flags & os.O_EXCL and isinstance(exc, FileExistsError):
            raise
        raise PoolError(f"cannot open pool file {path}: {exc}") from exc
    try:
        _share_mode(fd)
    except OSError as exc:
        os.close(fd)
        raise PoolError(f"cannot make pool file {path} accessible to other accounts: {exc}") from exc
    return fd


def _write_json(fd: int, path: Path, payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    try:
        os.ftruncate(fd, 0)
        os.pwrite(fd, data, 0)
    except PermissionError as exc:
        raise _permission_error(path, exc) from exc
    except OSError as exc:
        raise PoolError(f"cannot write holder metadata into {path}: {exc}") from exc


def _read_metadata(path: Path) -> dict[str, Any]:
    """Display metadata of a slot or ticket; an unreadable record is reported as such, never guessed."""
    try:
        text = path.read_text(encoding="utf-8")
    except PermissionError as exc:
        raise _permission_error(path, exc) from exc
    except FileNotFoundError:
        return {"unavailable": "file removed while reading"}
    except OSError as exc:
        raise PoolError(f"cannot read pool file {path}: {exc}") from exc
    if not text.strip():
        return {"unavailable": "metadata not written yet"}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"unavailable": f"metadata unreadable: {exc}"}
    if not isinstance(payload, dict):
        return {"unavailable": "metadata is not an object"}
    return payload


def _git_branch(root: Path) -> str:
    from _platform_common import validation_subprocess_env

    done = subprocess.run(["git", "-C", str(root), "branch", "--show-current"], capture_output=True, text=True,
                          env=validation_subprocess_env())
    if done.returncode:
        raise PoolError(f"cannot determine the task branch in {root}: {done.stderr.strip() or 'git failed'}")
    return done.stdout.strip() or "(detached)"


def _metadata(lease_id: str, weight: int, check_class: str, purpose: str, root: Path) -> dict[str, Any]:
    now = time.time()
    return {
        "lease": lease_id,
        "user": getpass.getuser(),
        "pid": os.getpid(),
        "project_root": str(root),
        "branch": _git_branch(root),
        "class": check_class,
        "weight": weight,
        "purpose": purpose,
        "started": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"),
        "started_epoch": now,
    }


# -------------------------------------------------------------------------- queue


def _ensure_queue(config: PoolConfig) -> None:
    queue = config.queue
    try:
        queue.mkdir(mode=0o777, exist_ok=True)
        if queue.stat().st_uid == os.geteuid() and queue.stat().st_mode & 0o777 != 0o777:
            queue.chmod(0o777)  # the umask must not hide the queue from other accounts
    except PermissionError as exc:
        raise _permission_error(queue, exc) from exc
    except OSError as exc:
        raise PoolError(f"cannot prepare queue directory {queue}: {exc}") from exc


def _ticket_order(name: str, directory: Path) -> tuple[int, int]:
    match = _TICKET_RE.match(name)
    if not match:
        raise PoolError(f"unexpected entry {directory / name} in the queue directory; only queue tickets belong there")
    return int(match.group("rank")), int(match.group("time"))


def _list_tickets(config: PoolConfig) -> list[str]:
    try:
        names = sorted(entry.name for entry in config.queue.iterdir())
    except FileNotFoundError:
        return []
    except PermissionError as exc:
        raise _permission_error(config.queue, exc) from exc
    return sorted(names, key=lambda name: _ticket_order(name, config.queue))


def _scan_queue(config: PoolConfig, *, remove_dead: bool, own: str | None = None) -> list[tuple[str, bool]]:
    """Ordered ``(ticket name, alive)``; a dead ticket is removed only after its lock was taken."""
    scanned: list[tuple[str, bool]] = []
    for name in _list_tickets(config):
        if name == own:
            scanned.append((name, True))
            continue
        path = config.queue / name
        try:
            fd = os.open(path, os.O_RDONLY)
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            raise _permission_error(path, exc) from exc
        try:
            if not _try_lock(fd, path, shared=not remove_dead):
                scanned.append((name, True))
                continue
            if remove_dead:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
                except PermissionError as exc:
                    raise _permission_error(path, exc) from exc
                continue
            scanned.append((name, False))
        finally:
            os.close(fd)
    return scanned


@dataclasses.dataclass
class _Ticket:
    fd: int
    path: Path

    @property
    def name(self) -> str:
        return self.path.name

    def release(self) -> None:
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        finally:
            os.close(self.fd)


@contextlib.contextmanager
def _admission(config: PoolConfig) -> Iterator[bool]:
    """Try the admission lock without blocking; yields whether it is held for the ``with`` body.

    It serializes ticket creation with admission so a head decision never uses a stale queue. It is never
    waited on: a stopped or hung holder must not stall waiters past their own wait timeout.
    """
    path = config.admission_lock
    fd = _open_shared(path)
    try:
        yield _try_lock(fd, path)
    finally:
        os.close(fd)  # closing the descriptor releases the lock


def _admit_if_head(config: PoolConfig, own: str, weight: int) -> tuple[str | None, list[tuple[int, Path]] | None]:
    """Under the admission lock, re-read the queue and take slots only while ``own`` is still its head.

    Returns ``(wait_reason, held)``: ``held`` when admitted; otherwise why not, including a ticket that joined
    ahead of ``own`` (a finalize run) since the last poll or another run briefly holding the admission lock.
    """
    with _admission(config) as locked:
        if not locked:
            return "another run is being admitted", None
        live = [name for name, _ in _scan_queue(config, remove_dead=True, own=own)]
        if own not in live:
            raise PoolError(f"queue ticket {config.queue / own} disappeared while waiting")
        if live[0] != own:
            return "an earlier-ranked run joined the queue", None
        held = _try_take_slots(config, weight)
        return (None if held is not None else f"fewer than {weight} free token(s)"), held


def _create_ticket(config: PoolConfig, check_class: str, metadata: dict[str, Any], hooks: Hooks,
                   started: float) -> tuple[_Ticket, bool]:
    """Queue a ticket within the run's single wait deadline measured from ``started``.

    Returns the ticket and whether queueing had to wait for the admission lock.
    """
    waited = False
    while True:
        # A deadline that passed while sleeping fails before another attempt.
        if waited and hooks.monotonic() - started >= config.wait_timeout_seconds:
            raise _queueing_timeout(config)
        with _admission(config) as locked:
            if locked:
                return _create_ticket_unlocked(config, check_class, metadata), waited
        waited = True
        if hooks.monotonic() - started >= config.wait_timeout_seconds:
            raise _queueing_timeout(config)
        hooks.sleep(hooks.poll_interval)


def _queueing_timeout(config: PoolConfig) -> PoolTimeout:
    return PoolTimeout(f"machine pool wait timed out after {config.wait_timeout_seconds}s before queueing: "
                       f"{config.admission_lock} stayed locked by another run")


def _create_ticket_unlocked(config: PoolConfig, check_class: str, metadata: dict[str, Any]) -> _Ticket:
    rank = CLASS_RANKS[check_class]
    for _ in range(_TICKET_ATTEMPTS):
        name = f"{rank}-{time.time_ns():020d}-{os.getpid()}-{secrets.token_hex(4)}.json"
        path = config.queue / name
        try:
            fd = _open_shared(path, os.O_EXCL)
        except FileExistsError:
            continue
        if not _try_lock(fd, path):
            os.close(fd)  # a sweeper holds the fresh file; take a new name
            continue
        try:
            same = os.stat(path).st_ino == os.fstat(fd).st_ino
        except FileNotFoundError:
            same = False
        if not same:
            os.close(fd)  # swept between creation and lock; take a new name
            continue
        try:
            _write_json(fd, path, metadata)
        except BaseException:
            _Ticket(fd, path).release()
            raise
        return _Ticket(fd, path)
    raise PoolError(f"cannot create a queue ticket in {config.queue} after {_TICKET_ATTEMPTS} attempts")


# -------------------------------------------------------------------------- slots


def _try_take_slots(config: PoolConfig, weight: int) -> list[tuple[int, Path]] | None:
    """All-or-nothing: lock ``weight`` free slots, or release any taken and return ``None``."""
    held: list[tuple[int, Path]] = []
    try:
        for index in range(config.tokens):
            path = config.slot(index)
            fd = _open_shared(path)
            if _try_lock(fd, path):
                held.append((fd, path))
                if len(held) == weight:
                    return held
            else:
                os.close(fd)
    except BaseException:
        for fd, _ in held:
            os.close(fd)
        raise
    for fd, _ in held:
        os.close(fd)
    return None


def read_holders(config: PoolConfig) -> list[dict[str, Any]]:
    """Live holders grouped by lease; a free slot's stale content is ignored."""
    by_lease: dict[str, dict[str, Any]] = {}
    for index in range(config.tokens):
        path = config.slot(index)
        try:
            fd = os.open(path, os.O_RDONLY)
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            raise _permission_error(path, exc) from exc
        try:
            if _try_lock(fd, path, shared=True):
                fcntl.flock(fd, fcntl.LOCK_UN)
                continue
        finally:
            os.close(fd)
        metadata = _read_metadata(path)
        key = str(metadata.get("lease", f"slot-{index}"))
        entry = by_lease.setdefault(key, {**metadata, "lease": key, "slots": []})
        entry["slots"].append(index)
    return list(by_lease.values())


def _age(metadata: dict[str, Any]) -> str:
    started = metadata.get("started_epoch")
    if not isinstance(started, (int, float)):
        return "age unknown"
    return f"{max(0, int(time.time() - started))}s"


def describe_holder(holder: dict[str, Any]) -> str:
    if "unavailable" in holder:
        return f"slot(s) {holder['slots']}: holder unknown ({holder['unavailable']})"
    return (f"{holder.get('user')} project={holder.get('project_root')} branch={holder.get('branch')} "
            f"class={holder.get('class')} weight={holder.get('weight')} pid={holder.get('pid')} age={_age(holder)}")


def describe_holders(holders: list[dict[str, Any]]) -> str:
    return "; ".join(describe_holder(holder) for holder in holders) if holders else "none"


def _blocked_report(config: PoolConfig, weight: int, check_class: str, position: int, queued: int, reason: str) -> str:
    return (f"DEV_PLATFORM_MACHINE_POOL: waiting for {weight} of {config.tokens} token(s) as class {check_class}; "
            f"queue position {position} of {queued}; {reason}; holders: {describe_holders(read_holders(config))}")


def _acquire(config: PoolConfig, weight: int, check_class: str, purpose: str, root: Path, lease_id: str,
             hooks: Hooks) -> list[int]:
    _ensure_queue(config)
    metadata = _metadata(lease_id, weight, check_class, purpose, root)
    # One deadline covers queueing and admission, so waiting for the admission lock does not extend the limit.
    started = hooks.monotonic()
    ticket, queued_after_wait = _create_ticket(config, check_class, metadata, hooks, started)
    try:
        next_progress = hooks.monotonic()
        first = True
        # (queue position, wait reason) of the previous poll; None until the first poll waited.
        last_wait: tuple[int, str] | None = None
        while True:
            # A deadline that passed while sleeping (or while queueing) fails before any admission attempt.
            if (last_wait is not None or queued_after_wait) \
                    and hooks.monotonic() - started >= config.wait_timeout_seconds:
                where = (f"queue position {last_wait[0]}; {last_wait[1]}" if last_wait is not None
                         else f"queued only after waiting for {config.admission_lock}")
                raise PoolTimeout(
                    f"machine pool wait timed out after {config.wait_timeout_seconds}s for {weight} token(s) as class "
                    f"{check_class} ({where}); holders: {describe_holders(read_holders(config))}")
            live = [name for name, _ in _scan_queue(config, remove_dead=True, own=ticket.name)]
            if ticket.name not in live:
                raise PoolError(f"queue ticket {ticket.path} disappeared while waiting")
            position = live.index(ticket.name) + 1
            # Measured on the first pass by every waiter so that an unmeasurable value fails at once,
            # afterwards only by the head, which is the only one that can be admitted.
            load = memory = None
            if first or position == 1:
                load = hooks.load_per_cpu()
                memory = hooks.available_memory_mb()
            first = False
            if position != 1:
                reason = f"waiting behind {position - 1} earlier queued run(s)"
            elif load > config.max_load_per_cpu:
                reason = f"load per CPU {load:.2f} exceeds the limit {config.max_load_per_cpu:g}"
            elif memory < config.min_available_memory_mb:
                reason = f"available memory {memory:.0f} MB is below the minimum {config.min_available_memory_mb} MB"
            else:
                wait_reason, held = _admit_if_head(config, ticket.name, weight)
                if held is not None:
                    try:
                        for fd, path in held:
                            _write_json(fd, path, metadata)
                    except BaseException:
                        for fd, _ in held:
                            os.close(fd)
                        raise
                    return [fd for fd, _ in held]
                reason = wait_reason
            now = hooks.monotonic()
            if now - started >= config.wait_timeout_seconds:
                raise PoolTimeout(
                    f"machine pool wait timed out after {config.wait_timeout_seconds}s for {weight} token(s) as class "
                    f"{check_class} (queue position {position}; {reason}); holders: {describe_holders(read_holders(config))}")
            if now >= next_progress:
                hooks.out(_blocked_report(config, weight, check_class, position, len(live), reason))
                next_progress = now + hooks.progress_interval
            last_wait = (position, reason)
            hooks.sleep(hooks.poll_interval)
    finally:
        ticket.release()


# ------------------------------------------------------------------------- lease


@dataclasses.dataclass(frozen=True)
class Lease:
    """A granted (or inherited) pool lease.

    ``weight`` is the tokens held (``None`` in the declared unpooled mode); ``fds`` are the descriptors to pass
    to child processes with ``pass_fds`` so they keep the tokens if this process dies first.
    """

    id: str
    pooled: bool
    nested: bool
    weight: int | None
    fds: tuple[int, ...]
    check_class: str | None


def _parse_lease(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise PoolError(f"{LEASE_ENV} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), str) or not isinstance(payload.get("pooled"), bool):
        raise PoolError(f"{LEASE_ENV} must be a JSON object with a string id and a boolean pooled flag")
    if payload["pooled"]:
        fds = payload.get("fds")
        if not _is_int(payload.get("weight")) or payload["weight"] <= 0 or not isinstance(fds, list) \
                or not all(_is_int(fd) and fd >= 0 for fd in fds):
            raise PoolError(f"{LEASE_ENV} describes a pooled lease without a positive weight and a list of descriptors")
        # A pooled lease holds one locked slot descriptor per token; anything else cannot prove the tokens are held.
        if len(fds) != payload["weight"] or len(set(fds)) != len(fds):
            raise PoolError(f"{LEASE_ENV} pooled lease of weight {payload['weight']} must list exactly "
                            f"{payload['weight']} distinct descriptor(s), got {fds}")
    return payload


def _open_descriptors(fds: list[int]) -> tuple[int, ...]:
    """Require every parent lease descriptor to be open so this process keeps its tokens."""
    missing = []
    for fd in fds:
        try:
            os.fstat(fd)
        except OSError:
            missing.append(fd)
    if missing:
        raise PoolError(f"{LEASE_ENV} pooled lease is missing inherited descriptor(s): "
                        f"{', '.join(map(str, missing))}; pass every lease descriptor with pass_fds")
    return tuple(fds)


def child_lease_descriptors(environ: MutableMapping[str, str] | None = None) -> tuple[int, ...]:
    """Return exported lease descriptors for a child, failing if pooled descriptors are closed."""
    environ = os.environ if environ is None else environ
    if LEASE_ENV not in environ:
        return ()
    parent = _parse_lease(environ[LEASE_ENV])
    return _open_descriptors(parent["fds"]) if parent["pooled"] else ()


@contextlib.contextmanager
def lease(weight: int, purpose: str, *, bounded: bool = False, check_class: str | None = None,
          root: Path | None = None, environ: MutableMapping[str, str] | None = None,
          hooks: Hooks | None = None) -> Iterator[Lease]:
    """Hold ``weight`` pool tokens for the ``with`` body, or reuse the parent's lease.

    ``bounded`` caps ``weight`` at the configured token count (the lease weight is then the run's parallelism);
    otherwise a weight above the tokens fails.  The lease is exported in ``DEV_PLATFORM_MACHINE_POOL_LEASE`` for
    the duration so child processes reuse it.
    """
    environ = os.environ if environ is None else environ
    hooks = Hooks() if hooks is None else hooks
    if LEASE_ENV in environ:
        parent = _parse_lease(environ[LEASE_ENV])
        yield Lease(id=parent["id"], pooled=parent["pooled"], nested=True,
                    weight=parent["weight"] if parent["pooled"] else None,
                    fds=_open_descriptors(parent["fds"]) if parent["pooled"] else (), check_class=None)
        return
    if not _is_int(weight) or weight <= 0:
        raise PoolError(f"lease weight must be a positive integer, got {weight!r}")
    resolved_class = resolve_class(environ, check_class)
    config = load_config(environ)
    lease_id = f"{os.getpid()}-{secrets.token_hex(6)}"
    fds: list[int] = []
    if config is None:
        hooks.out(NOT_CONFIGURED_LINE)
        granted = Lease(id=lease_id, pooled=False, nested=False, weight=None, fds=(), check_class=resolved_class)
        exported = {"id": lease_id, "pooled": False}
    else:
        if weight > config.tokens:
            if not bounded:
                raise PoolError(f"lease weight {weight} exceeds the {config.tokens} configured token(s)")
            weight = config.tokens
        started = hooks.monotonic()
        fds = _acquire(config, weight, resolved_class, purpose, (Path.cwd() if root is None else Path(root)).resolve(),
                       lease_id, hooks)
        hooks.out(f"DEV_PLATFORM_MACHINE_POOL: acquired {weight} of {config.tokens} token(s) as class {resolved_class} "
                  f"after {hooks.monotonic() - started:.0f}s (lease {lease_id})")
        granted = Lease(id=lease_id, pooled=True, nested=False, weight=weight, fds=tuple(fds), check_class=resolved_class)
        exported = {"id": lease_id, "pooled": True, "weight": weight, "fds": fds}
    environ[LEASE_ENV] = json.dumps(exported, sort_keys=True)
    try:
        yield granted
    finally:
        del environ[LEASE_ENV]
        for fd in fds:
            os.close(fd)


# ------------------------------------------------------------------------- status


def status_text(config: PoolConfig, hooks: Hooks | None = None) -> str:
    hooks = Hooks() if hooks is None else hooks
    holders = read_holders(config)
    held = sum(len(holder["slots"]) for holder in holders)
    load = hooks.load_per_cpu()
    memory = hooks.available_memory_mb()
    lines = [
        f"{POOL_ENV}: {config.path}",
        f"directory: {config.directory}",
        f"tokens: {config.tokens} (held {held}, free {config.tokens - held})",
        f"wait_timeout_seconds: {config.wait_timeout_seconds}",
        f"max_load_per_cpu: {config.max_load_per_cpu:g}; current load per CPU: {load:.2f}",
        f"min_available_memory_mb: {config.min_available_memory_mb}; current available memory MB: {memory:.0f}",
        "holders:",
    ]
    lines += [f"  {describe_holder(holder)}" for holder in holders] or ["  none"]
    lines.append("waiters:")
    waiters = _scan_queue(config, remove_dead=False)
    live = [name for name, alive in waiters if alive]
    for position, name in enumerate(live, 1):
        metadata = _read_metadata(config.queue / name)
        detail = describe_holder({**metadata, "slots": []}) if "unavailable" not in metadata else metadata["unavailable"]
        lines.append(f"  {position}. {detail}")
    if not live:
        lines.append("  none")
    dead = [name for name, alive in waiters if not alive]
    if dead:
        lines.append(f"dead tickets awaiting removal by the next waiter: {len(dead)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Machine-wide validation pool.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Read-only: configuration, holders, waiters and load.")
    parser.parse_args(argv)
    try:
        config = load_config()
        if config is None:
            print(NOT_CONFIGURED_LINE)
            return 0
        print(status_text(config))
    except PoolError as exc:
        print(f"machine pool error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
