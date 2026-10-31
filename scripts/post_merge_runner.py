#!/usr/bin/env python3
"""Scheduled operator-Mac runner for post-merge lifecycle work (BR-885).

One *round* repeats the existing ``lifecycle_workers.py work-next --run`` for the post-merge kinds
(retrospective, terminal-reconciliation, cleanup) until it reports ``idle`` or a bound is reached, so the
chain retro -> terminal -> cleanup catches up without a coordinator. The round duration bounds only when a run may start; a started
run is bounded by the claim TTL alone. A PR whose run ended blocked or failed is
excluded for the rest of the round, so each obligation is attempted at most once per round. The runner owns no queue, claim format
or job state: claims, results, the attempt limit and the attention on a spent obligation are the platform's.
It only schedules, bounds, guards the shared GitHub REST limit and writes a run journal.

Every missing or invalid input fails the round explicitly; nothing is defaulted or retried with another strategy.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import plistlib
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

KINDS = "retrospective,terminal-reconciliation,cleanup"
LABEL = "dev.platform.post-merge-runner"
START_INTERVAL_SECONDS = 600  # the Requirement fixes 10-15 minutes
JOURNAL_NAME = "post-merge-runs.jsonl"
LOCK_NAME = "post-merge-runner.lock"
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
ERROR_TAIL = 400
# A run that ends so leaves its obligation open; it is not attempted again in the same round.
RETRY_LATER = frozenset({"blocked", "failed"})
# Tools the post-merge jobs need on the runner's PATH (cleanup's active-process check).
REQUIRED_TOOLS = ("lsof",)


class RunnerError(RuntimeError):
    """A required input is missing or invalid, or a step failed; the message names it."""


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---- journal ----------------------------------------------------------------------------------------

def append_record(journal_dir: Path, record: dict[str, Any]) -> None:
    line = json.dumps({"at": _stamp(), **record}, sort_keys=True, ensure_ascii=False) + "\n"
    try:
        fd = os.open(journal_dir / JOURNAL_NAME, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line.encode())
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise RunnerError(f"run journal {journal_dir / JOURNAL_NAME} is not writable: {exc}") from exc


def read_records(journal_dir: Path) -> list[dict[str, Any]]:
    path = journal_dir / JOURNAL_NAME
    if not path.exists():
        return []
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RunnerError(f"run journal {path} line {number} is not valid JSON: {exc.msg}") from exc
        if not isinstance(item, dict):
            raise RunnerError(f"run journal {path} line {number} is not a JSON object")
        records.append(item)
    return records


def interrupted_round(records: list[dict[str, Any]]) -> str | None:
    """The id of the last round that started and never ended, if it is the most recent one."""
    started = [r["round"] for r in records if r.get("event") == "round-start"]
    ended = {r["round"] for r in records if r.get("event") == "round-end"}
    return started[-1] if started and started[-1] not in ended else None


# ---- external commands ------------------------------------------------------------------------------

def run_command(argv: list[str], *, env: dict[str, str], cwd: Path, timeout: float) -> subprocess.CompletedProcess:
    """Run in its own process group; on timeout kill exactly that group."""
    proc = subprocess.Popen(argv, cwd=cwd, env=env, text=True, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise RunnerError(f"{argv[1] if len(argv) > 1 else argv[0]} exceeded {timeout:.0f}s and was killed")
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


Runner = Callable[..., subprocess.CompletedProcess]


def github_token(gh: str, cwd: Path, run: Runner) -> str:
    done = run([gh, "auth", "token"], env=dict(os.environ), cwd=cwd, timeout=30)
    token = (done.stdout or "").strip()
    if done.returncode or not token:
        raise RunnerError(f"gh auth token failed: {(done.stderr or '').strip()[:ERROR_TAIL] or 'empty token'}")
    return token


def rest_remaining(gh: str, token: str, cwd: Path, run: Runner) -> tuple[int, int]:
    """``(remaining, reset_epoch)`` of the core REST limit; this endpoint is not charged."""
    done = run([gh, "api", "rate_limit"], env={**os.environ, "GH_TOKEN": token}, cwd=cwd, timeout=30)
    if done.returncode:
        raise RunnerError(f"gh api rate_limit failed: {(done.stderr or '').strip()[:ERROR_TAIL]}")
    try:
        core = json.loads(done.stdout)["resources"]["core"]
        return int(core["remaining"]), int(core["reset"])
    except (ValueError, KeyError, TypeError) as exc:
        raise RunnerError(f"gh api rate_limit returned an unreadable payload: {exc!r}") from exc


# ---- the round --------------------------------------------------------------------------------------

def validate(args: argparse.Namespace) -> None:
    if not REPO_RE.fullmatch(args.repo):
        raise RunnerError(f"--repo must be owner/repo, got {args.repo!r}")
    for name in ("checkout", "journal_dir"):
        if not getattr(args, name).is_absolute():
            raise RunnerError(f"--{name.replace('_', '-')} must be an absolute path, got {getattr(args, name)}")
    if not (args.checkout / "scripts/lifecycle_workers.py").is_file():
        raise RunnerError(f"--checkout {args.checkout} has no scripts/lifecycle_workers.py")
    if not args.journal_dir.is_dir():
        raise RunnerError(f"--journal-dir {args.journal_dir} does not exist")
    for name in ("min_rest_remaining", "max_jobs", "max_seconds", "claim_ttl"):
        if getattr(args, name) < 1:
            raise RunnerError(f"--{name.replace('_', '-')} must be a positive integer")
    if not shutil.which(args.gh) and not Path(args.gh).is_file():
        raise RunnerError(f"--gh {args.gh} is not an executable gh")


def require_tools(path: str | None) -> None:
    """Fail before any claim when a tool the jobs need does not resolve on the runner's PATH."""
    missing = [tool for tool in REQUIRED_TOOLS if not shutil.which(tool, path=path)]
    if missing:
        raise RunnerError(f"{', '.join(missing)} not found on PATH {path!r}; post-merge cleanup cannot check active "
                          "processes, so no job is claimed (fix the runner PATH)")


