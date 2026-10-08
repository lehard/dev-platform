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
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from candidate_lifecycle import derive_candidate, trusted_marker_comment
import disposable_repository_sandbox

CLAIM_PREFIX = "dev-platform-lifecycle-claim:v1 "
JOB_KINDS = frozenset({"review", "repair", "integration-repair", "finalize", "retrospective",
                       "terminal-reconciliation", "cleanup", "contribution-integration"})
WRITE_KINDS = frozenset({"repair", "integration-repair"})
POST_MERGE_KINDS = frozenset({"retrospective", "terminal-reconciliation", "cleanup"})
STATE_KIND = {"review-pending": "review", "reviewing": "review", "repair-pending": "repair",
              "repairing": "repair", "finalize-pending": "finalize",
              "integration-repair-pending": "integration-repair",
              "contribution-integration-pending": "contribution-integration"}
HEAD = re.compile(r"[0-9a-f]{40}")
RESULT_PREFIX = "dev-platform-lifecycle-result:v1 "
# Hardening for every harness git invocation (never trust repo-local hooks or fsmonitor).
SAFE_GIT = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false")
# Harness merges and commits never depend on an ambient git identity (CI runners have none).
HARNESS_IDENTITY = ("-c", "user.name=Lifecycle harness", "-c", "user.email=lifecycle@localhost")
EVIDENCE_NAMES = ("verification.md", "automated-checks.json")
CREDENTIAL_VARS = frozenset({
    "GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN",
    "GIT_ASKPASS", "SSH_ASKPASS", "SSH_AUTH_SOCK", "GH_HOST_TOKEN", "GITHUB_PAT",
    "DEV_PLATFORM_COORDINATOR_APP_KEY", "GCM_CREDENTIAL_CACHE_OPTIONS",
    # An LLM CLI's own login token reaches only the provider's LLM environment, via ``llm_env``.
    "CLAUDE_CODE_OAUTH_TOKEN"})
# The only environment variable each provider's declared login token file may become, and the
# offline, model-free command whose exit status proves that provider's login.
LOGIN_TOKEN_ENV = {"claude": "CLAUDE_CODE_OAUTH_TOKEN"}
LOGIN_PROBES = {"claude": ("auth", "status"), "codex": ("login", "status")}
# Any GitHub-scoped variable (GH_*, GITHUB_*, *_GITHUB_TOKEN/API_KEY...) is dropped; the LLM
# provider's own key (e.g. ANTHROPIC_API_KEY) is not a repository credential and is kept.
_CREDENTIAL_PATTERN = re.compile(r"^(GH|GITHUB)_|(GH|GITHUB)\w*_(TOKEN|API_KEY)$|^(GIT|SSH)_ASKPASS$")


class WorkerError(RuntimeError):
    pass


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
    return f"pr{job['number']}:{job['kind']}:{job['head']}:a{job['attempt']}" + suffix + (":pre-merge" if job.get("phase") == "pre-merge" else "")


def job_record(kind: str, head: str, task_identity: str | dict, attempt: int, *, providers=None, target_head=None, phase=None) -> dict:
    """The explicit ``next_job`` a coordinator publishes in a handoff record."""
    if kind not in JOB_KINDS or not HEAD.fullmatch(str(head)) or type(attempt) is not int or attempt < 0:
        raise ValueError("invalid job record")
    if not isinstance(task_identity, (str, dict)) or not task_identity:
        raise ValueError("missing task identity")
    if kind == "contribution-integration" and not HEAD.fullmatch(str(target_head)):
        raise ValueError("contribution integration job requires exact target head")
    if phase is not None and (phase != "pre-merge" or kind != "retrospective"):
        raise ValueError("invalid job phase")
    return {"kind": kind, "head": head, "task_identity": task_identity, "attempt": attempt,
            **({"phase": phase} if phase else {}),
            **({"providers": list(providers)} if providers is not None else {}),
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
            **{key: explicit[key] for key in ("provider", "providers", "target_head", "phase") if key in explicit}}


