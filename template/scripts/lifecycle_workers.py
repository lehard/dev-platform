#!/usr/bin/env python3
"""Head-bound lifecycle jobs, claims and the credential-free worker harness.

Claim and validation decisions are pure functions over snapshots; GitHub and
process I/O is injected so everything is testable with fixtures. Jobs reuse the
v2 candidate lifecycle records (``next_job``); claims are separate PR comment
markers. The LLM process never holds a credential: only this harness pushes.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
import re
import secrets
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from _platform_common import (REFUSED_HOME_PATHS, ProjectCheckRuntimeError, check_runtime_declaration,
                              credential_free_env, project_check_env, read_platform_config, refused_home_path)
from candidate_lifecycle import derive_candidate, trusted_marker_comment
import disposable_repository_sandbox
import github_read_cache as read_cache
from github_read_cache import GithubReadCacheError

CLAIM_PREFIX = "dev-platform-lifecycle-claim:v1 "
JOB_KINDS = frozenset({"review", "repair", "integration-repair", "integration-merge", "finalize", "retrospective",
                       "terminal-reconciliation", "cleanup", "contribution-integration"})
WRITE_KINDS = frozenset({"repair", "integration-repair"})
# Integrates current main through the harness alone: no writer, no provider, no --llm-command (BR-768).
MERGE_ONLY_KIND = "integration-merge"
POST_MERGE_KINDS = frozenset({"retrospective", "terminal-reconciliation", "cleanup"})
STATE_KIND = {"review-pending": "review", "reviewing": "review", "repair-pending": "repair",
              "repairing": "repair", "finalize-pending": "finalize",
              "integration-repair-pending": "integration-repair",
              "contribution-integration-pending": "contribution-integration"}
HEAD = re.compile(r"[0-9a-f]{40}")
RESULT_PREFIX = "dev-platform-lifecycle-result:v1 "
# Hardening for every harness git invocation (never trust repo-local hooks or fsmonitor, never recurse into
# submodules). ``diff.ignoreSubmodules`` is deliberately not set here: it would hide gitlinks from result validation.
SAFE_GIT = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "submodule.recurse=false")
# Harness merges and commits never depend on an ambient git identity (CI runners have none).
HARNESS_IDENTITY = ("-c", "user.name=Lifecycle harness", "-c", "user.email=lifecycle@localhost")
EVIDENCE_NAMES = ("verification.md", "automated-checks.json")
# Files the harness itself installs into a writer checkout; never candidate content.
INSTALLED_FILES = (".dev-platform.toml", disposable_repository_sandbox.MARKER)
# Bounded writer stdout/stderr kept in the local job result only, never in a posted record.
WRITER_OUTPUT_TAIL = 4000
# Bound of an outcome text a job posts (rejection reasons can quote writer-chosen paths).
POSTED_OUTCOME_LIMIT = 300
# A claim released by a failed run is counted per job; this many releases stop offering the job.
MAX_RELEASES = 3
# The red-gate cause a job escalates with once its claim was released after MAX_RELEASES failed runs.
CLAIM_RELEASE_CAUSE = "claim released after failed runs"
RELEASED = "released"


class WorkerError(RuntimeError):
    pass


# ---- worker identity ------------------------------------------------------

WORKER_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@-]{0,63}")
WORKER_ENV = "DEV_PLATFORM_WORKER"


def validate_worker_identity(value: Any) -> str:
    """The one identity validator; every claim and result record passes through it."""
    if not isinstance(value, str) or WORKER_IDENTITY.fullmatch(value) is None:
        raise WorkerError(f"invalid worker identity {value!r}: expected {WORKER_IDENTITY.pattern}")
    return value


def resolve_worker_identity(explicit: str | None, environ: dict[str, str], *, hostname: str, pid: int, nonce: str) -> str:
    """The single identity of one run: explicit option, then ``DEV_PLATFORM_WORKER``, else generated.

    An invalid explicit value is never replaced by a generated one. The generated form
    ``worker-<host>-<pid>-<nonce>`` is unique across hosts, reused PIDs and relaunches.
    """
    if explicit is not None:
        return validate_worker_identity(explicit)
    if WORKER_ENV in environ:
        return validate_worker_identity(environ[WORKER_ENV])
    if not isinstance(hostname, str) or not hostname.strip():
        raise WorkerError("cannot generate a worker identity: the host name is empty; pass --worker")
    host = re.sub(r"[^a-z0-9.-]", "-", hostname.strip().lower())[:24]
    return validate_worker_identity(f"worker-{host}-{pid}-{nonce}")


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


# ---- jobs -----------------------------------------------------------------

def job_id(job: dict) -> str:
    suffix = ":t" + job["target_head"] if job.get("target_head") else ""
    # A re-offered pre-merge retrospective moves to its next bounded attempt, which already makes the
    # id distinct; its operator event stays audit-only so the attempt bound keeps counting results.
    reoffer = (f":r{job['reoffer']['seq']}" if isinstance(job.get("reoffer"), dict) and job.get("phase") != "pre-merge"
               else "")
    return (f"pr{job['number']}:{job['kind']}:{job['head']}:a{job['attempt']}" + reoffer + suffix
            + (":pre-merge" if job.get("phase") == "pre-merge" else ""))


def job_record(kind: str, head: str, task_identity: str | dict, attempt: int, *, providers=None, target_head=None, phase=None,
               reoffer=None) -> dict:
    """The explicit ``next_job`` a coordinator publishes in a handoff record."""
    if kind not in JOB_KINDS or not HEAD.fullmatch(str(head)) or type(attempt) is not int or attempt < 0:
        raise ValueError("invalid job record")
    if not isinstance(task_identity, (str, dict)) or not task_identity:
        raise ValueError("missing task identity")
    if kind == "contribution-integration" and not HEAD.fullmatch(str(target_head)):
        raise ValueError("contribution integration job requires exact target head")
    if phase is not None and (phase != "pre-merge" or kind != "retrospective"):
        raise ValueError("invalid job phase")
    if reoffer is not None and (not isinstance(reoffer, dict) or type(reoffer.get("seq")) is not int or reoffer["seq"] < 1
                                or not (kind in {"review", "repair", "finalize"} or phase == "pre-merge")):
        raise ValueError("invalid job re-offer")
    return {"kind": kind, "head": head, "task_identity": task_identity, "attempt": attempt,
            **({"phase": phase} if phase else {}),
            **({"providers": list(providers)} if providers is not None else {}),
            **({"reoffer": dict(reoffer)} if reoffer is not None else {}),
            **({"target_head": target_head} if target_head is not None else {})}


def build_job(candidate: dict) -> dict | None:
    """The head-bound job a derived candidate currently offers, if any.

    Explicit fields of the published ``next_job`` win; the candidate's head,
    identity and attempts fill only what is absent. A job published for another
    head than the candidate's current one is stale and offers nothing, and a PR
    without any trusted coordinator record (no task identity) offers no job.
    """
    if candidate.get("task_identity") is None:
        return None
    head = candidate.get("head")
    if not isinstance(head, str) or not HEAD.fullmatch(head):
        return None
    next_job = candidate.get("next_job")
    explicit = next_job if isinstance(next_job, dict) else {}
    kind = explicit.get("kind") if explicit else STATE_KIND.get(candidate.get("state"))
    if kind not in JOB_KINDS:
        return None
    job_head = explicit.get("head", head)
    if job_head != head:
        return None
    attempt = explicit.get("attempt")
    if type(attempt) is not int:
        attempt = candidate.get("attempts", {}).get(kind, 0)
    return {"kind": kind, "number": candidate["number"], "head": job_head,
            "task_identity": explicit.get("task_identity", candidate.get("task_identity")), "attempt": attempt,
            **{key: explicit[key] for key in ("provider", "providers", "target_head", "phase", "reoffer") if key in explicit}}


def job_providers(job: dict) -> list[str]:
    """The validated provider list of a job, or a ``WorkerError`` naming the pull request."""
    from model_routing import PROVIDERS

    where = f"PR #{job.get('number')} {job.get('kind')} job"
    providers, single = job.get("providers"), job.get("provider")
    if providers is None and single is None:
        raise WorkerError(f"{where} has no provider")
    if providers is None:
        providers = [single]
    if (not isinstance(providers, list) or not providers
            or any(not isinstance(name, str) or name not in PROVIDERS for name in providers)):
        raise WorkerError(f"{where} has an empty or unsupported provider list {providers!r}")
    if single is not None and single not in providers:
        raise WorkerError(f"{where} provider {single!r} contradicts its provider list {providers!r}")
    return list(providers)


REOFFER_AUTHORIZING_ACTIONS = ("switch-provider", "retry-unavailable")


def authorized_repair_providers(route: dict | None, providers: list[str], reoffer: Any, where: str, *,
                                switched: list[str] | None = None) -> list[str]:
    """The single provider a repair job may run on.

    The default is the originating route provider recorded on the candidate handoff. An explicit recorded
    operator re-offer (``switch-provider``; an unavailable-runtime retry only repeats an already authorized
    list) naming exactly the job's provider authorizes it. Anything else fails.
    """
    if not isinstance(route, dict) or not route.get("provider"):
        raise WorkerError(f"{where} has no originating task route; re-run developer handoff")
    if len(providers) != 1:
        raise WorkerError(f"{where} must name exactly one provider, got {providers!r}")
    if providers == [route["provider"]]:
        return providers
    if (isinstance(reoffer, dict) and reoffer.get("action") in REOFFER_AUTHORIZING_ACTIONS
            and reoffer.get("to") == providers):
        return providers
    if switched is not None and list(switched) == providers:
        return providers  # the operator's recorded switch persists for later repair rounds of the candidate
    raise WorkerError(f"{where} provider {providers[0]!r} is neither the originating route provider "
                      f"{route['provider']!r} nor named by a recorded operator re-offer")


def require_job_provider(job: dict, worker_provider: str | None) -> str:
    """Repair work names exactly one provider and only a worker serving it may run the job."""
    providers = job_providers(job)
    if len(providers) != 1:
        raise WorkerError(f"PR #{job.get('number')} {job.get('kind')} job must name exactly one provider, got {providers!r}")
    if worker_provider is None:
        raise WorkerError("--provider is required for repair kinds")
    if worker_provider != providers[0]:
        raise WorkerError(f"PR #{job.get('number')} {job.get('kind')} job requires provider {providers[0]}, "
                          f"this worker serves {worker_provider}")
    return providers[0]


def claim_body(job: dict, worker: str, expires_at: str, provider: str | None = None) -> str:
    if job.get("kind") not in JOB_KINDS or not HEAD.fullmatch(str(job.get("head", ""))):
        raise ValueError("invalid job")
    if _parse_time(expires_at) is None:
        raise ValueError("invalid expiry")
    record = {"job": job_id(job), "worker": validate_worker_identity(worker), "head": job["head"], "expires_at": expires_at}
    if provider is not None:
        record["provider"] = provider
    return CLAIM_PREFIX + json.dumps(record, sort_keys=True, separators=(",", ":"))


def _claims(job: dict, comments: list[dict], trusted_apps, trusted_writers) -> list[tuple[dict, dict]]:
    found = []
    for row in sorted(comments, key=lambda item: item.get("id", 0)):
        body = row.get("body", "")
        if not isinstance(body, str) or not body.startswith(CLAIM_PREFIX):
            continue
        if not trusted_marker_comment(row, trusted_apps, trusted_writers):
            continue
        try:
            record = json.loads(body[len(CLAIM_PREFIX):])
        except ValueError:
            continue
        if (isinstance(record, dict) and record.get("job") == job_id(job)
                and record.get("head") == job["head"] and isinstance(record.get("worker"), str)
                and _parse_time(record.get("expires_at")) is not None):
            found.append((row, record))
    return found


def _releases(job: dict, comments: list[dict], trusted_apps, trusted_writers) -> list[tuple[dict, dict]]:
    """Trusted ``released`` results of this exact job, in comment order."""
    found = []
    for row in sorted(comments, key=lambda item: item.get("id", 0)):
        body = row.get("body")
        if not isinstance(body, str) or not body.startswith(RESULT_PREFIX):
            continue
        if not trusted_marker_comment(row, trusted_apps, trusted_writers):
            continue
        try:
            record = json.loads(body[len(RESULT_PREFIX):])
        except ValueError:
            continue
        if (isinstance(record, dict) and record.get("job") == job_id(job) and record.get("head") == job["head"]
                and str(record.get("outcome", "")).startswith(RELEASED)):
            found.append((row, record))
    return found


def release_count(job: dict, comments: list[dict], *, trusted_apps=frozenset(), trusted_writers=frozenset()) -> int:
    return len(_releases(job, comments, trusted_apps, trusted_writers))


def winning_claim(job: dict, comments: list[dict], *, now: datetime | None = None,
                  trusted_apps: frozenset[str] = frozenset(),
                  trusted_writers: frozenset[str] = frozenset()) -> dict | None:
    """Earliest valid, unexpired, trusted claim for this job and exact head that its worker has not released."""
    current = _now(now)
    releases = _releases(job, comments, trusted_apps, trusted_writers)
    for row, record in _claims(job, comments, trusted_apps, trusted_writers):
        released = any(rel_row.get("id", 0) > row.get("id", 0) and rel.get("worker") == record["worker"]
                       for rel_row, rel in releases)
        if not released and _parse_time(record["expires_at"]) > current:
            return {**record, "comment_id": row.get("id")}
    return None


def latest_claim(job: dict, comments: list[dict], *, trusted_apps: frozenset[str] = frozenset(),
                 trusted_writers: frozenset[str] = frozenset()) -> dict | None:
    """The most recent valid, trusted claim for this job and exact head, expired or not (read-only observation)."""
    found = _claims(job, comments, trusted_apps, trusted_writers)
    return {**found[-1][1], "comment_id": found[-1][0].get("id")} if found else None


def job_completed(job: dict, comments: list[dict], *, trusted_apps=frozenset(), trusted_writers=frozenset()) -> bool:
    """Whether a trusted result was already recorded for this exact job (head and attempt).

    A completed job is not offered again after its claim expires; a new attempt or
    a new head is a different job. A discarded result (head moved) and an unavailable provider runtime complete nothing.
    """
    for row in comments:
        body = row.get("body")
        if not isinstance(body, str) or not body.startswith(RESULT_PREFIX):
            continue
        if not trusted_marker_comment(row, trusted_apps, trusted_writers):
            continue
        try:
            record = json.loads(body[len(RESULT_PREFIX):])
        except json.JSONDecodeError:
            continue
        if (isinstance(record, dict) and record.get("job") == job_id(job) and record.get("head") == job["head"]
                and record.get("outcome") != "validated-push"
                and not str(record.get("outcome", "")).startswith(("discarded", "unavailable", RELEASED))):
            return True
    return False


def is_claimable(job: dict, comments: list[dict], **kwargs) -> bool:
    """Unclaimed, not completed, and released fewer than ``MAX_RELEASES`` times."""
    trust = {key: kwargs[key] for key in ("trusted_apps", "trusted_writers") if key in kwargs}
    return (winning_claim(job, comments, **kwargs) is None and not job_completed(job, comments, **trust)
            and release_count(job, comments, **trust) < MAX_RELEASES)


def release_claim(job: dict, worker: str, exc: BaseException, *, comments_for: Callable[[int], list[dict]],
                  post_comment: Callable[[int, str], None], trusted_apps=frozenset(), trusted_writers=frozenset(),
                  now: datetime | None = None) -> int | None:
    """Release this worker's claim after its run failed; the job's release count, or ``None`` if not ours.

    The posted ``released`` result names the cause, ends the claim at once instead of at its expiry,
    and completes nothing: the job stays claimable until it has been released ``MAX_RELEASES`` times.
    """
    comments = comments_for(job["number"])
    writers = frozenset(trusted_writers(comments)) if callable(trusted_writers) else frozenset(trusted_writers)
    trust = dict(trusted_apps=trusted_apps, trusted_writers=writers)
    if not i_won(job, worker, comments, now=now, **trust):
        return None
    cause = f"{RELEASED}: {type(exc).__name__}: {exc}"[:POSTED_OUTCOME_LIMIT]
    post_comment(job["number"], result_body(job, worker, cause))
    return release_count(job, comments, **trust) + 1


def i_won(job: dict, worker: str, comments: list[dict], **kwargs) -> bool:
    claim = winning_claim(job, comments, **kwargs)
    return claim is not None and claim["worker"] == worker


def result_is_current(job: dict, result_head: str, current_head: str) -> bool:
    """A result for any head other than the job's and the PR's current head is discarded."""
    return job["head"] == result_head == current_head


# A successful lease push proves nobody moved the branch before it; the pull request
# API may still report the previous head for a few seconds afterwards.
PUSH_CONVERGENCE_SECONDS = 60
PUSH_CONVERGENCE_INTERVAL = 3


def own_result_landed(current_head: Callable[[], str], job_head: str, result_head: str, *,
                      clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> bool:
    """Whether the pull request now reports this job's own result head.

    Without a push (``result_head == job_head``) the head must still be the job head.
    After a push the observation may lag: while it still reports ``job_head`` it is
    re-read until ``timeout``; any other head means someone else moved the branch
    (``False``, the job is discarded). A head that never converges raises: the
    pushed result is not silently discarded.
    """
    observed = current_head()
    if result_head == job_head or observed != job_head:
        return observed == result_head
    deadline = clock() + PUSH_CONVERGENCE_SECONDS
    while observed == job_head:
        if clock() >= deadline:
            raise WorkerError(f"pull request head did not converge to pushed head {result_head[:12]} within "
                              f"{PUSH_CONVERGENCE_SECONDS} seconds; it still reports {job_head[:12]}")
        sleep(PUSH_CONVERGENCE_INTERVAL)
        observed = current_head()
    return observed == result_head


# ---- environment ----------------------------------------------------------

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


WRITERS = ("claude-sandboxed",)


def sandboxed_claude_writer(root: Path) -> tuple[list[str], Callable[..., Any]]:
    """The platform repair writer: Claude on the balanced R2 tier under the BR-576 sandbox launch.

    Returns the writer argv (the job task is appended as its final argument) and the launch that replaces
    ``run_llm``. Every prerequisite (macOS, sandbox runtime, Claude CLI, operator token file) is checked by
    the launch and a missing one fails the job explicitly; there is no unsandboxed fallback.
    """
    import model_routing
    import sandboxed_writer

    config = read_platform_config(root)
    argv = ["claude", "-p", "--permission-mode", "dontAsk", "--allowedTools", model_routing.CLAUDE_WRITER_TOOLS,
            "--no-session-persistence", "--strict-mcp-config", "--model", model_routing._model_for(config, "claude", "standard")]

    def launch(command: list[str], checkout: Path, *, tmp: Path, env, runner, home: Path) -> Any:
        try:
            return sandboxed_writer.launch_sandboxed_writer(
                command, checkout, integration_root=root, platform_root=root.parent, workdir=Path(tmp).parent,
                home=home, tmp=tmp, config=config, runner=runner)
        except sandboxed_writer.SandboxedWriterError as exc:
            raise WorkerError(f"sandboxed Claude writer refused to launch: {exc}") from exc

    return argv, launch


CANDIDATE_PATHS_LIMIT = 300


def candidate_paths(repo: str, number: int, *, gh_json: Callable[..., Any] | None = None) -> list[str]:
    """The paths the pull request itself changes (GitHub compares from the merge base), bounded."""
    rows = (gh_json or _gh_json)("api", "--paginate", f"repos/{repo}/pulls/{number}/files?per_page=100")
    if not isinstance(rows, list) or len(rows) >= CANDIDATE_PATHS_LIMIT:
        raise WorkerError(f"PR #{number} changed-path inventory is unavailable or exceeds {CANDIDATE_PATHS_LIMIT} files")
    paths = [row.get("filename") for row in rows if isinstance(row, dict)]
    if not paths or not all(isinstance(path, str) and path for path in paths):
        raise WorkerError(f"PR #{number} has no provable changed paths for the writer scope")
    return sorted(set(paths))


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


def provider_readiness(root: Path, providers, *, workdir, home_files=(), probe=None) -> dict[str, str | None]:
    """Probe each provider once in the scratch environment its job would use: ``{provider: limitation or None}``."""
    import independent_review_runner as runner

    probe = probe or runner.preflight
    unsupported = [provider for provider in providers if provider not in runner.PROVIDERS]
    if unsupported:
        raise WorkerError(f"unsupported provider {unsupported[0]!r}; use one of {', '.join(runner.PROVIDERS)}")
    clean = credential_free_env(dict(os.environ), scratch_home(Path(workdir), home_files))
    launcher = lambda argv, cwd, timeout: runner.subprocess_launcher(argv, cwd, timeout, env=clean)
    base = {key: value for key, value in runner.settings(root).items() if key not in {"provider", "providers"}}
    readiness = {}
    for provider in dict.fromkeys(providers):
        result = probe(root, config={**base, "provider": provider}, launcher=launcher)
        readiness[provider] = None if result.get("ready") else str(result.get("limitation") or f"the {provider} readiness probe reported not ready without stating a limitation")
    return readiness


def needs_private_backlog(job: dict) -> bool:
    """A composition review of an opaque (private-lineage) Requirement resolves its parent through the Backlog."""
    from requirement_integration import ISSUE_RE

    identity = job.get("task_identity")
    return (job["kind"] == "review" and isinstance(identity, dict) and identity.get("kind") == "requirement-composition"
            and not ISSUE_RE.fullmatch(str(identity.get("requirement", ""))))


def job_eligible(job: dict, *, review_ready=None, repair_ready=None, backlog_configured: bool | None = None) -> bool:
    """Whether a worker that proved these providers can run the job; ``None`` means that kind is unfiltered.

    ``backlog_configured=False`` names a worker without a Development Backlog (a hosted runner): it
    skips, before any claim, a job it could not finish.
    """
    if backlog_configured is False and needs_private_backlog(job):
        return False
    ready = {"review": review_ready, "repair": repair_ready}.get(job["kind"])
    if ready is None:
        return True
    named = job.get("providers", [job["provider"]] if "provider" in job else [])
    return bool(set(named) & set(ready))


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


SOURCE_CONTRACT = Path("dev-platform") / "source-contract.toml"


def checkout_harness(harness: Path, head: str) -> None:
    """Detach a harness-owned clone at ``head`` and install its platform contract before any config read.

    ``prepare_harness`` clones without a checkout, so the contract can only be installed once the
    head is checked out; it is excluded locally and never becomes candidate content.
    """
    _git(harness, "checkout", "--detach", head)
    install_source_contract(harness)


def install_source_contract(checkout: Path, contract_from: Path | None = None) -> None:
    """Give a clean checkout the committed contract, exactly as the CI publication queue does.

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