def run_round(args: argparse.Namespace, *, run: Runner = run_command, monotonic: Callable[[], float] = time.monotonic) -> int:
    validate(args)
    journal = args.journal_dir
    lock = None
    try:
        try:
            lock = open(journal / LOCK_NAME, "a")
        except OSError as exc:
            raise RunnerError(f"lock file {journal / LOCK_NAME} cannot be opened: {exc}") from exc
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            append_record(journal, {"event": "round-skipped", "reason": "previous round still running"})
            return 0
        return _locked_round(args, run, monotonic)
    finally:
        if lock is not None:
            lock.close()  # releases the single-instance lock


def _locked_round(args: argparse.Namespace, run: Runner, monotonic: Callable[[], float]) -> int:
    journal = args.journal_dir
    round_id = secrets.token_hex(4)
    previous = interrupted_round(read_records(journal))
    if previous:
        append_record(journal, {"event": "interrupted-previous-round", "round": round_id, "interrupted": previous})
    append_record(journal, {"event": "round-start", "round": round_id, "repo": args.repo})
    outcome, jobs, error = "idle", 0, None
    deferred: list[int] = []  # PRs whose obligation stays open until the next round
    try:
        require_tools(os.environ.get("PATH"))
        token = github_token(args.gh, args.checkout, run)
        deadline = monotonic() + args.max_seconds
        env = {**os.environ, "GH_TOKEN": token}
        while True:
            if jobs >= args.max_jobs:
                outcome = "max-jobs"
                break
            if monotonic() >= deadline:
                outcome = "max-seconds"
                break
            remaining, reset = rest_remaining(args.gh, token, args.checkout, run)
            if remaining < args.min_rest_remaining:
                outcome = "skipped-low-rest"
                append_record(journal, {"event": "rest-low", "round": round_id, "remaining": remaining,
                                        "threshold": args.min_rest_remaining, "reset": reset})
                break
            started = monotonic()
            if started >= deadline:
                outcome = "max-seconds"  # the rate-limit read used the last of the round's time
                break
            # The round budget only bounds when a run may start; a started run is bounded by its claim TTL alone,
            # so the budget never kills an action mid-way (the single-instance lock skips an overlapping round).
            done = run([sys.executable, "scripts/lifecycle_workers.py", "work-next", "--kinds", KINDS,
                        "--repo", args.repo, "--ttl", str(args.claim_ttl), "--run",
                        *[flag for number in deferred for flag in ("--exclude-pr", str(number))]],
                       env=env, cwd=args.checkout, timeout=args.claim_ttl)
            if done.returncode:
                raise RunnerError(f"work-next exited {done.returncode}: {(done.stderr or '').strip()[-ERROR_TAIL:]}")
            try:
                result = json.loads((done.stdout or "").strip().splitlines()[-1])
            except (IndexError, ValueError) as exc:
                raise RunnerError(f"work-next printed no JSON result: {(done.stdout or '')[-ERROR_TAIL:]!r}") from exc
            job = result.get("job") or {}
            execution = result.get("execution") or {}
            append_record(journal, {"event": "work-next", "round": round_id, "status": result.get("status"),
                                    "pr": job.get("number"), "kind": job.get("kind"),
                                    "result": execution.get("status"), "outcome": execution.get("outcome"),
                                    "rest_remaining": remaining, "seconds": round(monotonic() - started, 1)})
            if result.get("status") == "idle":
                outcome = "idle"
                break
            jobs += 1
            if execution.get("status") in RETRY_LATER and type(job.get("number")) is int:
                deferred.append(job["number"])
                append_record(journal, {"event": "deferred-to-next-round", "round": round_id, "pr": job["number"],
                                        "kind": job.get("kind"), "result": execution.get("status")})
    except RunnerError as exc:
        outcome, error = "failed", str(exc)
    append_record(journal, {"event": "round-end", "round": round_id, "outcome": outcome, "jobs": jobs,
                            **({"error": error} if error else {})})
    if error:
        print(f"post-merge runner: {error}", file=sys.stderr)
        return 1
    return 0


