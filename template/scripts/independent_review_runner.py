"""Launch platform-observed independent review processes.

Each review perspective runs as a new, non-resumable provider process whose
runtime-enforced surface grants no repository write capability:

- Codex: ``codex exec --sandbox read-only --ephemeral``.
- Claude Code: headless print mode restricted to ``Read,Grep,Glob`` with
  session persistence disabled and no MCP servers.

The prompt is built only from the file-backed request, and the precomputed
candidate diff lives in a temporary directory outside the repository.
Prompts, stdout and stderr are never persisted; only the runtime's
structured usage counters are retained as a runtime-local ``runtime_usage``
block on an available report.  A content snapshot of the
task worktree and the integration checkout before and after every launch
proves the reviewer did not write; any mutation, launch failure, timeout or
malformed output yields an ``unavailable`` report with an actionable
limitation instead of findings.  The runner never repairs, cleans, publishes,
archives or records completion state.

Before any perspective launches, ``preflight`` proves the selected runtime is
usable on this host and account with the exact selected model through one
small probe with the same read-only flags; a failed probe records both
perspectives as unavailable without launching them.  No other model or
provider is ever tried.  The reviewer diff covers exactly the paths the review
task-content identity binds; lifecycle evidence is withheld from it.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from _platform_common import atomic_write_text, read_platform_config, run_git, utc_now
import independent_review as review


DEFAULT_TIMEOUT_SECONDS = 1800
DEFAULT_PREFLIGHT_TIMEOUT_SECONDS = 120
PREFLIGHT_PROMPT = (
    "Reviewer runtime readiness probe. Do not read files or use any tool. Reply with exactly the word READY."
)
DIFF_PATHSPEC_CHUNK = 200
DEFAULT_PROFILE = "standard"
PROVIDERS = ("codex", "claude")
CLAUDE_BIN_ENV = "DEV_PLATFORM_CLAUDE_BIN"
CLAUDE_READ_ONLY_TOOLS = "Read,Grep,Glob"
READ_ONLY_MECHANISMS = {
    "codex": "codex exec --sandbox read-only --ephemeral (no MCP servers)",
    "claude": f"claude -p --tools {CLAUDE_READ_ONLY_TOOLS} --permission-mode dontAsk --no-session-persistence --strict-mcp-config",
}
RUNTIMES = {"codex": "codex-exec", "claude": "claude-code-print"}
FINDINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["findings"],
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "severity", "summary", "evidence"],
                "properties": {
                    "id": {"type": "string"},
                    "severity": {"type": "string", "enum": ["material", "advisory"]},
                    "summary": {"type": "string"},
                    "evidence": {"type": "string"},
                },
            },
        }
    },
}


@dataclass(frozen=True)
class LaunchResult:
    returncode: int
    stdout: str


class LaunchUnavailable(Exception):
    """The reviewer process could not be started."""


class LaunchTimeout(Exception):
    """The reviewer process exceeded its bounded runtime."""


class ReviewOutputError(Exception):
    """The reviewer output does not match the findings contract."""


Launcher = Callable[[list[str], Path, float], LaunchResult]


def subprocess_launcher(argv: list[str], cwd: Path, timeout: float) -> LaunchResult:
    """Run a reviewer with no stdin; stderr is discarded, never persisted."""
    try:
        # A new session makes the reviewer its own process group, so a timeout
        # terminates every descendant before the read-only postcheck runs.
        process = subprocess.Popen(
            argv, cwd=cwd, text=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise LaunchUnavailable(f"reviewer binary cannot be executed: {argv[0]}") from exc
    except OSError as exc:
        raise LaunchUnavailable(f"reviewer could not start: {exc}") from exc
    try:
        stdout, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_process_group(process)
        raise LaunchTimeout(f"reviewer exceeded {int(timeout)}s") from exc
    finally:
        if process.poll() is None:
            _kill_process_group(process)
    # Descendants that outlived a normally exiting CLI must not write after the postcheck.
    _kill_process_group(process)
    return LaunchResult(process.returncode, stdout or "")


def _kill_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.communicate(timeout=10)
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass


def settings(root: Path) -> dict[str, Any]:
    value = read_platform_config(root).get("independent_review", {})
    return value if isinstance(value, dict) else {}


def _positive_seconds(config: dict[str, Any], key: str, default: int) -> float:
    value = config.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    return float(default)


def timeout_seconds(config: dict[str, Any]) -> float:
    return _positive_seconds(config, "timeout_seconds", DEFAULT_TIMEOUT_SECONDS)


def preflight_timeout_seconds(config: dict[str, Any]) -> float:
    return _positive_seconds(config, "preflight_timeout_seconds", DEFAULT_PREFLIGHT_TIMEOUT_SECONDS)


def resolve_provider(root: Path, config: dict[str, Any]) -> tuple[str | None, str]:
    """Return ``(provider, provenance-or-limitation)``.

    An explicit ``[independent_review] provider`` is the only way to review
    across providers; otherwise the current task route's provider is used.
    """
    configured = config.get("provider")
    if isinstance(configured, str) and configured.strip():
        provider = configured.strip()
        if provider not in PROVIDERS:
            return None, f"[independent_review] provider {provider!r} is not supported; use one of {', '.join(PROVIDERS)}"
        return provider, "configured"
    try:
        import model_routing

        route, _ = model_routing.read_current_durable_route(root)
    except Exception as exc:  # Any unknowable route is an actionable limitation, not a guess.
        return None, (
            f"the current task route provider is unknown ({exc}); record the route with "
            "scripts/dogfood_task.py route-codex/route-claude or set [independent_review] provider"
        )
    if route.provider not in PROVIDERS:
        return None, f"task route provider {route.provider!r} has no independent review adapter"
    return route.provider, "task-route"


def resolve_model(root: Path, provider: str, config: dict[str, Any]) -> str:
    import model_routing

    profile = config.get("profile") if isinstance(config.get("profile"), str) else DEFAULT_PROFILE
    if profile not in model_routing.PROFILES:
        raise review.IndependentReviewError(f"[independent_review] profile {profile!r} is not a model_routing profile")
    return model_routing._model_for(read_platform_config(root), provider, profile)


def resolve_binary(provider: str) -> tuple[str | None, str | None]:
    """Return ``(binary, limitation)`` for the provider CLI."""
    if provider == "claude":
        override = os.environ.get(CLAUDE_BIN_ENV, "").strip()
        if override:
            if os.path.isfile(override) and os.access(override, os.X_OK):
                return override, None
            return None, f"{CLAUDE_BIN_ENV}={override} is not an executable file; point it at the Claude Code CLI"
        found = shutil.which("claude")
        if found:
            return found, None
        return None, f"Claude Code CLI 'claude' is not on PATH; install it or set {CLAUDE_BIN_ENV} to its machine-local path"
    found = shutil.which("codex")
    if found:
        return found, None
    return None, "Codex CLI 'codex' is not on PATH; install it or set [independent_review] provider to an available provider"


def codex_argv(binary: str, worktree: Path, model: str, schema_path: Path, output_path: Path, prompt: str) -> list[str]:
    return [
        binary, "exec", "--sandbox", "read-only", "--ephemeral", "--cd", str(worktree), "--json",
        "-c", "mcp_servers={}", "--model", model, "--output-schema", str(schema_path),
        "--output-last-message", str(output_path), prompt,
    ]


def claude_argv(binary: str, model: str, schema: dict[str, Any], readable_dir: Path, prompt: str) -> list[str]:
    return [
        binary, "-p", "--tools", CLAUDE_READ_ONLY_TOOLS, "--permission-mode", "dontAsk",
        "--no-session-persistence", "--strict-mcp-config", "--add-dir", str(readable_dir),
        "--output-format", "json", "--json-schema", json.dumps(schema, separators=(",", ":")),
        "--model", model, prompt,
    ]


def probe_argv(provider: str, binary: str, worktree: Path, model: str) -> list[str]:
    """The readiness probe: the review adapter's read-only flags, exact model, no repository content."""
    if provider == "codex":
        return [
            binary, "exec", "--sandbox", "read-only", "--ephemeral", "--cd", str(worktree), "--json",
            "-c", "mcp_servers={}", "--model", model, PREFLIGHT_PROMPT,
        ]
    return [
        binary, "-p", "--tools", CLAUDE_READ_ONLY_TOOLS, "--permission-mode", "dontAsk",
        "--no-session-persistence", "--strict-mcp-config", "--output-format", "json",
        "--model", model, PREFLIGHT_PROMPT,
    ]