# ---- harness validation and push -------------------------------------------

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


def _allowed(path: str, allowed_paths) -> bool:
    return any(path == a or path.startswith(a.rstrip("/") + "/") for a in allowed_paths)


def _refusal(reason: str, paths: list[str]) -> WorkerError:
    """One bounded refusal: the first offending path plus how many more there are."""
    more = f" (+{len(paths) - 1} more)" if len(paths) > 1 else ""
    return WorkerError(f"{reason}: {paths[0]}{more}")


def refuse_write_paths(paths, allowed_paths) -> None:
    """Raise one bounded ``WorkerError`` when any path is a forbidden edit or outside the candidate scope."""
    refused = [(_forbidden(path) or "path outside candidate scope", path) for path in paths
               if _forbidden(path) or not _allowed(path, allowed_paths)]
    if refused:
        raise _refusal(refused[0][0], [path for _, path in refused])


def validate_worker_result(repo: Path, expected_head: str, result_head: str,
                           allowed_paths, kind: str = "repair") -> list[str]:
    """Return the changed paths of an acceptable result or raise WorkerError."""
    if kind not in WRITE_KINDS:
        raise WorkerError(f"{kind} jobs have no write path")
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
    refuse_write_paths(changed, allowed_paths)
    return changed


def push_command(branch: str, expected_head: str, result_head: str) -> list[str]:
    return ["git", *SAFE_GIT, "-c", "credential.useHttpPath=true", "push", "origin", f"{result_head}:refs/heads/{branch}",
            f"--force-with-lease=refs/heads/{branch}:{expected_head}"]


