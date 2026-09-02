"""Shared synchronization helpers for concurrency-sensitive lifecycle tests.

Two timing assumptions repeatedly produced *false* failures when the canonical
suite runs its groups in parallel on a loaded host:

* a fixture read a child's published state (a pid file, a spawned descendant)
  immediately after launch, before the child had scheduled far enough to write
  it; and
* helper subprocesses were awaited with ad-hoc wall-clock ``timeout=`` values
  with no diagnostics and no operator override when a genuine stall did occur.

These helpers fix exactly those assumptions with standard synchronization
primitives. They are outer *test* deadlines, not product policy: the product's
own bounded timeouts (lock acquisition, cleanup grace) stay asserted by
dedicated cases that must keep failing when a real hang is introduced.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Callable

# One bounded outer deadline for helper subprocesses across the concurrency
# tests. Generous on purpose: a real hang is caught here *and* by dedicated
# product-timeout cases, so the only cost of headroom is latency on an already
# failing run. Override with DEV_PLATFORM_TEST_PROCESS_TIMEOUT (seconds).
_DEFAULT_PROCESS_DEADLINE_SECONDS = 30.0
_PROCESS_DEADLINE_ENV = "DEV_PLATFORM_TEST_PROCESS_TIMEOUT"

# Bounded window for a freshly launched helper to publish the state an
# assertion depends on. This measures process-start scheduling only.
_DEFAULT_READINESS_DEADLINE_SECONDS = 10.0


class HelperTimeout(AssertionError):
    """A helper subprocess exceeded its bounded test deadline."""


def process_deadline_seconds() -> float:
    """Bounded helper-subprocess deadline, with an explicit operator override."""
    raw = os.environ.get(_PROCESS_DEADLINE_ENV)
    if raw:
        try:
            value = float(raw)
        except ValueError:
            value = 0.0
        if value > 0:
            return value
    return _DEFAULT_PROCESS_DEADLINE_SECONDS


def wait_for_readiness(
    is_ready: Callable[[], bool],
    process: subprocess.Popen,
    *,
    description: str = "helper",
    deadline_seconds: float = _DEFAULT_READINESS_DEADLINE_SECONDS,
) -> None:
    """Block until ``is_ready()`` holds, an explicit startup handshake.

    Fails with process diagnostics if the helper exits first or never reaches
    readiness within the bounded window -- never on scheduler timing alone.
    """
    deadline = time.monotonic() + deadline_seconds
    while not is_ready():
        code = process.poll()
        if code is not None:
            raise AssertionError(
                f"{description} exited (returncode {code}) before signalling readiness"
            )
        if time.monotonic() >= deadline:
            raise AssertionError(
                f"{description} did not signal readiness within {deadline_seconds:g}s "
                f"(pid {process.pid}, still running)"
            )
        time.sleep(0.01)


def communicate_within_deadline(
    process: subprocess.Popen,
    *,
    description: str = "helper",
    deadline_seconds: float | None = None,
) -> tuple[str, str]:
    """``Popen.communicate`` under the shared bounded deadline.

    On expiry the helper is killed and the failure reports its identity, exit
    state and retained output instead of leaking a bare ``TimeoutExpired``.
    """
    limit = process_deadline_seconds() if deadline_seconds is None else deadline_seconds
    try:
        return process.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            retained_stdout, retained_stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - kill did not settle
            retained_stdout, retained_stderr = "", ""
        raise HelperTimeout(
            f"{description} did not finish within the {limit:g}s bounded test deadline; "
            f"pid={process.pid} returncode={process.returncode} "
            f"retained_stdout={retained_stdout!r} retained_stderr={retained_stderr!r}"
        ) from None