def _codex_thread_id(stdout: str) -> str | None:
    for line in stdout.splitlines():
        if not line.lstrip().startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "thread.started":
            value = event.get("thread_id")
            if isinstance(value, str) and value:
                return value
    return None


RUNTIME_ERROR_LIMIT = 200


def runtime_error(provider: str, stdout: str) -> str | None:
    """Extract the CLI's own bounded error message so a blocker is actionable.

    Only the runtime's structured error field is read (Claude's ``result`` on
    an error result, Codex's ``error``/``turn.failed`` event message); no
    prompt, transcript or repository text is retained.
    """
    candidates: list[dict[str, Any]] = []
    for line in stdout.splitlines() if provider == "codex" else [stdout]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            candidates.append(value)
    for event in candidates:
        message: Any = None
        if provider == "claude" and event.get("is_error") is True:
            message = event.get("result")
        elif provider == "codex" and event.get("type") in {"error", "turn.failed"}:
            error = event.get("error")
            message = event.get("message") or (error.get("message") if isinstance(error, dict) else error)
        if isinstance(message, str) and message.strip():
            return " ".join(message.split())[:RUNTIME_ERROR_LIMIT]
    return None


CLAUDE_USAGE_FIELDS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")
CLAUDE_RESULT_FIELDS = ("num_turns", "duration_ms", "duration_api_ms")
# Codex runtime field names; model_routing normalizes cached_input_tokens to cache_read_tokens.
CODEX_USAGE_FIELDS = {"input_tokens": "input_tokens", "cached_input_tokens": "cache_read_tokens", "output_tokens": "output_tokens"}