def active_gh_token(checkout: Path, env: dict[str, str]) -> str:
    """The candidate-branch push credential: gh's active token (an exported GH_TOKEN, else the gh login).

    gh output is never echoed, so a failure cannot leak a credential.
    """
    done = subprocess.run(["gh", "auth", "token"], cwd=checkout, env={**env, "GH_PROMPT_DISABLED": "1"},
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    token = done.stdout.strip() if done.returncode == 0 else ""
    if not token:
        raise WorkerError("harness GitHub push requires an authenticated gh credential (gh auth token failed)")
    return token


def harness_push_env(checkout: Path, env: dict[str, str] | None = None) -> dict[str, str]:
    """One push process only; no token in argv, config files or writer checkouts."""
    from urllib.parse import urlsplit

    result = {k: v for k, v in (os.environ if env is None else env).items() if k != "CLAUDE_CODE_OAUTH_TOKEN"}
    origin = harness_git(checkout, "remote", "get-url", "--push", "origin").strip()
    parsed = urlsplit(origin)
    if not origin:
        raise WorkerError("harness push origin is missing")
    if parsed.scheme == "file" or (not parsed.scheme and (checkout / origin).is_dir()):
        return result  # local harness repositories do not require hosted credentials
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username or parsed.password:
        raise WorkerError("harness push requires an uncredentialed GitHub HTTPS origin")
    token = active_gh_token(checkout, result)
    result = {k: v for k, v in result.items() if not k.startswith("GIT_CONFIG_")}
    encoded = base64.b64encode(("x-access-token:" + token).encode()).decode()
    result.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_GLOBAL=os.devnull,
                  GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_COUNT="2",
                  GIT_CONFIG_KEY_0="credential.helper", GIT_CONFIG_VALUE_0="",
                  GIT_CONFIG_KEY_1=f"http.{origin}.extraheader",
                  GIT_CONFIG_VALUE_1="AUTHORIZATION: basic " + encoded)
    return result


