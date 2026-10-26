#!/usr/bin/env python3
"""GitHub-hosted placement of lifecycle workers: class table, plan, preflight and outcome report.

A hosted run executes the existing ``lifecycle_workers.py work-next --run`` contract; this module adds
only the placement rules around it. Every failure names the missing or contradictory input and never
substitutes another strategy, provider, token or placement.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

import lifecycle_workers as workers

ENABLE_ENV = "DEV_PLATFORM_HOSTED_KINDS"
PROVIDER = "claude"
PROVIDER_SECRET_ENV = "CLAUDE_CODE_OAUTH_TOKEN"
PROVIDER_FLAG_ENV = "PREFLIGHT_PROVIDER_SECRET_SET"
PHASES = ("inputs", "runtime", "all")

# One table drives the plan, the preflight and (through the structure tests) the workflow.
# Every class pushes to the candidate branch through the harness (review evidence, the finalization
# commit, the integration-merge commit), so each needs contents write next to pull-request comment rights.
# ``integrate`` runs the LLM-free integration merge: no provider, no writer, no --llm-command (BR-768).
CLASSES: dict[str, dict[str, Any]] = {
    "review": {"kinds": ("review",), "needs_provider": True, "tools": (),
               "permissions": {"contents": "write", "pull-requests": "write"}},
    "finalize": {"kinds": ("finalize",), "needs_provider": False, "tools": ("openspec",),
                 "permissions": {"contents": "write", "pull-requests": "write"}},
    "integrate": {"kinds": (workers.MERGE_ONLY_KIND,), "needs_provider": False, "tools": (),
                  "permissions": {"contents": "write", "pull-requests": "write"}},
}
HOSTED_KINDS = frozenset(kind for spec in CLASSES.values() for kind in spec["kinds"])

_WRITER = "no platform-supported hosted writer with proven containment exists (BR-576 owns the sandboxed writer contract)"
_LOCAL_STATE = ("it reads machine-local lifecycle state and Development Backlog Issues that a runner token cannot reach")
UNHOSTED: dict[str, str] = {
    "repair": _WRITER,
    "integration-repair": _WRITER,
    "retrospective": _LOCAL_STATE,
    "terminal-reconciliation": _LOCAL_STATE,
    "cleanup": _LOCAL_STATE,
}
_SECRET_SHAPES = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{10,}")
_RUN_NUMBER = re.compile(r"[1-9][0-9]*")


class HostedError(RuntimeError):
    """A hosted-run input is missing, unknown or refused; the message names it."""

    def __init__(self, message: str, name: str = "hosted-preflight"):
        super().__init__(message)
        self.name = name


def parse_kinds(raw: str | None) -> list[str]:
    """The enabled job kinds, validated; an unset or empty setting is a named error, never an empty list."""
    kinds = [item.strip() for item in (raw or "").split(",") if item.strip()]
    if not kinds:
        raise HostedError(f"{ENABLE_ENV} is required: set it to a comma list of hosted job kinds "
                          f"({', '.join(sorted(HOSTED_KINDS))})")
    for kind in kinds:
        if kind in UNHOSTED:
            raise HostedError(f"{ENABLE_ENV} names {kind!r}, which is not hosted: {UNHOSTED[kind]}; "
                              "it stays on the local operator node (BR-433)")
        if kind not in HOSTED_KINDS:
            raise HostedError(f"{ENABLE_ENV} names unknown job kind {kind!r}")
    return list(dict.fromkeys(kinds))


def class_kinds(name: str, enabled: list[str]) -> list[str]:
    if name not in CLASSES:
        raise HostedError(f"unknown hosted class {name!r}; use one of {', '.join(CLASSES)}")
    return [kind for kind in CLASSES[name]["kinds"] if kind in enabled]


def plan(raw: str | None) -> dict[str, list[dict[str, str]]]:
    """The class matrix for the enabled kinds: one entry per class that has an enabled kind."""
    enabled = parse_kinds(raw)
    return {"include": [{"class": name, "kinds": ",".join(class_kinds(name, enabled))}
                        for name in CLASSES if class_kinds(name, enabled)]}


def worker_identity(env: Mapping[str, str], name: str) -> str:
    """``gha-<run_id>-<run_attempt>-<class>``: unique per run attempt and class, valid for the worker contract."""
    parts = [env.get("GITHUB_RUN_ID", ""), env.get("GITHUB_RUN_ATTEMPT", "")]
    for label, value in zip(("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"), parts):
        if not _RUN_NUMBER.fullmatch(value):
            raise HostedError(f"{label} is missing or not a positive integer", label)
    if name not in CLASSES:
        raise HostedError(f"unknown hosted class {name!r}")
    try:
        return workers.validate_worker_identity(f"gha-{parts[0]}-{parts[1]}-{name}")
    except workers.WorkerError as exc:
        raise HostedError(str(exc)) from exc


def redact(text: str, env: Mapping[str, str]) -> str:
    """Remove secret values and token shapes from text that is about to be printed."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN", PROVIDER_SECRET_ENV):
        value = env.get(name, "")
        if value:
            text = text.replace(value, "***")
    return _SECRET_SHAPES.sub("***", text)