def claim_body(job: dict, worker: str, expires_at: str) -> str:
    if job.get("kind") not in JOB_KINDS or not HEAD.fullmatch(str(job.get("head", ""))):
        raise ValueError("invalid job")
    if _parse_time(expires_at) is None:
        raise ValueError("invalid expiry")
    record = {"job": job_id(job), "worker": worker, "head": job["head"], "expires_at": expires_at}
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


def winning_claim(job: dict, comments: list[dict], *, now: datetime | None = None,
                  trusted_apps: frozenset[str] = frozenset(),
                  trusted_writers: frozenset[str] = frozenset()) -> dict | None:
    """Earliest valid, unexpired, trusted claim for this job and exact head."""
    current = _now(now)
    for row, record in _claims(job, comments, trusted_apps, trusted_writers):
        if _parse_time(record["expires_at"]) > current:
            return {**record, "comment_id": row.get("id")}
    return None


def job_completed(job: dict, comments: list[dict], *, trusted_apps=frozenset(), trusted_writers=frozenset()) -> bool:
    """Whether a trusted result was already recorded for this exact job (head and attempt).

    A completed job is not offered again after its claim expires; a new attempt or
    a new head is a different job. A discarded result (head moved) completes nothing.
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
                and not str(record.get("outcome", "")).startswith("discarded")):
            return True
    return False


def is_claimable(job: dict, comments: list[dict], **kwargs) -> bool:
    trust = {key: kwargs[key] for key in ("trusted_apps", "trusted_writers") if key in kwargs}
    return winning_claim(job, comments, **kwargs) is None and not job_completed(job, comments, **trust)


def i_won(job: dict, worker: str, comments: list[dict], **kwargs) -> bool:
    claim = winning_claim(job, comments, **kwargs)
    return claim is not None and claim["worker"] == worker


def result_is_current(job: dict, result_head: str, current_head: str) -> bool:
    """A result for any head other than the job's and the PR's current head is discarded."""
    return job["head"] == result_head == current_head


# ---- environment ----------------------------------------------------------

def credential_free_env(env: dict[str, str], home: Path | None = None) -> dict[str, str]:
    clean = {key: value for key, value in env.items()
             if key not in CREDENTIAL_VARS and not _CREDENTIAL_PATTERN.search(key)
             and not key.startswith("GIT_CONFIG_")}
    clean.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_GLOBAL=os.devnull,
                 GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    if home is not None:
        # A scratch home: the operator's ~/.config/gh, ~/.ssh and git config are absent.
        clean.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"),
                     XDG_CACHE_HOME=str(home / ".cache"), GH_CONFIG_DIR=str(home / ".config" / "gh-disabled"))
    return clean


def read_login_token(path_text: str) -> str:
    """Read a declared LLM login token file; every violation names the path and rule, never the content."""
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        raise WorkerError(f"LLM login token file {path_text!r} must be an absolute path")
    try:
        info = path.stat()
    except OSError as exc:
        raise WorkerError(f"LLM login token file {path} is not readable: {exc.strerror}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise WorkerError(f"LLM login token file {path} must be a regular file")
    if info.st_mode & 0o077:
        raise WorkerError(f"LLM login token file {path} must not be accessible by group or others (chmod 600)")
    for parent in path.resolve().parents:
        if (parent / ".git").exists():
            raise WorkerError(f"LLM login token file {path} must be outside any git checkout ({parent})")
    try:
        token = path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError as exc:
        raise WorkerError(f"LLM login token file {path} is not UTF-8 text") from exc
    if not token:
        raise WorkerError(f"LLM login token file {path} is empty")
    return token


def login_bindings(config: dict[str, Any]) -> dict[str, str]:
    """Validate ``[independent_review.login.<provider>] token_file`` entries: provider -> token file path."""
    login = config.get("login", {})
    if not isinstance(login, dict):
        raise WorkerError("[independent_review.login] must be a table of providers")
    bindings: dict[str, str] = {}
    for provider, entry in login.items():
        if provider not in LOGIN_TOKEN_ENV:
            raise WorkerError(f"[independent_review.login.{provider}] is not supported; "
                              f"use one of {', '.join(sorted(LOGIN_TOKEN_ENV))}")
        if not isinstance(entry, dict) or set(entry) != {"token_file"} or not isinstance(entry["token_file"], str) \
                or not entry["token_file"].strip():
            raise WorkerError(f"[independent_review.login.{provider}] must contain exactly one non-empty token_file")
        bindings[provider] = entry["token_file"].strip()
    return bindings


def llm_env(provider: str, config: dict[str, Any], home: Path, env: dict[str, str] | None = None) -> dict[str, str]:
    """The credential-free LLM environment plus ``provider``'s own declared login token, if any."""
    clean = credential_free_env(dict(os.environ if env is None else env), home)
    token_file = login_bindings(config).get(provider)
    if token_file is not None:
        clean[LOGIN_TOKEN_ENV[provider]] = read_login_token(token_file)
    return clean