def push_validated(repo: Path, branch: str, expected_head: str, result_head: str, *,
                   runner: Callable[..., Any] = subprocess.run, env: dict[str, str] | None = None) -> Any:
    """The only push to a candidate branch. Callers must validate first."""
    done = runner(push_command(branch, expected_head, result_head), cwd=repo,
                  env=harness_push_env(repo) if env is None else env,
                  stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    if done.returncode:
        raise WorkerError(f"push rejected (git push exited {done.returncode})")
    return done


# ---- work-next ------------------------------------------------------------

def select_job(candidates: list[dict], kinds: frozenset[str], claims_by_pr: dict[int, list[dict]], *,
               now: datetime | None = None, trusted_apps=frozenset(), trusted_writers=frozenset(),
               only_prs: frozenset[int] | None = None, eligible: Callable[[dict], bool] | None = None,
               executor_provider: str | None = None, unauthorized: list[dict] | None = None,
               invalid: list[dict] | None = None) -> dict | None:
    """The first claimable job of the requested kinds.

    A repair job is validated (one supported provider) and offered only to a worker serving that
    provider; other workers see it listed in ``unauthorized`` and it stays claimable for a match.
    With ``invalid`` a job whose provider record is invalid is listed there with its cause and skipped,
    so it never stops the selection of other PRs; without it the error is raised.
    """
    for candidate in sorted(candidates, key=lambda item: item.get("number", 0)):
        if only_prs is not None and candidate.get("number") not in only_prs:
            continue
        job = build_job(candidate)
        if job and job["kind"] in kinds and (eligible is None or eligible(job)) and is_claimable(
                job, claims_by_pr.get(job["number"], []), now=now,
                trusted_apps=trusted_apps, trusted_writers=trusted_writers):
            if job["kind"] in WRITE_KINDS:
                if executor_provider is None:
                    raise WorkerError("--provider is required for repair kinds")
                try:
                    providers = job_providers(job)
                    authorized_repair_providers(candidate.get("route"), providers, job.get("reoffer"),
                                                f"PR #{job['number']} {job['kind']} job",
                                                switched=(candidate.get("provider_switch") or {}).get("repair"))
                except WorkerError as exc:
                    if invalid is None:
                        raise
                    invalid.append({"number": job["number"], "kind": job["kind"], "error": str(exc)[:POSTED_OUTCOME_LIMIT]})
                    continue
                if providers[0] != executor_provider:
                    if unauthorized is not None:
                        unauthorized.append({"number": job["number"], "kind": job["kind"], "required_provider": providers[0]})
                    continue
            return job
    return None


def work_next(kinds: frozenset[str], *, list_prs: Callable[[], list[dict]],
              comments_for: Callable[[int], list[dict]], post_comment: Callable[[int, str], None],
              worker: str, ttl_seconds: int = 1800, dry_run: bool = False, now: datetime | None = None,
              current_head: Callable[[int], str] | None = None, provider: str | None = None,
              trusted_apps=frozenset(), trusted_writers=frozenset(),
              only_prs: frozenset[int] | None = None, eligible: Callable[[dict], bool] | None = None) -> dict:
    """Select, claim, re-read and confirm one job; abandon if another worker won.

    A PR whose record, comments or provider record cannot be read is skipped and listed under
    ``skipped`` so it never stops the other PRs; when nothing else is claimable the run fails naming them.
    """
    unknown = kinds - JOB_KINDS
    if unknown:
        raise WorkerError(f"unknown job kinds: {sorted(unknown)}")
    current = _now(now)

    def writers(comments: list[dict]) -> frozenset[str]:
        # ``trusted_writers`` may resolve proven writers per comment set (repository permission API).
        return frozenset(trusted_writers(comments)) if callable(trusted_writers) else frozenset(trusted_writers)

    candidates, claims, all_writers = [], {}, set()
    skipped: list[dict] = []
    for pr in list_prs():
        if only_prs is not None and pr["number"] not in only_prs:
            continue
        try:
            comments = comments_for(pr["number"])
            proven = writers(comments)
            candidate = derive_candidate(pr, comments, trusted_apps=trusted_apps, trusted_writers=proven)
        except GithubReadCacheError:
            raise  # a corrupt read cache is not one PR's unreadable record: it fails the run, naming the file
        except Exception as exc:  # one PR's unreadable record or comments never stops the other PRs
            skipped.append({"number": pr["number"], "error": f"{type(exc).__name__}: {exc}"[:POSTED_OUTCOME_LIMIT]})
            continue
        claims[pr["number"]] = comments
        all_writers |= proven
        candidates.append(candidate)
    trust = dict(now=current, trusted_apps=trusted_apps, trusted_writers=frozenset(all_writers))
    unauthorized: list[dict] = []
    skipped_jobs: list[dict] = []
    job = select_job(candidates, kinds, claims, only_prs=only_prs, eligible=eligible,
                     executor_provider=provider, unauthorized=unauthorized, invalid=skipped_jobs, **trust)
    skipped += skipped_jobs
    report = {**({"unauthorized": unauthorized} if unauthorized else {}), **({"skipped": skipped} if skipped else {})}
    if job is None:
        if skipped:
            # Nothing else was claimable: the anomalies themselves are the explicit failure of this run.
            raise WorkerError("no job claimed; skipped " + "; ".join(f"PR #{item['number']}: {item['error']}" for item in skipped))
        return {"status": "idle", "job": None, **report}
    if dry_run:
        return {"status": "dry-run", "job": job, **report}
    expires = datetime.fromtimestamp(current.timestamp() + ttl_seconds, timezone.utc).isoformat().replace("+00:00", "Z")
    post_comment(job["number"], claim_body(job, worker, expires, provider if job["kind"] in WRITE_KINDS else None))
    reread = comments_for(job["number"])
    trust["trusted_writers"] = frozenset(all_writers) | writers(reread)
    if not i_won(job, worker, reread, **trust):
        return {"status": "lost", "job": job, **report}
    if current_head is not None and current_head(job["number"]) != job["head"]:
        return {"status": "stale", "job": job, **report}  # head moved after the claim: abandon, re-evaluated next run
    return {"status": "claimed", "job": job, "expires_at": expires, **report}


def result_body(job: dict, worker: str, outcome: str, pushed_head: str | None = None, *, task_identity=None,
                provider: str | None = None) -> str:
    record = {"job": job_id(job), "worker": validate_worker_identity(worker), "head": job["head"], "outcome": outcome,
              "pushed_head": pushed_head}
    if provider is not None:
        record["provider"] = provider
    if task_identity is not None:
        record["task_identity"] = task_identity
    return RESULT_PREFIX + json.dumps(record, sort_keys=True, separators=(",", ":"))


def harness_git(repo: Path, *args: str) -> str:
    """Harness git for a harness-owned repository, with no credential and no operator git config.

    Every git command that runs after a writer or reviewer touched a checkout uses this (and only
    on a harness-owned clone), so configuration planted in the writer's checkout is never consulted.
    Ambient author/committer variables are dropped so a harness commit carries ``HARNESS_IDENTITY`` only.
    """
    env = {key: value for key, value in credential_free_env(dict(os.environ), repo.parent / "harness-home").items()
           if key not in {"GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
                          "CLAUDE_CODE_OAUTH_TOKEN"}}
    done = subprocess.run(["git", *SAFE_GIT, *args], cwd=repo, text=True, capture_output=True, check=False,
                          stdin=subprocess.DEVNULL, env=env)
    if done.returncode:
        raise WorkerError(f"git {' '.join(args)} failed: {done.stderr.strip() or done.stdout.strip()}")
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


def commit_writer_worktree(stage: Path, checkout: Path, expected_head: str, result_head: str, allowed_paths,
                           message: str) -> str:
    """The writer's result head, committing edits it left uncommitted (a sandbox may keep ``.git`` read-only).

    The writer checkout stays data only: its files are imported into a harness-owned staging clone at the
    writer's HEAD and git runs only there, so planted config, attributes drivers and hooks never execute. Every
    changed path must pass the write rules before anything is staged. A writer either commits its result
    or leaves it in the working tree, never both: edits left beside its own commit are rejected
    explicitly rather than pushed without them.
    """
    harness_git(stage, "checkout", "-q", "--detach", result_head)
    with (stage / ".git" / "info" / "exclude").open("a", encoding="utf-8") as handle:
        handle.write("".join(f"\n/{name}" for name in INSTALLED_FILES) + "\n")
    import_worktree(checkout, stage)
    changed = worktree_changes(stage)
    if not changed:
        return result_head
    if result_head != expected_head:
        raise _refusal("writer committed and also left uncommitted changes", changed)
    refuse_write_paths(changed, allowed_paths)
    harness_git(stage, "--literal-pathspecs", "add", "--", *changed)
    harness_git(stage, *HARNESS_IDENTITY, "commit", "-q", "--no-verify", "-m", message)
    return harness_git(stage, "rev-parse", "HEAD").strip()


def execute_job(job: dict, *, source_repo: str, branch: str, allowed_paths, llm_command,
                current_head: Callable[[], str], post_result: Callable[[str], None], workdir: str,
                worker: str, kind: str | None = None, provider: str | None = None,
                runner: Callable[..., Any] = run_in_session, env: dict[str, str] | None = None,
                push_env: dict[str, str] | None = None, home_files: list[str] | tuple[str, ...] = (),
                review_handler: Callable[[Path], dict] | None = None,
                before_push: Callable[[Path, str], None] | None = None,
                claim_current: Callable[[], bool] = lambda: True,
                runtime_check: Callable[[], str | None] | None = None,
                launch: Callable[..., Any] | None = None) -> dict:
    """Run one claimed job. The LLM only ever touches its own disposable checkout.

    Validation and the only push happen in a separate harness-owned clone that
    receives nothing but the result commit, so hooks, remotes and credential
    settings planted in the LLM checkout are never consulted. A write job's task
    is the final argv element of ``llm_command``; the writer either commits or
    leaves its edits in the working tree for the harness to commit.
    """
    kind = kind or job["kind"]
    if kind != job["kind"] or kind not in WRITE_KINDS | {"review"}:
        raise WorkerError(f"no executor for {kind} jobs")
    if kind in WRITE_KINDS:
        require_job_provider(job, provider)
    result_provider = provider if kind in WRITE_KINDS else None
    command = shlex.split(llm_command) if isinstance(llm_command, str) else list(llm_command)
    if kind in WRITE_KINDS and (not command or not str(command[-1]).strip()):
        raise WorkerError(f"PR #{job['number']} {kind} job has an empty writer task: the final llm command argument is blank")
    root = Path(workdir).resolve()
    checkout = prepare_checkout(source_repo, str(root), "llm-checkout", job["head"])

    writer_output: dict[str, str] = {}

    def finish(outcome: str, pushed: str | None = None, status: str | None = None) -> dict:
        if not claim_current():
            return {"status": "discarded"}
        outcome = outcome[:POSTED_OUTCOME_LIMIT]  # posted publicly, also through red-gate evidence
        post_result(result_body(job, worker, outcome, pushed, provider=result_provider))
        status = status or outcome.split(":")[0]
        # Writer output stays local (operator console, not the posted record): it may hold sensitive text.
        local = {"writer_output": dict(writer_output)} if writer_output and status in {
            "failed", "no-change", "rejected", "unavailable"} else {}
        return {"status": status, "outcome": outcome, "pushed_head": pushed, **local}

    if kind == "review" and review_handler is not None:
        outcome = review_handler(checkout)
        if outcome["status"] == "discarded" or not claim_current():
            return {"status": "discarded"}
        post_result(result_body(job, worker, outcome["status"], outcome.get("pushed_head"), provider=result_provider))
        return outcome
    before = (_git(checkout, "rev-parse", "HEAD").strip(), tree_snapshot(checkout))
    try:
        done = (launch or run_llm)(command, checkout, tmp=writer_tmp(root), env=env, runner=runner,
                                   home=scratch_home(root, home_files))
    except OSError as exc:
        if kind != "repair" or runtime_check is None:
            raise  # only the repair gate handles an unavailable runtime
        return finish(f"unavailable: cannot start the llm command: {exc}"[:300], status="unavailable")
    writer_output.update(stdout=done.stdout[-WRITER_OUTPUT_TAIL:], stderr=done.stderr[-WRITER_OUTPUT_TAIL:])
    if done.returncode:
        # A runtime that no longer passes its readiness probe (login, usage limit) is unavailable, not a failed result.
        limitation = runtime_check() if runtime_check is not None else None
        if limitation:
            return finish(f"unavailable: {limitation}"[:300], status="unavailable")
        return finish("failed: llm exited %s" % done.returncode, status="failed")
    try:
        after = tree_snapshot(checkout)
    except WorkerError as exc:
        verdict = "failed" if kind == "review" else "rejected"
        return finish(f"{verdict}: {exc}", status=verdict)
    if kind == "review":
        if (harness_git(checkout, "rev-parse", "HEAD").strip(), after) != before:
            return finish("failed: review modified the checkout", status="failed")
        return finish("reviewed", status="reviewed")
    try:
        proposal = json.loads(done.stdout or "null")
    except (ValueError, AttributeError):
        proposal = None
    if isinstance(proposal, dict) and proposal.get("reject_material") is True:
        return finish("proposed-rejection", status="proposed-rejection")
    result_head = harness_git(checkout, "rev-parse", "HEAD").strip()
    if result_head == job["head"] and after == before[1]:
        return finish("no-change", status="no-change")
    if current_head() != job["head"]:
        return finish("discarded: head moved", status="discarded")
    try:
        # The writer's commits and files pass through a staging clone; the harness clone then receives
        # nothing but the (possibly harness-committed) result commit, exactly as for a writer commit.
        stage = prepare_harness(source_repo, checkout, root, result_head, name="writer-stage")
        result_head = commit_writer_worktree(stage, checkout, job["head"], result_head, allowed_paths,
                                             f"Apply {kind} writer edits for {job_id(job)}")
        harness = prepare_harness(source_repo, stage, root, result_head) if result_head != job["head"] else None
    except WorkerError as exc:
        return finish(f"rejected: {exc}", status="rejected")
    if harness is None:
        return finish("no-change", status="no-change")  # only ignored files changed
    try:
        validate_worker_result(harness, job["head"], result_head, allowed_paths, kind=kind)
        if before_push is not None:
            before_push(harness, result_head)
        if not claim_current():
            return {"status": "discarded"}
        push_validated(harness, branch, job["head"], result_head, runner=runner, env=push_env)
    except WorkerError as exc:
        return finish(f"rejected: {exc}", status="rejected")
    return finish("pushed", result_head, status="pushed")


def _decode_all(text: str) -> Any:
    """Decode one JSON value, or the concatenated arrays ``gh --paginate`` prints."""
    decoder, index, items, single = json.JSONDecoder(), 0, [], None
    text = text.strip()
    while index < len(text):
        value, index = decoder.raw_decode(text, index)
        while index < len(text) and text[index].isspace():
            index += 1
        if isinstance(value, list):
            items.extend(value)
        else:
            single = value
    return items if single is None and text else single


def _is_plain_api_read(args: tuple[str, ...]) -> bool:
    """``api [--paginate] <path>`` with no method, field or other flag: a pure GET the read cache can serve."""
    rest = list(args[1:]) if args[:1] == ("api",) else None
    if rest is None:
        return False
    if rest[:1] == ["--paginate"]:
        rest = rest[1:]
    return len(rest) == 1 and not rest[0].startswith("-")


def _gh_json(*args: str) -> Any:
    if _is_plain_api_read(args):  # unchanged reads are revalidated by ETag through the disposable read cache
        try:
            return read_cache.cached_gh_json(Path.cwd(), *args)
        except read_cache.GithubReadError as exc:
            raise WorkerError(str(exc)) from exc
    done = subprocess.run(["gh", *args], text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL)
    if done.returncode:
        raise WorkerError(done.stderr.strip() or "gh failed")
    return _decode_all(done.stdout or "null")


def _coordinator_trust(root: Path, repo: str | None = None) -> dict[str, Any]:
    """The coordinator's own trust model: its configured App and proven repository writers."""
    import publication_queue

    return {"trusted_apps": publication_queue.trusted_apps(root),
            # Claim authors need proven write permission too, not only record authors.
            # Permissions are proven against the repository the worker serves (--repo).
            "trusted_writers": lambda comments: publication_queue.trusted_writers(root, comments, (CLAIM_PREFIX,), repo=repo)}


MERGED_DISCOVERY_PAGE = 50


def candidate_prs(repo: str, *, include_merged: bool, gh_json: Callable[..., Any] | None = None) -> list[dict]:
    """The pull requests lifecycle workers consider: every open PR, plus the merged ones when asked.

    Post-merge obligations belong to recently merged candidates: one bounded page
    (``MERGED_DISCOVERY_PAGE``) of the most recently updated closed PRs. Older merges offer nothing
    from here. The read-only lifecycle overview uses this same function so it shows exactly the
    candidates workers can act on.
    """
    read = gh_json or _gh_json
    listed = read("api", "--paginate", f"repos/{repo}/pulls?state=open&per_page=100")
    if include_merged:
        closed = read("api", f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page={MERGED_DISCOVERY_PAGE}")
        listed = [*listed, *({**pr, "merged": True} for pr in closed if pr.get("merged_at"))]
    return listed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lifecycle worker contract")
    sub = parser.add_subparsers(dest="command", required=True)
    nxt = sub.add_parser("work-next")
    nxt.add_argument("--kinds", required=True)
    nxt.add_argument("--worker", help=f"worker identity (default: ${WORKER_ENV}, else generated host-pid-nonce)")
    nxt.add_argument("--provider", choices=("codex", "claude"),
                     help="provider of the executor behind --llm-command; required for repair kinds")
    nxt.add_argument("--repo", required=True, help="owner/repo")
    nxt.add_argument("--ttl", type=int, default=1800)
    nxt.add_argument("--dry-run", action="store_true")
    nxt.add_argument("--run", action="store_true", help="execute the claimed job")
    nxt.add_argument("--llm-command")
    nxt.add_argument("--writer", choices=WRITERS,
                     help="platform repair writer instead of --llm-command: claude-sandboxed runs Claude (R2) under the "
                          "BR-576 sandbox for repair and integration-repair")
    nxt.add_argument("--pr", type=int, action="append", help="select only jobs of this PR (repeatable)")
    nxt.add_argument("--providers", help="comma list of review providers this worker offers; each must pass a readiness probe")
    nxt.add_argument("--repair-provider", help="provider behind --llm-command; required to claim repair with --run or --providers")
    nxt.add_argument("--source", help="repository URL or absolute path (default: the GitHub repo)")
    nxt.add_argument("--branch", help="candidate branch (default: the PR head ref)")
    nxt.add_argument("--allow", action="append", default=[], help="path a write result may change (repeatable)")
    nxt.add_argument("--llm-home-file", action="append", default=[],
                     help="file under HOME the LLM CLI needs for its own login, e.g. .codex/auth.json (repeatable)")
    import hosted_workers

    hosted_workers.add_parsers(sub)
    args = parser.parse_args(argv)
    if args.command != "work-next":
        return hosted_workers.run_command(args, Path.cwd())
    repo = args.repo
    try:
        args.worker = resolve_worker_identity(args.worker, os.environ, hostname=socket.gethostname(),
                                              pid=os.getpid(), nonce=secrets.token_hex(6))
        if set(args.kinds.split(",")) & WRITE_KINDS and args.provider is None and args.writer is None:
            raise WorkerError("--provider is required for repair kinds (or --writer, which names its own provider)")
    except WorkerError as exc:
        print(f"lifecycle worker: {exc}", file=sys.stderr)
        return 2

    def list_prs() -> list[dict]:
        return candidate_prs(repo, include_merged=bool(set(args.kinds.split(",")) & (POST_MERGE_KINDS | {"contribution-integration"})))

    def comments_for(number: int) -> list[dict]:
        return _gh_json("api", "--paginate", f"repos/{repo}/issues/{number}/comments?per_page=100")

    def post_comment(number: int, body: str) -> None:
        _gh_json("api", f"repos/{repo}/issues/{number}/comments", "-f", f"body={body}")

    def pr_info(number: int) -> dict:
        return _gh_json("api", f"repos/{repo}/pulls/{number}")

    try:
        needs_writer = (set(args.kinds.split(",")) - {"review", "finalize", "integration-repair", MERGE_ONLY_KIND,
                                                       "contribution-integration"} - POST_MERGE_KINDS)
        kinds = set(args.kinds.split(","))
        writer_launch = None
        if args.writer is not None:
            if args.llm_command:
                raise WorkerError("--writer and --llm-command are exclusive: the platform writer builds its own command")
            if not kinds & WRITE_KINDS:
                raise WorkerError("--writer applies only to repair and integration-repair kinds")
            for option, value in (("--provider", args.provider), ("--repair-provider", args.repair_provider)):
                if value not in (None, "claude"):
                    raise WorkerError(f"--writer claude-sandboxed runs claude, but {option} names {value}")
            args.provider = "claude"
            if "repair" in kinds:
                args.repair_provider = "claude"
            args.llm_command, writer_launch = sandboxed_claude_writer(Path.cwd())
        if "repair" in kinds and (args.run or args.providers) and not args.repair_provider:
            raise WorkerError("claiming repair jobs with --run or --providers needs --repair-provider (the provider behind --llm-command)")
        if args.repair_provider and "repair" not in kinds:
            raise WorkerError("--repair-provider applies only when claiming repair jobs")
        if args.repair_provider and args.provider and args.repair_provider != args.provider:
            raise WorkerError(f"--repair-provider {args.repair_provider} disagrees with --provider {args.provider}; "
                              "both name the provider behind --llm-command")
        review_names = [name for name in (args.providers or "").split(",") if name]
        if args.providers is not None and not review_names:
            raise WorkerError("--providers needs at least one provider")
        if args.run and "integration-repair" in args.kinds.split(",") and not args.llm_command:
            raise WorkerError("--run needs --llm-command for integration repair")
        if args.run and needs_writer and (not args.llm_command or not (args.allow or writer_launch)):
            raise WorkerError("--run needs --llm-command and at least one --allow path")
        if args.run:
            import publication_queue

            publication_queue.use_default_friction_sink(Path.cwd(), worker=args.worker)
        readiness: dict[str, str | None] | None = None
        review_ready = repair_ready = None
        if review_names or args.repair_provider:
            with tempfile.TemporaryDirectory(prefix="lifecycle-preflight-") as scratch:
                readiness = provider_readiness(Path.cwd(), [*review_names, *([args.repair_provider] if args.repair_provider else [])],
                                               workdir=scratch, home_files=args.llm_home_file)
            if review_names:
                review_ready = frozenset(name for name in review_names if readiness[name] is None)
            if args.repair_provider:
                repair_ready = frozenset([args.repair_provider]) if readiness[args.repair_provider] is None else frozenset()
        backlog_configured = bool(read_platform_config(Path.cwd()).get("development_backlog", {}).get("repository"))
        result = work_next(frozenset(k for k in args.kinds.split(",") if k), list_prs=list_prs,
                           only_prs=frozenset(args.pr) if args.pr else None,
                           eligible=lambda job: job_eligible(job, review_ready=review_ready, repair_ready=repair_ready,
                                                             backlog_configured=backlog_configured),
                           comments_for=comments_for, post_comment=post_comment, worker=args.worker,
                           ttl_seconds=args.ttl, dry_run=args.dry_run, provider=args.provider,
                           current_head=lambda n: pr_info(n)["head"]["sha"],
                           **_coordinator_trust(Path.cwd(), repo))
        if args.run and result["status"] == "claimed":
            job = result["job"]
            # The platform writer is bounded by the candidate's own changed paths unless --allow narrows it.
            allowed = args.allow or (candidate_paths(repo, job["number"]) if writer_launch is not None else args.allow)
            try:
                with tempfile.TemporaryDirectory(prefix="lifecycle-worker-") as workdir:
                    if job["kind"] in {"review", "repair"} and isinstance(job["task_identity"], dict) and job["task_identity"].get("change"):
                        from pr_review_gate import run_claimed
                        import publication_queue

                        candidate = publication_queue.candidate_status(Path.cwd(), job["number"], repo=repo)
                        outcome = run_claimed(
                            Path.cwd(), repo, candidate, job, review_ready=review_ready,
                            repair_runtime_check=(lambda: provider_readiness(
                                Path.cwd(), [args.repair_provider], workdir=workdir, home_files=args.llm_home_file)[args.repair_provider])
                            if args.repair_provider else None,
                            source_repo=args.source or f"https://github.com/{repo}.git",
                            branch=args.branch or pr_info(job["number"])["head"]["ref"],
                            allowed_paths=allowed, llm_command=args.llm_command,
                            current_head=lambda: pr_info(job["number"])["head"]["sha"],
                            post_result=lambda body: post_comment(job["number"], body),
                            workdir=workdir, home_files=args.llm_home_file, worker=args.worker, provider=args.provider,
                            launch=writer_launch)
                    elif job["kind"] == "finalize" and isinstance(job["task_identity"], dict) and job["task_identity"].get("change"):
                        from post_review_finalization import run_claimed_finalize
                        import publication_queue

                        candidate = publication_queue.candidate_status(Path.cwd(), job["number"], repo=repo)
                        outcome = run_claimed_finalize(
                            Path.cwd(), repo, candidate, job,
                            source_repo=args.source or f"https://github.com/{repo}.git",
                            branch=args.branch or pr_info(job["number"])["head"]["ref"],
                            current_head=lambda: pr_info(job["number"])["head"]["sha"],
                            post_result=lambda body: post_comment(job["number"], body),
                            workdir=workdir, worker=args.worker)
                    elif job["kind"] == "contribution-integration":
                        from requirement_contributions import merge_reviewed_contribution
                        import publication_queue

                        candidate = publication_queue.candidate_status(Path.cwd(), job["number"], repo=repo)
                        def contribution_claim_current():
                            comments = comments_for(job["number"])
                            return i_won(job, args.worker, comments,
                                         trusted_apps=publication_queue.trusted_apps(Path.cwd()),
                                         trusted_writers=publication_queue.trusted_writers(
                                             Path.cwd(), comments, (CLAIM_PREFIX,), repo=repo))

                        outcome = merge_reviewed_contribution(Path.cwd(), repo, candidate,
                                                              source_repo=args.source, expected_target_head=job["target_head"],
                                                              claim_current=contribution_claim_current)
                        post_comment(job["number"], result_body(job, args.worker, outcome["state"]))
                    elif job["kind"] in {"integration-repair", MERGE_ONLY_KIND}:
                        from integration_contour import run_claimed_integration_repair
                        import publication_queue

                        candidate = publication_queue.candidate_status(Path.cwd(), job["number"], repo=repo)
                        merge_only = job["kind"] == MERGE_ONLY_KIND  # never handed a writer, provider or command
                        outcome = run_claimed_integration_repair(
                            Path.cwd(), repo, candidate, job,
                            source_repo=args.source or f"https://github.com/{repo}.git",
                            branch=args.branch or pr_info(job["number"])["head"]["ref"],
                            allowed_paths=allowed, llm_command=None if merge_only else args.llm_command,
                            current_head=lambda: pr_info(job["number"])["head"]["sha"],
                            post_result=lambda body: post_comment(job["number"], body),
                            workdir=workdir, home_files=args.llm_home_file, worker=args.worker,
                            provider=None if merge_only else args.provider, launch=None if merge_only else writer_launch)
                    elif (job["kind"] == "retrospective" and isinstance(job["task_identity"], dict) and job["task_identity"].get("kind") == "requirement-composition"
                          and job.get("phase") == "pre-merge" and not pr_info(job["number"]).get("merged")):
                        from requirement_composition import run_claimed_retrospective
                        import publication_queue

                        candidate = publication_queue.candidate_status(Path.cwd(), job["number"], repo=repo)
                        outcome = run_claimed_retrospective(
                            Path.cwd(), repo, candidate, job, source_repo=args.source or f"https://github.com/{repo}.git",
                            post_result=lambda body: post_comment(job["number"], body), worker=args.worker)
                    elif job["kind"] in POST_MERGE_KINDS:
                        from integration_contour import run_claimed_post_merge
                        import publication_queue

                        candidate = publication_queue.candidate_status(Path.cwd(), job["number"], repo=repo)
                        outcome = run_claimed_post_merge(
                            Path.cwd(), repo, candidate, job, branch=args.branch or pr_info(job["number"])["head"]["ref"],
                            post_result=lambda body: post_comment(job["number"], body), worker=args.worker)
                        try:
                            publication_queue.ensure_post_merge_attention(Path.cwd(), repo, job["number"])
                        except publication_queue.AttentionError as exc:
                            raise WorkerError(str(exc)) from exc
                    else:
                        if writer_launch is not None:
                            # The generic executor appends no task to the writer command: the platform writer runs
                            # only platform-briefed repair (findings) and integration repair (conflicts, red gate).
                            raise WorkerError(f"--writer cannot run PR #{job['number']} {job['kind']} job: it has no "
                                              "platform task brief")
                        outcome = execute_job(
                            job, source_repo=args.source or f"https://github.com/{repo}.git",
                            branch=args.branch or pr_info(job["number"])["head"]["ref"], allowed_paths=args.allow,
                            llm_command=args.llm_command, worker=args.worker, provider=args.provider, workdir=workdir,
                            home_files=args.llm_home_file,
                            current_head=lambda: pr_info(job["number"])["head"]["sha"],
                            post_result=lambda body: post_comment(job["number"], body))
            except Exception as exc:
                # A failed run releases its claim at once (counted per job) instead of holding it until expiry.
                trust = _coordinator_trust(Path.cwd(), repo)
                releases = release_claim(job, args.worker, exc, comments_for=comments_for, post_comment=post_comment, **trust)
                if releases is not None and releases >= MAX_RELEASES and job["kind"] not in POST_MERGE_KINDS:
                    import publication_queue

                    publication_queue._transition(
                        Path.cwd(), repo, job["number"], "blocked-escalation", job["head"], task_identity=job["task_identity"],
                        red_gate={"name": job["kind"], "evidence": {"cause": CLAIM_RELEASE_CAUSE,
                                                                "releases": releases, "last": f"{type(exc).__name__}: {exc}"[:POSTED_OUTCOME_LIMIT]}})
                raise
            result = {**result, "execution": outcome}
        if readiness is not None:
            result = {**result, "providers": {"ready": sorted(name for name, limitation in readiness.items() if limitation is None),
                                              "unavailable": {name: limitation for name, limitation in readiness.items() if limitation}}}
        result = {**result, "worker": args.worker}
    except (WorkerError, ValueError, GithubReadCacheError) as exc:
        print(f"lifecycle worker: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