# ---- credential boundary ----------------------------------------------------------------------------

_CHILD_REPORT = (
    "import json, os, subprocess\n"
    "git = subprocess.run(['git', 'config', '--list'], capture_output=True, text=True, check=False)\n"
    "print(json.dumps({'env': sorted(os.environ), 'git': [line.split('=', 1)[0] for line in git.stdout.splitlines()],\n"
    "                  'gh_config': os.environ.get('GH_CONFIG_DIR', ''), 'home': os.environ.get('HOME', '')}))\n"
)
_GIT_CREDENTIAL_KEY = re.compile(r"^(credential\.|core\.askpass$|core\.sshcommand$|url\..*\.insteadof$|http\..*extraheader$)", re.I)
_ALLOWED_GIT_ENV = frozenset({"GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_NOSYSTEM", "GIT_TERMINAL_PROMPT"})


def credential_boundary_violations(report: Mapping[str, Any]) -> list[str]:
    """Fixed categories (never values) of credentials a credential-free child can still see."""
    from _platform_common import is_credential_name

    found: list[str] = []
    names = [name for name in report.get("env", []) if name not in _ALLOWED_GIT_ENV and name != "GH_CONFIG_DIR"]
    if any(is_credential_name(name) for name in names):
        found.append("github-environment-credential")
    if any(name == "SSH_AUTH_SOCK" or name.endswith("_ASKPASS") for name in report.get("env", [])):
        found.append("askpass-or-ssh-agent")
    if any(name.startswith("GIT_CONFIG_") and name not in _ALLOWED_GIT_ENV for name in report.get("env", [])):
        found.append("git-config-injection")
    if any(_GIT_CREDENTIAL_KEY.search(key) for key in report.get("git", [])):
        found.append("git-credential-configuration")
    gh_config = report.get("gh_config", "")
    if not gh_config or Path(gh_config).exists():
        found.append("gh-configuration")
    return found