def login_binding_hint(provider: str) -> str:
    """Name the explicit login bindings when a provider cannot authenticate."""
    return (f"bind a login with [independent_review.login.{provider}] token_file in the operator config, "
            "or pass --llm-home-file for a login file")


def check_login(provider: str, binary: str, config: dict[str, Any], home: Path, *, timeout: float,
                runner: Callable[..., Any] = subprocess.run) -> None:
    """Prove ``provider`` can log in inside the scratch HOME and environment the reviewer will use."""
    probe = LOGIN_PROBES.get(provider)
    if probe is None:
        raise WorkerError(f"no login probe exists for provider {provider!r}")
    hint = login_binding_hint(provider)
    try:
        done = runner([binary, *probe], cwd=home, env=llm_env(provider, config, home), stdin=subprocess.DEVNULL,
                      capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise WorkerError(f"{provider} login probe timed out after {timeout:g}s; {hint}; no review job was claimed") from exc
    except OSError as exc:
        raise WorkerError(f"{provider} login probe could not start ({exc}); {hint}; no review job was claimed") from exc
    if done.returncode:
        raise WorkerError(f"{provider} reviewer cannot log in inside the scratch HOME ({binary} {' '.join(probe)} "
                          f"exited {done.returncode}); {hint}; "
                          "no review job was claimed")


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


def run_llm(command: list[str], checkout: Path, *, env: dict[str, str] | None = None,
            runner: Callable[..., Any] = subprocess.run, timeout: int | None = None,
            home: Path | None = None) -> Any:
    """Run the LLM command in a checkout with no credential, a scratch home and no inherited stdin."""
    return runner(command, cwd=checkout, env=credential_free_env(dict(os.environ if env is None else env), home),
                  stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False, timeout=timeout)


def prepare_checkout(source: str, root: str, name: str, head: str) -> Path:
    """Disposable checkout detached at the exact head (local sources reuse the sandbox helper)."""
    if Path(source).is_absolute() and Path(source).is_dir():
        create = disposable_repository_sandbox.create
        path = create(source, root, name)
        with (path / ".git" / "info" / "exclude").open("a", encoding="utf-8") as handle:
            handle.write("\n.dev-platform-disposable-repository.json\n")  # sandbox marker is not candidate content
        steps = [["checkout", "--detach", head]]
    else:
        path = Path(root) / name
        steps = [["clone", "--no-local", "--no-checkout", source, str(path)], ["checkout", "--detach", head]]
    for step in steps:
        done = subprocess.run(["git", *SAFE_GIT, *step], cwd=path if path.exists() else root, text=True,
                              capture_output=True, check=False, stdin=subprocess.DEVNULL)
        if done.returncode:
            raise WorkerError(f"git {step[0]} failed for {head}: {done.stderr.strip()}")
    return path


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
    changed = [p for p in _git(repo, "diff", "--name-only", "--no-renames", "-z",
                               expected_head, result_head).split("\0") if p]
    for path in changed:
        reason = _forbidden(path)
        if reason:
            raise WorkerError(f"{reason}: {path}")
        if not _allowed(path, allowed_paths):
            raise WorkerError(f"path outside candidate scope: {path}")
    return changed


def push_command(branch: str, expected_head: str, result_head: str) -> list[str]:
    return ["git", *SAFE_GIT, "-c", "credential.useHttpPath=true", "push", "origin", f"{result_head}:refs/heads/{branch}",
            f"--force-with-lease=refs/heads/{branch}:{expected_head}"]


def harness_push_env(checkout: Path, env: dict[str, str] | None = None) -> dict[str, str]:
    """One push process only; no token in argv, config files or writer checkouts."""
    from urllib.parse import urlsplit

    result = dict(os.environ if env is None else env)
    for token_variable in LOGIN_TOKEN_ENV.values():
        result.pop(token_variable, None)
    origin = harness_git(checkout, "remote", "get-url", "--push", "origin").strip()
    parsed = urlsplit(origin)
    if not origin:
        raise WorkerError("harness push origin is missing")
    if parsed.scheme == "file" or (not parsed.scheme and (checkout / origin).is_dir()):
        return result  # local harness repositories do not require hosted credentials
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username or parsed.password:
        raise WorkerError("harness push requires an uncredentialed GitHub HTTPS origin")
    token = result.get("GH_TOKEN")
    if not isinstance(token, str) or not token.strip():
        raise WorkerError("harness GitHub push requires coordinator GH_TOKEN")
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
    push_env = harness_push_env(repo) if env is None else env
    if any(variable in push_env for variable in LOGIN_TOKEN_ENV.values()):
        push_env = {key: value for key, value in push_env.items() if key not in LOGIN_TOKEN_ENV.values()}
    done = runner(push_command(branch, expected_head, result_head), cwd=repo,
                  env=push_env,
                  stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    if done.returncode:
        raise WorkerError(f"push rejected (git push exited {done.returncode})")
    return done


# ---- work-next ------------------------------------------------------------

def select_job(candidates: list[dict], kinds: frozenset[str], claims_by_pr: dict[int, list[dict]], *,
               now: datetime | None = None, trusted_apps=frozenset(), trusted_writers=frozenset()) -> dict | None:
    for candidate in sorted(candidates, key=lambda item: item.get("number", 0)):
        job = build_job(candidate)
        if job and job["kind"] in kinds and is_claimable(
                job, claims_by_pr.get(job["number"], []), now=now,
                trusted_apps=trusted_apps, trusted_writers=trusted_writers):
            return job
    return None


def work_next(kinds: frozenset[str], *, list_prs: Callable[[], list[dict]],
              comments_for: Callable[[int], list[dict]], post_comment: Callable[[int, str], None],
              worker: str, ttl_seconds: int = 1800, dry_run: bool = False, now: datetime | None = None,
              current_head: Callable[[int], str] | None = None,
              trusted_apps=frozenset(), trusted_writers=frozenset(),
              before_claim: Callable[[dict], None] | None = None) -> dict:
    """Select, claim, re-read and confirm one job; abandon if another worker won.

    ``before_claim`` runs once the job is selected and before anything is posted; an exception it
    raises propagates and leaves the job unclaimed.
    """
    unknown = kinds - JOB_KINDS
    if unknown:
        raise WorkerError(f"unknown job kinds: {sorted(unknown)}")
    current = _now(now)

    def writers(comments: list[dict]) -> frozenset[str]:
        # ``trusted_writers`` may resolve proven writers per comment set (repository permission API).
        return frozenset(trusted_writers(comments)) if callable(trusted_writers) else frozenset(trusted_writers)

    candidates, claims, all_writers = [], {}, set()
    for pr in list_prs():
        comments = comments_for(pr["number"])
        claims[pr["number"]] = comments
        proven = writers(comments)
        all_writers |= proven
        candidates.append(derive_candidate(pr, comments, trusted_apps=trusted_apps, trusted_writers=proven))
    trust = dict(now=current, trusted_apps=trusted_apps, trusted_writers=frozenset(all_writers))
    job = select_job(candidates, kinds, claims, **trust)
    if job is None:
        return {"status": "idle", "job": None}
    if dry_run:
        return {"status": "dry-run", "job": job}
    if before_claim is not None:
        before_claim(job)
    expires = datetime.fromtimestamp(current.timestamp() + ttl_seconds, timezone.utc).isoformat().replace("+00:00", "Z")
    post_comment(job["number"], claim_body(job, worker, expires))
    reread = comments_for(job["number"])
    trust["trusted_writers"] = frozenset(all_writers) | writers(reread)
    if not i_won(job, worker, reread, **trust):
        return {"status": "lost", "job": job}
    if current_head is not None and current_head(job["number"]) != job["head"]:
        return {"status": "stale", "job": job}  # head moved after the claim: abandon, re-evaluated next run
    return {"status": "claimed", "job": job, "expires_at": expires}


def result_body(job: dict, worker: str, outcome: str, pushed_head: str | None = None, *, task_identity=None) -> str:
    record = {"job": job_id(job), "worker": worker, "head": job["head"], "outcome": outcome,
              "pushed_head": pushed_head}
    if task_identity is not None:
        record["task_identity"] = task_identity
    return RESULT_PREFIX + json.dumps(record, sort_keys=True, separators=(",", ":"))


def harness_git(repo: Path, *args: str) -> str:
    """Harness git for a harness-owned repository, with no credential and no operator git config.

    Every git command that runs after a writer or reviewer touched a checkout uses this (and only
    on a harness-owned clone), so configuration planted in the writer's checkout is never consulted.
    """
    done = subprocess.run(["git", *SAFE_GIT, *args], cwd=repo, text=True, capture_output=True, check=False,
                          stdin=subprocess.DEVNULL, env=credential_free_env(dict(os.environ), repo.parent / "harness-home"))
    if done.returncode:
        raise WorkerError(f"git {' '.join(args)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def tree_snapshot(path: Path) -> str:
    """A content digest of a working tree read from the filesystem only (no git, no filters), excluding ``.git``."""
    import hashlib

    digest = hashlib.sha256()
    for directory, names, files in os.walk(path):
        names[:] = sorted(name for name in names if name != ".git")
        for name in sorted(files):
            target = Path(directory) / name
            digest.update(str(target.relative_to(path)).encode() + b"\0")
            if target.is_symlink():
                digest.update(b"L" + os.readlink(target).encode())
            else:
                digest.update(b"F" + str(target.stat().st_mode & 0o111).encode() + target.read_bytes())
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


def import_worktree(source: Path, target: Path) -> None:
    """Make ``target``'s working tree match ``source``'s files without running git in ``source``.

    Only file content, executable bits and symlinks are copied; ``.git`` of either side is never read
    or written, so a writer's repository configuration, attributes drivers or hooks cannot execute.
    Symlinks (to files or directories) are recreated as links and never followed on either side, so
    writer content cannot be redirected outside the harness clone.
    """
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


def prepare_harness(source_repo: str, checkout: Path, root: Path, result_head: str) -> Path:
    """Import only result commits into a separate trusted clone for validation/push."""
    harness = root / "harness"
    for step in (["clone", "--no-local", "--no-checkout", source_repo, str(harness)],
                 ["fetch", "--no-tags", str(checkout), result_head]):
        cwd = harness if step[0] == "fetch" else root
        proc = subprocess.run(["git", *SAFE_GIT, "-c", "protocol.file.allow=always", *step],
                              cwd=cwd, text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL)
        if proc.returncode:
            raise WorkerError(proc.stderr.strip()[:200])
    return harness


def execute_job(job: dict, *, source_repo: str, branch: str, allowed_paths, llm_command,
                current_head: Callable[[], str], post_result: Callable[[str], None], workdir: str,
                kind: str | None = None, worker: str = "worker",
                runner: Callable[..., Any] = subprocess.run, env: dict[str, str] | None = None,
                push_env: dict[str, str] | None = None, home_files: list[str] | tuple[str, ...] = (),
                review_handler: Callable[[Path], dict] | None = None,
                before_push: Callable[[Path, str], None] | None = None,
                claim_current: Callable[[], bool] = lambda: True) -> dict:
    """Run one claimed job. The LLM only ever touches its own disposable checkout.

    Validation and the only push happen in a separate harness-owned clone that
    receives nothing but the result commit, so hooks, remotes and credential
    settings planted in the LLM checkout are never consulted.
    """
    kind = kind or job["kind"]
    if kind != job["kind"] or kind not in WRITE_KINDS | {"review"}:
        raise WorkerError(f"no executor for {kind} jobs")
    command = shlex.split(llm_command) if isinstance(llm_command, str) else list(llm_command)
    root = Path(workdir).resolve()
    checkout = prepare_checkout(source_repo, str(root), "llm-checkout", job["head"])

    def finish(outcome: str, pushed: str | None = None, status: str | None = None) -> dict:
        if not claim_current():
            return {"status": "discarded"}
        post_result(result_body(job, worker, outcome, pushed))
        return {"status": status or outcome.split(":")[0], "outcome": outcome, "pushed_head": pushed}

    if kind == "review" and review_handler is not None:
        outcome = review_handler(checkout)
        if outcome["status"] == "discarded" or not claim_current():
            return {"status": "discarded"}
        post_result(result_body(job, worker, outcome["status"], outcome.get("pushed_head")))
        return outcome
    before = (_git(checkout, "rev-parse", "HEAD").strip(), tree_snapshot(checkout))
    done = run_llm(command, checkout, env=env, runner=runner, home=scratch_home(root, home_files))
    if done.returncode:
        return finish("failed: llm exited %s" % done.returncode, status="failed")
    if kind == "review":
        if (harness_git(checkout, "rev-parse", "HEAD").strip(), tree_snapshot(checkout)) != before:
            return finish("failed: review modified the checkout", status="failed")
        return finish("reviewed", status="reviewed")
    try:
        proposal = json.loads(done.stdout or "null")
    except (ValueError, AttributeError):
        proposal = None
    if isinstance(proposal, dict) and proposal.get("reject_material") is True:
        return finish("proposed-rejection", status="proposed-rejection")
    result_head = harness_git(checkout, "rev-parse", "HEAD").strip()
    if result_head == job["head"]:
        return finish("no-change", status="no-change")
    if current_head() != job["head"]:
        return finish("discarded: head moved", status="discarded")
    try:
        harness = prepare_harness(source_repo, checkout, root, result_head)
    except WorkerError as exc:
        return finish(f"rejected: {exc}", status="rejected")
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


def _gh_json(*args: str) -> Any:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lifecycle worker contract")
    sub = parser.add_subparsers(dest="command", required=True)
    nxt = sub.add_parser("work-next")
    nxt.add_argument("--kinds", required=True)
    nxt.add_argument("--worker", default=os.environ.get("DEV_PLATFORM_WORKER", f"worker-{os.getpid()}"))
    nxt.add_argument("--repo", required=True, help="owner/repo")
    nxt.add_argument("--ttl", type=int, default=1800)
    nxt.add_argument("--dry-run", action="store_true")
    nxt.add_argument("--run", action="store_true", help="execute the claimed job")
    nxt.add_argument("--llm-command")
    nxt.add_argument("--source", help="repository URL or absolute path (default: the GitHub repo)")
    nxt.add_argument("--branch", help="candidate branch (default: the PR head ref)")
    nxt.add_argument("--allow", action="append", default=[], help="path a write result may change (repeatable)")
    nxt.add_argument("--llm-home-file", action="append", default=[],
                     help="file under HOME the LLM CLI needs for its own login, e.g. .codex/auth.json (repeatable)")
    args = parser.parse_args(argv)
    repo = args.repo

    def list_prs() -> list[dict]:
        listed = _gh_json("api", "--paginate", f"repos/{repo}/pulls?state=open&per_page=100")
        if set(args.kinds.split(",")) & (POST_MERGE_KINDS | {"contribution-integration"}):
            # Post-merge obligations belong to recently merged candidates: one bounded page of the
            # most recently updated closed PRs. Older merges offer nothing from here.
            closed = _gh_json("api", f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=50")
            listed = [*listed, *({**pr, "merged": True} for pr in closed if pr.get("merged_at"))]
        return listed

    def comments_for(number: int) -> list[dict]:
        return _gh_json("api", "--paginate", f"repos/{repo}/issues/{number}/comments?per_page=100")

    def post_comment(number: int, body: str) -> None:
        _gh_json("api", f"repos/{repo}/issues/{number}/comments", "-f", f"body={body}")

    def pr_info(number: int) -> dict:
        return _gh_json("api", f"repos/{repo}/pulls/{number}")

    try:
        needs_writer = set(args.kinds.split(",")) - {"review", "finalize", "integration-repair", "contribution-integration"} - POST_MERGE_KINDS
        if args.run and "integration-repair" in args.kinds.split(",") and not args.llm_command:
            raise WorkerError("--run needs --llm-command for integration repair")
        if args.run and needs_writer and (not args.llm_command or not args.allow):
            raise WorkerError("--run needs --llm-command and at least one --allow path")
        if args.run:
            import publication_queue

            publication_queue.use_default_friction_sink(Path.cwd())
        def login_preflight(job: dict) -> None:
            """Review jobs only: every provider the job names must log in inside the reviewer's scratch HOME."""
            if job["kind"] != "review":
                return
            from independent_review_runner import preflight_timeout_seconds, resolve_binary, settings

            providers = job.get("providers") or ([job["provider"]] if job.get("provider") else [])
            if not providers:
                raise WorkerError(f"review job for PR #{job['number']} names no provider; no review job was claimed")
            config = settings(Path.cwd())
            with tempfile.TemporaryDirectory(prefix="lifecycle-login-") as probe_root:
                home = scratch_home(Path(probe_root), args.llm_home_file)
                for provider in providers:
                    binary, limitation = resolve_binary(provider)
                    if binary is None:
                        raise WorkerError(f"{provider} reviewer runtime is unavailable: {limitation}; {login_binding_hint(provider)}; no review job was claimed")
                    check_login(provider, binary, config, home, timeout=preflight_timeout_seconds(config))

        result = work_next(frozenset(k for k in args.kinds.split(",") if k), list_prs=list_prs,
                           before_claim=login_preflight if args.run else None,
                           comments_for=comments_for, post_comment=post_comment, worker=args.worker,
                           ttl_seconds=args.ttl, dry_run=args.dry_run,
                           current_head=lambda n: pr_info(n)["head"]["sha"],
                           **_coordinator_trust(Path.cwd(), repo))
        if args.run and result["status"] == "claimed":
            job = result["job"]
            with tempfile.TemporaryDirectory(prefix="lifecycle-worker-") as workdir:
                if job["kind"] in {"review", "repair"} and isinstance(job["task_identity"], dict) and job["task_identity"].get("change"):
                    from pr_review_gate import run_claimed
                    import publication_queue

                    candidate = publication_queue.candidate_status(Path.cwd(), job["number"], repo=repo)
                    outcome = run_claimed(
                        Path.cwd(), repo, candidate, job,
                        source_repo=args.source or f"https://github.com/{repo}.git",
                        branch=args.branch or pr_info(job["number"])["head"]["ref"],
                        allowed_paths=args.allow, llm_command=args.llm_command,
                        current_head=lambda: pr_info(job["number"])["head"]["sha"],
                        post_result=lambda body: post_comment(job["number"], body),
                        workdir=workdir, home_files=args.llm_home_file, worker=args.worker)
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
                elif job["kind"] == "integration-repair":
                    from integration_contour import run_claimed_integration_repair
                    import publication_queue

                    candidate = publication_queue.candidate_status(Path.cwd(), job["number"], repo=repo)
                    outcome = run_claimed_integration_repair(
                        Path.cwd(), repo, candidate, job,
                        source_repo=args.source or f"https://github.com/{repo}.git",
                        branch=args.branch or pr_info(job["number"])["head"]["ref"],
                        allowed_paths=args.allow, llm_command=args.llm_command,
                        current_head=lambda: pr_info(job["number"])["head"]["sha"],
                        post_result=lambda body: post_comment(job["number"], body),
                        workdir=workdir, home_files=args.llm_home_file, worker=args.worker)
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
                else:
                    outcome = execute_job(
                        job, source_repo=args.source or f"https://github.com/{repo}.git",
                        branch=args.branch or pr_info(job["number"])["head"]["ref"], allowed_paths=args.allow,
                        llm_command=args.llm_command, worker=args.worker, workdir=workdir, home_files=args.llm_home_file,
                        current_head=lambda: pr_info(job["number"])["head"]["sha"],
                        post_result=lambda body: post_comment(job["number"], body))
            result = {**result, "execution": outcome}
    except (WorkerError, ValueError) as exc:
        print(f"lifecycle worker: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