# ---- LaunchAgent ------------------------------------------------------------------------------------

def agent_path() -> Path:
    return Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"


def render_plist(args: argparse.Namespace) -> bytes:
    gh = shutil.which(args.gh) or (args.gh if Path(args.gh).is_file() else None)
    git = shutil.which("git")
    if not gh or not git:
        raise RunnerError("gh and git must be on PATH to render the LaunchAgent")
    arguments = [sys.executable, str(args.checkout / "scripts/post_merge_runner.py"), "run",
                 "--repo", args.repo, "--checkout", str(args.checkout), "--journal-dir", str(args.journal_dir),
                 "--gh", gh, "--min-rest-remaining", str(args.min_rest_remaining), "--max-jobs", str(args.max_jobs),
                 "--max-seconds", str(args.max_seconds), "--claim-ttl", str(args.claim_ttl)]
    path = ":".join(dict.fromkeys([str(Path(gh).parent), str(Path(git).parent), "/usr/bin", "/bin", "/usr/sbin", "/sbin"]))
    log = str(args.journal_dir / "launchd.log")
    return plistlib.dumps({"Label": LABEL, "ProgramArguments": arguments, "WorkingDirectory": str(args.checkout),
                           "EnvironmentVariables": {"PATH": path}, "RunAtLoad": True,
                           "StartInterval": START_INTERVAL_SECONDS, "StandardOutPath": log, "StandardErrorPath": log})


def _loaded() -> bool:
    return subprocess.run(["launchctl", "print", f"gui/{os.geteuid()}/{LABEL}"], capture_output=True).returncode == 0


def _bootout(destination: Path) -> None:
    if _loaded():
        done = subprocess.run(["launchctl", "bootout", f"gui/{os.geteuid()}", str(destination)], capture_output=True, text=True)
        if done.returncode:
            raise RunnerError(f"LaunchAgent unload failed, plist kept: {done.stderr.strip()}")


def install_agent(args: argparse.Namespace) -> None:
    if sys.platform != "darwin":
        raise RunnerError("LaunchAgent installation requires macOS")
    validate(args)
    content = render_plist(args)
    destination = agent_path()
    _bootout(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    destination.chmod(0o600)
    try:
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.geteuid()}", str(destination)], check=True,
                       capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RunnerError(f"launchctl bootstrap failed ({(exc.stderr or '').strip() or exc.returncode}); any previous agent "
                          f"is already unloaded and the new plist is at {destination}; fix the cause and rerun --install, "
                          "or remove-launchagent") from exc


def remove_agent() -> None:
    if sys.platform != "darwin":
        raise RunnerError("LaunchAgent removal requires macOS")
    destination = agent_path()
    _bootout(destination)
    if destination.exists():
        if destination.stat().st_uid != os.geteuid():
            raise RunnerError("foreign LaunchAgent owner")
        destination.unlink()


# ---- CLI --------------------------------------------------------------------------------------------

def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", required=True, help="owner/repo whose merged PRs are served")
    parser.add_argument("--checkout", required=True, type=Path, help="integration checkout that runs work-next")
    parser.add_argument("--journal-dir", required=True, type=Path, help="existing directory for the journal and lock")
    parser.add_argument("--gh", required=True, help="gh executable")
    parser.add_argument("--min-rest-remaining", required=True, type=int, help="skip when GitHub REST remaining is below")
    parser.add_argument("--max-jobs", required=True, type=int, help="work-next runs per round")
    parser.add_argument("--max-seconds", required=True, type=int, help="duration bound of a round")
    parser.add_argument("--claim-ttl", required=True, type=int, help="claim lifetime and per-run timeout, seconds")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scheduled post-merge lifecycle runner")
    sub = parser.add_subparsers(dest="command", required=True)
    _common(sub.add_parser("run", help="execute one bounded round"))
    agent = sub.add_parser("launchagent", help="render, install or remove the LaunchAgent")
    _common(agent)
    mode = agent.add_mutually_exclusive_group(required=True)
    for flag in ("print", "install"):
        mode.add_argument(f"--{flag}", action="store_true")
    sub.add_parser("remove-launchagent", help="unload and delete the LaunchAgent")
    show = sub.add_parser("journal", help="print the most recent journal records")
    show.add_argument("--journal-dir", required=True, type=Path)
    show.add_argument("--last", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "journal":
            for record in read_records(args.journal_dir)[-args.last:]:
                print(json.dumps(record, sort_keys=True, ensure_ascii=False))
            return 0
        if args.command == "run":
            return run_round(args)
        if args.command == "remove-launchagent":
            remove_agent()
        elif args.install:
            install_agent(args)
        else:
            validate(args)
            sys.stdout.write(render_plist(args).decode())
        return 0
    except RunnerError as exc:
        print(f"post-merge runner: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