def _usage_measurement(value: Any) -> dict[str, Any]:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return {"value": value, "source": "runtime-confirmed", "status": "measured"}
    return {"value": None, "source": "unknown", "status": "unknown"}


def runtime_usage(provider: str, stdout: str) -> dict[str, Any]:
    """Retain the runtime-returned usage of one review launch, runtime-local.

    Only integer counters from the runtime's structured result are kept, under
    the runtime's own field names; Claude and Codex count cached input
    differently, so nothing is mapped onto a cross-runtime field.  Monetary
    fields are never retained, and an absent or malformed value is unknown.
    """
    fields: dict[str, dict[str, Any]] = {}
    if provider == "claude":
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None
        payload = payload if isinstance(payload, dict) else {}
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        fields.update({name: _usage_measurement(usage.get(name)) for name in CLAUDE_USAGE_FIELDS})
        fields.update({name: _usage_measurement(payload.get(name)) for name in CLAUDE_RESULT_FIELDS})
    elif provider == "codex":
        import model_routing

        events = [usage for line in stdout.splitlines() if (usage := model_routing._codex_usage_from_line(line)) is not None]
        # More than one completion may be incremental or cumulative: unknown, never summed.
        evidence = model_routing._codex_usage_evidence(events)
        fields.update({name: _usage_measurement((evidence.get(normalized) or {}).get("value"))
                       for name, normalized in CODEX_USAGE_FIELDS.items()})
    return {"runtime": RUNTIMES.get(provider, "unresolved"), "fields": fields}


def _launch_usage(provider: str, stdout: str) -> dict[str, Any]:
    """Usage retention is informational: a parse failure never makes a review unavailable."""
    try:
        return runtime_usage(provider, stdout)
    except Exception:
        return {"runtime": RUNTIMES.get(provider, "unresolved"), "fields": {}}