def probe_credential_boundary(env: Mapping[str, str], scratch: Path,
                              runner: Callable[..., Any] = subprocess.run) -> list[str]:
    """Start a child through the same credential-free environment an LLM or check process gets and inspect it."""
    home = workers.scratch_home(scratch)
    clean = workers.credential_free_env(dict(env), home)
    try:
        done = runner([sys.executable, "-c", _CHILD_REPORT], env=clean, cwd=str(scratch), capture_output=True, text=True,
                      check=False, stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise HostedError(f"credential-boundary probe could not start a child ({type(exc).__name__})") from None
    if done.returncode:
        raise HostedError("credential-boundary probe child exited unsuccessfully")
    try:
        report = json.loads(done.stdout)
    except ValueError:
        raise HostedError("credential-boundary probe child printed an unreadable report") from None
    return credential_boundary_violations(report)


# ---- preflight ---------------------------------------------------------------------------------------

def _check(checks: list[dict[str, str]], name: str, detail: str) -> None:
    checks.append({"name": name, "status": "ok", "detail": detail})


def _fail(checks: list[dict[str, str]], name: str, detail: str, mode: str, phase: str) -> dict[str, Any]:
    checks.append({"name": name, "status": "failed", "detail": detail})
    return {"state": "error", "mode": mode, "phase": phase, "checks": checks,
            "reason": f"hosted preflight failed: {name}: {detail}"}


def preflight(root: Path, name: str, phase: str, env: Mapping[str, str], *, mode: str = "ci",
              queue=None, readiness: Callable[..., dict[str, str | None]] | None = None,
              probe: Callable[..., list[str]] | None = None,
              which: Callable[[str], str | None] | None = None) -> dict[str, Any]:
    """Prove the hosted class's inputs and runtime; stop at the first failed check and name it.

    ``queue`` is the publication queue module (its coordinator preflight proves App identity, trust and
    the installation-token scope); the other callables exist so tests can replace the probes.
    """
    if mode != "ci" or phase not in PHASES:
        raise HostedError("hosted preflight needs --mode ci and --phase inputs|runtime|all")
    if queue is None:
        import publication_queue as queue
    readiness = readiness or workers.provider_readiness
    probe = probe or probe_credential_boundary
    which = which or shutil.which
    checks: list[dict[str, str]] = []
    try:
        if name not in CLASSES:
            return _fail(checks, "class", f"unknown hosted class {name!r}; use one of {', '.join(CLASSES)}", mode, phase)
        _check(checks, "class", name)
        try:
            enabled = class_kinds(name, parse_kinds(env.get(ENABLE_ENV)))
        except HostedError as exc:
            return _fail(checks, ENABLE_ENV, str(exc), mode, phase)
        if not enabled:
            return _fail(checks, ENABLE_ENV, f"enables no kind of class {name!r}", mode, phase)
        _check(checks, ENABLE_ENV, f"enables {','.join(enabled)}")
        spec = CLASSES[name]
        if phase in ("inputs", "all"):
            if spec["needs_provider"]:
                if env.get(PROVIDER_FLAG_ENV) != "true":
                    return _fail(checks, PROVIDER_FLAG_ENV, "must be exactly 'true'; the provider secret behind it is not configured",
                                 mode, phase)
                _check(checks, PROVIDER_FLAG_ENV, "set")
            result = queue.preflight(root, mode, "inputs", env)
            checks.extend(result["checks"])
            if result["state"] != "ok":
                return {**result, "checks": checks, "phase": phase}
            identity = worker_identity(env, name)
            if env.get(workers.WORKER_ENV) != identity:
                return _fail(checks, workers.WORKER_ENV, f"must equal {identity}; the workflow and the preflight disagree on the worker identity",
                             mode, phase)
            _check(checks, "worker-identity", identity)
        if phase in ("runtime", "all"):
            for tool in spec["tools"]:
                if which(tool) is None:
                    return _fail(checks, f"tool:{tool}", "required executable is not available", mode, phase)
                _check(checks, f"tool:{tool}", "available")
            result = queue.preflight(root, mode, "runtime", env)
            checks.extend(result["checks"])
            if result["state"] != "ok":
                return {**result, "checks": checks, "phase": phase}
            with tempfile.TemporaryDirectory(prefix="hosted-preflight-") as scratch:
                leaks = probe(env, Path(scratch))
                if leaks:
                    return _fail(checks, "credential-boundary", "a credential-free child still sees: " + ", ".join(leaks), mode, phase)
                _check(checks, "credential-boundary", "a credential-free child sees no GitHub, App, askpass, SSH or credential-helper credential")
                if spec["needs_provider"]:
                    if not env.get(PROVIDER_SECRET_ENV):
                        return _fail(checks, PROVIDER_SECRET_ENV, "empty; the provider secret did not reach this step", mode, phase)
                    limitation = readiness(root, [PROVIDER], workdir=scratch)[PROVIDER]
                    if limitation:
                        return _fail(checks, f"{PROVIDER}-runtime", redact(limitation, env)[:300], mode, phase)
                    _check(checks, f"{PROVIDER}-runtime", "readiness probe passed in the scratch environment")
    except (HostedError, workers.WorkerError) as exc:
        return _fail(checks, getattr(exc, "name", "hosted-preflight"), redact(str(exc), env)[:300], mode, phase)
    return {"state": "ok", "mode": mode, "phase": phase, "class": name, "kinds": enabled, "checks": checks}


# ---- outcome report ----------------------------------------------------------------------------------

_FAILED_EXECUTION = frozenset({"blocked-retryable", "blocked-escalation", "failed", "unavailable", "rejected", "error"})
_RESULTED_EXECUTION = frozenset({"reviewed", "reused", "finalized", "returned-to-review", "changed", "integrated"})


def classify(result: Mapping[str, Any] | None, exit_code: int) -> tuple[str, bool, str]:
    """(outcome, failed, detail) of one ``work-next --run``. Nothing here asserts a candidate is done."""
    if exit_code:
        return "refused-or-failed", True, f"work-next exited {exit_code}; see the step log for the cause"
    if not isinstance(result, Mapping):
        return "refused-or-failed", True, "work-next printed no readable result"
    unavailable = (result.get("providers") or {}).get("unavailable") or {}
    if unavailable:
        causes = "; ".join(f"{name}: {limitation}" for name, limitation in sorted(unavailable.items()))
        return "provider-unavailable", True, causes[:300]
    status = result.get("status")
    execution = (result.get("execution") or {}).get("status")
    if status == "idle":
        return "idle", False, "no eligible job for this class"
    if status in ("lost", "stale"):
        return f"abandoned-{status}", False, "another worker won the claim or the head moved; the job is re-evaluated"
    if status == "claimed":
        if execution in _FAILED_EXECUTION:
            return f"job-{execution}", True, "the job is in its bounded retry or escalation state"
        if execution == "discarded":
            return "job-discarded", False, "the head or claim changed during the job; no result was published for it"
        if execution in _RESULTED_EXECUTION:
            return f"job-{execution}", False, "this run published its result; it does not assert the candidate is done"
        return "job-unknown", True, f"execution status {execution!r} is not a known hosted outcome"
    return "job-unknown", True, f"work-next status {status!r} is not a known hosted outcome"


def last_json_object(path: Path) -> Mapping[str, Any] | None:
    """The last JSON object line of a worker log (earlier lines are diagnostics), or ``None``."""
    if not path.is_file():
        return None
    for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if line.startswith("{"):
            try:
                value = json.loads(line)
            except ValueError:
                return None
            return value if isinstance(value, dict) else None
    return None


def summarize(result: Mapping[str, Any] | None, exit_code: int, name: str, worker: str) -> tuple[str, bool]:
    outcome, failed, detail = classify(result, exit_code)
    job = (result or {}).get("job") or {}
    lines = [f"### Hosted lifecycle worker: `{name}`", "",
             f"- worker: `{worker}`", f"- outcome: **{outcome}**" + (" (failed)" if failed else ""),
             f"- detail: {detail}"]
    if job:
        lines.append(f"- job: `{job.get('kind')}` on PR #{job.get('number')} at `{str(job.get('head'))[:12]}`")
    return "\n".join(lines) + "\n", failed


# ---- command line ------------------------------------------------------------------------------------

def add_parsers(sub: Any) -> None:
    plan_parser = sub.add_parser("hosted-plan", help="print the hosted class matrix for the enabling setting")
    plan_parser.add_argument("--kinds", default=None, help=f"comma list of kinds (the {ENABLE_ENV} setting, empty when unset)")
    pre = sub.add_parser("hosted-preflight", help="prove one hosted class's inputs and runtime before its worker runs")
    pre.add_argument("--mode", choices=("ci",), required=True)
    pre.add_argument("--class", dest="hosted_class", required=True)
    pre.add_argument("--phase", choices=PHASES, required=True)
    out = sub.add_parser("hosted-outcome", help="report one hosted work-next result and fail the run on a failed outcome")
    out.add_argument("--class", dest="hosted_class", required=True)
    out.add_argument("--result", help="file holding the work-next JSON result")
    out.add_argument("--exit-code", type=int, required=True)
    out.add_argument("--summary", help="file to append the markdown outcome to (GITHUB_STEP_SUMMARY)")


def run_command(args: Any, root: Path, env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    try:
        if args.command == "hosted-plan":
            print(json.dumps(plan(args.kinds if args.kinds is not None else env.get(ENABLE_ENV)), sort_keys=True))
            return 0
        if args.command == "hosted-preflight":
            result = preflight(root, args.hosted_class, args.phase, env, mode=args.mode)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["state"] == "ok" else 1
        if args.command == "hosted-outcome":
            result = last_json_object(Path(args.result)) if args.result else None
            text, failed = summarize(result, args.exit_code, args.hosted_class, worker_identity(env, args.hosted_class))
            print(text)
            if args.summary:
                with open(args.summary, "a", encoding="utf-8") as handle:
                    handle.write(text)
            return 1 if failed else 0
    except HostedError as exc:
        print(f"hosted lifecycle worker: {redact(str(exc), env)}", file=sys.stderr)
        return 2
    raise HostedError(f"unknown hosted command {args.command!r}")