def parse_findings(raw: bytes) -> list[dict[str, str]]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewOutputError("reviewer output is not JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("findings"), list):
        raise ReviewOutputError("reviewer output must be an object with a findings list")
    findings: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(payload["findings"]):
        if not isinstance(item, dict):
            raise ReviewOutputError(f"finding {index + 1} is not an object")
        values = {key: item.get(key) for key in ("id", "severity", "summary", "evidence")}
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ReviewOutputError(f"finding {index + 1} lacks id, severity, summary or evidence")
        if values["severity"] not in review.FINDING_SEVERITIES:
            raise ReviewOutputError(f"finding {index + 1} severity must be material or advisory")
        if "disposition" in item:
            raise ReviewOutputError("a reviewer must not write finding dispositions")
        finding_id = values["id"].strip()
        if finding_id in seen:
            raise ReviewOutputError(f"duplicate finding id {finding_id!r}")
        seen.add(finding_id)
        findings.append({key: value.strip() for key, value in values.items()})
    return findings


def parse_claude_output(stdout: str) -> tuple[bytes, str | None]:
    """Return the raw structured output bytes and the session id."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ReviewOutputError("Claude Code output is not JSON") from exc
    if not isinstance(payload, dict):
        raise ReviewOutputError("Claude Code output is not a JSON object")
    if payload.get("is_error") is True:
        raise ReviewOutputError(f"Claude Code reported an error result ({payload.get('subtype', 'unknown')})")
    session = payload.get("session_id") if isinstance(payload.get("session_id"), str) and payload.get("session_id") else None
    structured = payload.get("structured_output")
    if isinstance(structured, dict):
        return json.dumps(structured, sort_keys=True, separators=(",", ":")).encode("utf-8"), session
    result = payload.get("result")
    if isinstance(result, str) and result.strip():
        return result.strip().encode("utf-8"), session
    raise ReviewOutputError("Claude Code output has no structured findings")


def build_prompt(request: dict[str, Any], perspective: str, diff_path: Path) -> str:
    """Build the reviewer prompt only from the request and the diff location."""
    inputs = request["perspectives"][perspective]
    candidate = request["candidate"]
    content = request.get("task_content") or {}
    paths = "\n".join(f"- {path}" for path in inputs.get("paths", [])) or "- (none)"
    excluded = request.get("excluded_lifecycle_paths")
    lifecycle = "\n".join(f"- {path}" for path in excluded) if isinstance(excluded, list) and excluded else "- (none)"
    return (
        f"You are an independent {perspective} reviewer for OpenSpec change {request.get('change')}.\n"
        "You are read-only: do not modify files, run commands that change state, publish, archive, or record completion.\n"
        f"Objective: {inputs['objective']}\n\n"
        f"Candidate: base {candidate['base_ref']} ({candidate['base_head']}), head {candidate['candidate_head']}, "
        f"task-content digest {content.get('digest', 'unknown')}.\n"
        f"The exact candidate diff is in {diff_path} (outside the repository). Read it first.\n"
        "Contract and guidance files, relative to the repository root (your working directory):\n"
        f"{paths}\n\n"
        "Lifecycle evidence paths (previous review request/reports/dispositions, automated checks, verification "
        "receipt, evidence, archive-derived spec materialization) are not part of the candidate and are omitted from "
        "the diff. Do not review them and do not report findings about them:\n"
        f"{lifecycle}\n\n"
        "Report only findings supported by concrete evidence (file and line, or quoted behavior). Use severity "
        "'material' only for defects that must block completion; use 'advisory' otherwise. Give each finding a short "
        "stable kebab-case id. Do not propose or record dispositions. Return JSON matching the provided schema; "
        "return an empty findings list when there is nothing to report."
    )


def _probe_failure(provider: str, stdout: str, returncode: int) -> str | None:
    """Why a completed probe proves the runtime is not ready, if it does."""
    cause = runtime_error(provider, stdout)
    if returncode != 0:
        return f"probe exited with status {returncode}" + (f" ({cause})" if cause else "")
    if cause:
        return f"probe returned an error ({cause})"
    if provider == "claude":
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return "probe output is not a Claude Code JSON result"
        if not isinstance(payload, dict):
            return "probe output is not a Claude Code JSON result"
        if payload.get("is_error") is True:
            return f"probe returned an error result ({payload.get('subtype', 'unknown')})"
    return None


def _next_step(provider: str) -> str:
    binary_hint = f", point {CLAUDE_BIN_ENV} at the Claude Code CLI" if provider == "claude" else ""
    return (
        f"next: log the {provider} CLI in on this host{binary_hint}, or change the [model_routing] / "
        "[independent_review] binding for this account (no other model or provider is tried), then rerun "
        + review.preflight_command()
    )


def preflight(
    root: Path, *, config: dict[str, Any] | None = None, launcher: Launcher | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Prove the selected reviewer runtime and exact model are usable; write nothing.

    Returns ``{ready, provider, provider_source, model, binary, limitation}``.
    The probe runs through the same launcher and read-only flags as a review
    perspective, under the same workspace mutation postcheck, and never
    switches to another model or provider.
    """
    root = root.resolve()
    config = settings(root) if config is None else config
    result: dict[str, Any] = {
        "ready": False, "provider": None, "provider_source": None, "model": None, "binary": None, "limitation": None,
    }

    def not_ready(limitation: str) -> dict[str, Any]:
        result["limitation"] = limitation
        return result

    provider, provenance = resolve_provider(root, config)
    if provider is None:
        return not_ready(provenance)
    result.update(provider=provider, provider_source=provenance)
    try:
        model = resolve_model(root, provider, config)
    except Exception as exc:
        return not_ready(
            f"reviewer model cannot be resolved from [model_routing]: {exc}; fix the [model_routing] / "
            "[independent_review] profile binding"
        )
    result["model"] = model
    binary, binary_limitation = resolve_binary(provider)
    if binary is None:
        return not_ready(f"{provider} reviewer runtime for model {model!r} is not ready: {binary_limitation}")
    result["binary"] = binary
    label = f"{provider} reviewer runtime with model {model!r}"
    wait = preflight_timeout_seconds(config) if timeout is None else timeout
    try:
        before = _snapshots(workspaces(root))
    except Exception as exc:
        return not_ready(f"cannot snapshot the workspace for the readiness probe postcheck: {exc}")
    try:
        outcome: Any = (launcher or subprocess_launcher)(probe_argv(provider, binary, root, model), root, wait)
    except LaunchTimeout as exc:
        outcome = f"readiness probe timed out ({exc}); rerun, or raise [independent_review] preflight_timeout_seconds"
    except LaunchUnavailable as exc:
        outcome = f"readiness probe could not start: {exc}"
    try:
        mutated = _mutations(before)
    except Exception as exc:
        return not_ready(f"cannot prove the readiness probe left the workspace unchanged: {exc}")
    if mutated:
        return not_ready(
            f"{label} mutated the workspace during the readiness probe; nothing was repaired: "
            + ", ".join(sorted(mutated)) + ". Inspect and restore these paths yourself, then rerun."
        )
    failure = outcome if isinstance(outcome, str) else _probe_failure(provider, outcome.stdout, outcome.returncode)
    if failure:
        return not_ready(f"{label} is not ready: {failure}; {_next_step(provider)}")
    result["ready"] = True
    return result


def integration_root(root: Path) -> Path:
    common = run_git(["rev-parse", "--git-common-dir"], cwd=root, check=False)
    if common.returncode or not common.stdout.strip():
        raise review.IndependentReviewError("cannot resolve the integration checkout for the read-only postcheck")
    path = Path(common.stdout.strip())
    if not path.is_absolute():
        path = (root / path).resolve()
    return path.parent.resolve()


def workspaces(root: Path) -> list[Path]:
    return list(dict.fromkeys([root.resolve(), integration_root(root)]))


def _snapshots(paths: list[Path]) -> dict[Path, Any]:
    from delegation_containment import snapshot

    return {path: snapshot(path) for path in paths}


def _mutations(before: dict[Path, Any]) -> list[str]:
    from delegation_containment import check_containment, snapshot

    mutated: list[str] = []
    for path, pre in before.items():
        result = check_containment(pre, snapshot(path))
        if result.violated:
            names = list(result.new_changes) + list(result.disappeared_changes)
            if result.head_moved:
                names.append("HEAD")
            mutated.extend(f"{path}:{name}" for name in names)
    return mutated


def dirty_candidate_paths(root: Path, change: Path, base_ref: str = "origin/main") -> list[str]:
    """Uncommitted task paths the committed task-content identity would not cover."""
    from task_content_identity import _canonical_path, review_exclusion

    name = review.canonical_change_name(change)
    status = run_git(["status", "--porcelain=v1", "--untracked-files=all"], cwd=root, check=False)
    if status.returncode:
        raise review.IndependentReviewError("cannot read task worktree status before independent review")
    exclude = review_exclusion(root, name, base_ref)
    dirty: list[str] = []
    for line in status.stdout.splitlines():
        raw = line[3:].split(" -> ")[-1].strip().strip('"')
        if raw and not exclude(_canonical_path(raw, name), raw):
            dirty.append(raw)
    return dirty


def _report(request: dict[str, Any], perspective: str, reviewer: dict[str, Any], *, launched_at: str,
            findings: list[dict[str, str]] | None = None, limitation: str | None = None,
            output_sha256: str | None = None, usage: dict[str, Any] | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": review.SCHEMA_VERSION,
        "perspective": perspective,
        "request_id": request["request_id"],
        "candidate": request["candidate"],
        "task_content_digest": (request.get("task_content") or {}).get("digest"),
        "reviewer": reviewer,
        "launched_at": launched_at,
        "completed_at": utc_now(),
    }
    if limitation is not None:
        report.update({"availability": "unavailable", "findings": [], "limitation": limitation})
    else:
        report.update({"availability": "available", "findings": findings or [], "output_sha256": output_sha256})
        if usage is not None:
            report["runtime_usage"] = usage
    return report


def run_perspective(
    root: Path, request: dict[str, Any], perspective: str, *, provider: str | None, model: str | None,
    binary: str | None, limitation: str | None, launcher: Launcher, timeout: float, scratch: Path, diff_path: Path,
    watched: list[Path],
) -> dict[str, Any]:
    launch_id = f"platform-launch-{uuid.uuid4()}"
    reviewer: dict[str, Any] = {
        "runtime": RUNTIMES.get(provider or "", "unresolved"),
        "provider": provider or "unknown",
        # Always unique per launch, so a disposition binds to one exact run
        # even when two runs return identical findings within one second.
        "launch_id": launch_id,
        "context_id": launch_id,
        "context_id_source": "platform-launch",
        "fresh_context": True,
        "write_access": False,
        "launch_evidence": review.PLATFORM_OBSERVED,
        "read_only_mechanism": READ_ONLY_MECHANISMS.get(provider or "", "none"),
        "model": {"value": model, "source": "selected"} if model else {"value": None, "source": "unknown"},
    }
    launched_at = utc_now()
    if limitation is not None or provider is None or binary is None or model is None:
        return _report(request, perspective, reviewer, launched_at=launched_at, limitation=limitation or "reviewer could not be resolved")
    prompt = build_prompt(request, perspective, diff_path)
    output_path = scratch / f"{perspective}-output.json"
    schema_path = scratch / "findings-schema.json"
    if provider == "codex":
        argv = codex_argv(binary, root, model, schema_path, output_path, prompt)
    else:
        argv = claude_argv(binary, model, FINDINGS_SCHEMA, scratch, prompt)
    try:
        before = _snapshots(watched)
    except Exception as exc:
        return _report(request, perspective, reviewer, launched_at=launched_at,
                       limitation=f"cannot snapshot the workspace for the read-only postcheck: {exc}")
    try:
        result = launcher(argv, root, timeout)
    except LaunchTimeout as exc:
        outcome: Any = f"{provider} reviewer timed out ({exc}); rerun, or raise [independent_review] timeout_seconds"
    except LaunchUnavailable as exc:
        outcome = f"{provider} reviewer is unavailable: {exc}"
    else:
        outcome = result
    try:
        mutated = _mutations(before)
    except Exception as exc:
        return _report(request, perspective, reviewer, launched_at=launched_at,
                       limitation=f"cannot prove the reviewer left the workspace unchanged: {exc}")
    if mutated:
        return _report(request, perspective, reviewer, launched_at=launched_at, limitation=(
            "reviewer mutated the workspace; evidence invalidated and nothing was repaired: " + ", ".join(sorted(mutated))
            + ". Inspect and restore these paths yourself, then rerun the review."
        ))
    if isinstance(outcome, str):
        return _report(request, perspective, reviewer, launched_at=launched_at, limitation=outcome)
    if outcome.returncode != 0:
        cause = runtime_error(provider, outcome.stdout)
        return _report(request, perspective, reviewer, launched_at=launched_at, limitation=(
            f"{provider} reviewer exited with status {outcome.returncode}"
            + (f" ({cause})" if cause else "")
            + "; check the CLI login and the [model_routing] model for this account, then rerun"
        ))
    try:
        if provider == "codex":
            if not output_path.is_file():
                raise ReviewOutputError("Codex reviewer produced no final structured message")
            raw = output_path.read_bytes()
            context = _codex_thread_id(outcome.stdout)
        else:
            raw, context = parse_claude_output(outcome.stdout)
        findings = parse_findings(raw)
    except ReviewOutputError as exc:
        return _report(request, perspective, reviewer, launched_at=launched_at,
                       limitation=f"{provider} reviewer returned malformed output: {exc}; rerun the review")
    if context:
        reviewer["context_id"] = context
        reviewer["context_id_source"] = "runtime"
    return _report(request, perspective, reviewer, launched_at=launched_at, findings=findings,
                   output_sha256=hashlib.sha256(raw).hexdigest(), usage=_launch_usage(provider, outcome.stdout))


def candidate_diff(root: Path, merge_base: str, paths: list[str]) -> tuple[str, str | None]:
    """Diff only the identity-bound paths as literal pathspecs; ``(text, error)``."""
    parts: list[str] = []
    for start in range(0, len(paths), DIFF_PATHSPEC_CHUNK):
        pathspecs = [f":(literal){path}" for path in paths[start:start + DIFF_PATHSPEC_CHUNK]]
        diff = run_git(["diff", "--no-ext-diff", "--no-renames", f"{merge_base}...HEAD", "--", *pathspecs], cwd=root, check=False)
        if diff.returncode:
            return "", "cannot calculate the candidate diff for the reviewer"
        parts.append(diff.stdout)
    return "".join(parts), None


def _current_request(root: Path, change: Path) -> dict[str, Any] | None:
    try:
        request = json.loads(review.request_path(change).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(request, dict) or review._validate_request(request) or not isinstance(request.get("task_content"), dict):
        return None
    return request if review.request_staleness(root, change, request) is None else None


def run_review(
    root: Path, change: Path, *, base_ref: str | None = None, launcher: Launcher | None = None,
) -> dict[str, dict[str, Any]]:
    """Prepare (or reuse a current) request and launch every perspective."""
    root = root.resolve()
    if not change.is_dir():
        raise review.IndependentReviewError(f"OpenSpec change not found: {change}")
    base_ref = base_ref or f"origin/{read_platform_config(root).get('main_branch', 'main')}"
    dirty = dirty_candidate_paths(root, change, base_ref)
    if dirty:
        raise review.IndependentReviewError(
            "commit the candidate before independent review; uncommitted task paths would not be bound to the evidence: "
            + ", ".join(sorted(dirty)[:20])
        )
    request = _current_request(root, change)
    if request is None or request["candidate"].get("base_ref") != base_ref:
        request = review.prepare_request(root, change, base_ref)
    config = settings(root)
    merge_base = request["task_content"]["base"]
    reviewed_paths: list[str] = []
    diff_limitation: str | None = None
    try:
        reviewed_paths, excluded = review.lifecycle_path_partition(root, change, request["candidate"]["base_ref"], merge_base)
    except review.IndependentReviewError as exc:
        diff_limitation = f"cannot calculate the candidate diff for the reviewer: {exc}"
    else:
        if request.get("excluded_lifecycle_paths") != excluded:
            # A reused request records the exclusions this run actually applied.
            request["excluded_lifecycle_paths"] = excluded
            atomic_write_text(review.request_path(change), json.dumps(request, indent=2, sort_keys=True) + "\n")
    # Runtime readiness is proven before any perspective launches.
    readiness = preflight(root, config=config, launcher=launcher)
    provider, model, binary = readiness["provider"], readiness["model"], readiness["binary"]
    limitation: str | None = None if readiness["ready"] else readiness["limitation"]
    watched = workspaces(root)
    reports: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="dev-platform-review-") as temporary:
        scratch = Path(temporary).resolve()
        (scratch / "findings-schema.json").write_text(json.dumps(FINDINGS_SCHEMA), encoding="utf-8")
        diff_path = scratch / "candidate.diff"
        diff, diff_error = candidate_diff(root, merge_base, reviewed_paths)
        limitation = limitation or diff_limitation or diff_error
        diff_path.write_text(diff, encoding="utf-8")
        for perspective in review.PERSPECTIVES:
            report = run_perspective(
                root, request, perspective, provider=provider, model=model, binary=binary, limitation=limitation,
                launcher=launcher or subprocess_launcher, timeout=timeout_seconds(config), scratch=scratch,
                diff_path=diff_path, watched=watched,
            )
            atomic_write_text(review.report_path(change, perspective), json.dumps(report, indent=2, sort_keys=True) + "\n")
            reports[perspective] = report
    return reports
