#!/usr/bin/env python3
"""Experimental, disabled-by-default DeepSeek Harness runtime adapter.

All DeepSeek Harness and Cordis vocabulary is contained in this module and its
private observation profile.  Platform lifecycle, routing, verification and
publication code consume none of it.  The public boundary is JSON-compatible
capability/request/result evidence plus a cancellable process handle.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from _platform_common import current_worktree_root, main_root, read_platform_config
from delegation_containment import check_containment, snapshot
from model_routing import (
    efficiency_runtime_measurement,
    efficiency_timing,
    efficiency_unknown_usage,
)

BACKEND = "deepseek-harness"
SDK_DISTRIBUTION = "deepseek-harness-sdk"
RUNTIME_DISTRIBUTION = "deepseek-harness-runtime-bin"
PINNED_SDK_VERSION = "0.1.1rc1"
PINNED_LICENSE = "MIT"
SUPPORTED_PROFILE = "observation"
WRITE_PROFILE = "workspace-write"
SOURCE_PLATFORM_SELECTED = "platform-selected"
SOURCE_INSTALLED_PACKAGE = "installed-package"

ASSET_ROOT = Path(__file__).resolve().parents[1]
OBSERVATION_CONFIG = ASSET_ROOT / "dev-platform" / "deepseek-harness-observation.cordis.yml"
REQUIREMENTS_FILE = ASSET_ROOT / "requirements" / "deepseek-harness.txt"

_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret)(\s*[:=]\s*)([^\s'\"\\]+)"
)
_JSON_SECRET_RE = re.compile(
    r"(?i)([\"']?(?:api[_-]?key|token|password|secret)[\"']?\s*:\s*[\"'])([^\"'\s]+)"
)
_CREDENTIAL_SHAPE_RE = re.compile(r"\b(?:sk|sess|key)-[A-Za-z0-9._-]{8,}\b")
_DIAGNOSTIC_LIMIT = 4000


class AdapterError(RuntimeError):
    """Actionable experimental-runtime refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sanitize_diagnostic(value: str) -> str:
    sanitized = _SECRET_RE.sub(r"\1\2[REDACTED]", value)
    sanitized = _JSON_SECRET_RE.sub(r"\1[REDACTED]", sanitized)
    sanitized = _CREDENTIAL_SHAPE_RE.sub("[REDACTED]", sanitized)
    if len(sanitized) <= _DIAGNOSTIC_LIMIT:
        return sanitized
    return "[output truncated]\n" + sanitized[-_DIAGNOSTIC_LIMIT:]


def _runtime_policy(root: Path) -> dict[str, Any]:
    config = read_platform_config(root)
    experimental = config.get("experimental_runtime", {})
    section = experimental.get("deepseek_harness", {}) if isinstance(experimental, dict) else {}
    if not isinstance(section, dict):
        section = {}
    return {
        "enabled": section.get("enabled") is True,
        "sdk_version": str(section.get("sdk_version", PINNED_SDK_VERSION)),
        "profile": str(section.get("profile", SUPPORTED_PROFILE)),
    }


def _host_supported(system: str | None = None, machine: str | None = None) -> tuple[bool, str]:
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    if system == "linux" and machine in {"x86_64", "amd64", "aarch64", "arm64"}:
        return True, f"{system}/{machine}"
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return True, f"{system}/{machine}"
    return False, f"{system}/{machine}"


def _installed_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _resolve_bundled_runtime() -> tuple[str, ...]:
    # Keep this adapter's module name distinct from the upstream
    # ``deepseek_harness_runtime`` carrier imported here and by the SDK.
    from deepseek_harness_runtime import resolve_bundled_launch_args

    return tuple(str(part) for part in resolve_bundled_launch_args())


def inspect_capability(
    root: Path,
    *,
    explicit_opt_in: bool = False,
    version_reader: Callable[[str], str | None] = _installed_version,
    runtime_resolver: Callable[[], Sequence[str]] = _resolve_bundled_runtime,
    system: str | None = None,
    machine: str | None = None,
) -> dict[str, Any]:
    """Return bounded capability evidence without enabling or launching DSH."""
    policy = _runtime_policy(root)
    enabled = policy["enabled"] or explicit_opt_in
    base: dict[str, Any] = {
        "kind": "runtime-capability",
        "backend": BACKEND,
        "experimental": True,
        "selection": "enabled" if enabled else "disabled",
        "default": False,
        "profile": policy["profile"],
        "configured_version": policy["sdk_version"],
        "required_version": PINNED_SDK_VERSION,
        "license": PINNED_LICENSE,
        "write_capability": {
            "status": "unavailable",
            "reason": (
                "the pinned Python SDK does not expose sandbox runner/enforcement "
                "attestation; workspace-write therefore fails closed"
            ),
        },
    }

    if sys.version_info < (3, 10):  # noqa: UP036 - copied adapter can be invoked by an older project interpreter
        return {
            **base,
            "status": "incompatible",
            "diagnostic": "DeepSeek Harness SDK requires Python 3.10 or newer.",
        }
    supported, host = _host_supported(system, machine)
    base["host"] = host
    if not supported:
        return {
            **base,
            "status": "incompatible",
            "diagnostic": (
                "Pinned DeepSeek Harness runtime wheels support Linux x86_64/aarch64 "
                "and macOS 14+ arm64; no supported wheel exists for this host."
            ),
        }
    if policy["sdk_version"] != PINNED_SDK_VERSION:
        return {
            **base,
            "status": "incompatible",
            "diagnostic": (
                f"Configured DeepSeek Harness SDK version {policy['sdk_version']!r} is unsupported; "
                f"this adapter requires exact version {PINNED_SDK_VERSION}."
            ),
        }
    if policy["profile"] != SUPPORTED_PROFILE:
        return {
            **base,
            "status": "incompatible",
            "diagnostic": (
                f"Configured profile {policy['profile']!r} is unsupported; "
                f"the only initial profile is {SUPPORTED_PROFILE!r}."
            ),
        }

    sdk_version = version_reader(SDK_DISTRIBUTION)
    runtime_version = version_reader(RUNTIME_DISTRIBUTION)
    base["installed"] = {
        SDK_DISTRIBUTION: sdk_version,
        RUNTIME_DISTRIBUTION: runtime_version,
    }
    if sdk_version is None or runtime_version is None:
        return {
            **base,
            "status": "missing",
            "diagnostic": (
                "Optional DeepSeek Harness runtime is not installed. Create an isolated "
                f"environment and run: python -m pip install -r {REQUIREMENTS_FILE}"
            ),
        }
    if sdk_version != PINNED_SDK_VERSION or runtime_version != PINNED_SDK_VERSION:
        return {
            **base,
            "status": "incompatible",
            "diagnostic": (
                "Installed DeepSeek Harness distributions do not match the exact tested pin: "
                f"sdk={sdk_version!r}, runtime={runtime_version!r}, required={PINNED_SDK_VERSION!r}."
            ),
        }
    try:
        launch_args = tuple(runtime_resolver())
    except (ImportError, FileNotFoundError, OSError, RuntimeError) as exc:
        return {
            **base,
            "status": "incompatible",
            "diagnostic": "Pinned DeepSeek Harness runtime carrier is unusable: " + _sanitize_diagnostic(str(exc)),
        }
    if not launch_args:
        return {
            **base,
            "status": "incompatible",
            "diagnostic": "Pinned DeepSeek Harness runtime resolved an empty launch command.",
        }
    if not OBSERVATION_CONFIG.is_file():
        return {
            **base,
            "status": "incompatible",
            "diagnostic": f"Dev Platform observation profile is missing: {OBSERVATION_CONFIG}",
        }
    return {
        **base,
        "status": "available",
        "transport": "python-sdk-jsonrpc-stdio",
        "runtime_carrier": "bundled-executable",
    }


def _require_available(capability: Mapping[str, Any], profile_name: str) -> None:
    if capability.get("status") != "available":
        raise AdapterError(str(capability.get("status", "unavailable")), str(capability.get("diagnostic", "runtime unavailable")))
    if capability.get("selection") != "enabled":
        raise AdapterError(
            "experimental_runtime_disabled",
            "DeepSeek Harness is disabled by default; use the explicit experimental opt-in for this run or set experimental_runtime.deepseek_harness.enabled=true.",
        )
    if profile_name == WRITE_PROFILE:
        reason = capability.get("write_capability", {}).get("reason")
        raise AdapterError("containment_unavailable", str(reason or "write containment is not provable"))
    if profile_name != SUPPORTED_PROFILE:
        raise AdapterError("unsupported_profile", f"unsupported DeepSeek Harness profile {profile_name!r}")


def _resolved_workspace(workspace: Path, session_root: Path) -> tuple[Path, Path]:
    resolved_workspace = workspace.expanduser().resolve()
    if not resolved_workspace.is_dir():
        raise AdapterError("invalid_workspace", f"assigned workspace is not an existing directory: {resolved_workspace}")
    resolved_sessions = session_root.expanduser().resolve()
    try:
        resolved_sessions.relative_to(resolved_workspace)
    except ValueError as exc:
        raise AdapterError(
            "invalid_session_root",
            f"DSH session_root must stay inside the assigned workspace: {resolved_sessions}",
        ) from exc
    resolved_sessions.mkdir(parents=True, exist_ok=True)
    return resolved_workspace, resolved_sessions


def normalize_usage(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Map complete DSH samples into the canonical runtime-neutral usage schema."""
    requests = [event for event in events if event.get("type") == "assistant/message"]
    usage_evidence = efficiency_unknown_usage()
    if not requests:
        return usage_evidence
    usage_evidence["request_count"] = efficiency_runtime_measurement(len(requests))
    fields = {
        "inputTokens": "fresh_input_tokens",
        "cacheReadTokens": "cache_read_tokens",
        "outputTokens": "output_tokens",
    }
    for source_name, target_name in fields.items():
        values: list[int] = []
        for event in requests:
            data = event.get("data")
            sample = data.get("usage") if isinstance(data, dict) else None
            value = sample.get(source_name) if isinstance(sample, dict) else None
            if type(value) is not int or value < 0:
                values = []
                break
            values.append(value)
        if len(values) == len(requests):
            usage_evidence[target_name] = efficiency_runtime_measurement(sum(values))
    return usage_evidence


def _base_result(started_at: str, started_monotonic: float, *, status: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "backend": BACKEND,
        "experimental": True,
        "runtime": {
            "distribution": SDK_DISTRIBUTION,
            "version": PINNED_SDK_VERSION,
            "source": SOURCE_INSTALLED_PACKAGE,
        },
        "execution": {
            "efficiency": {
                "timing": efficiency_timing(
                    started_at,
                    max(0, round((time.monotonic() - started_monotonic) * 1000)),
                ),
                "usage": efficiency_unknown_usage(),
            },
        },
        "terminal": {"status": status, "reason": reason},
        "containment": {
            "profile": SUPPORTED_PROFILE,
            "write_capable": False,
            "status": "not-applicable",
            "reason": "the observation profile mounts no model-facing write-capable capability",
        },
    }


@dataclass
class RuntimeHandle:
    """One adapter-owned worker and its bundled DSH runtime process group."""

    process: subprocess.Popen[str]
    started_at: str
    started_monotonic: float

    def wait(self, timeout_seconds: float | None = None) -> dict[str, Any]:
        try:
            stdout, stderr = self.process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            return self.cancel("timeout")
        lines = [line for line in stdout.splitlines() if line.strip()]
        if len(lines) != 1:
            result = _base_result(self.started_at, self.started_monotonic, status="failed", reason="invalid-worker-output")
            result["diagnostic"] = _sanitize_diagnostic(stderr or stdout or "worker produced no result")
            result["cleanup"] = {"status": "clean" if self.process.poll() is not None else "unknown"}
            return result
        try:
            payload = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            result = _base_result(self.started_at, self.started_monotonic, status="failed", reason="invalid-worker-json")
            result["diagnostic"] = _sanitize_diagnostic(str(exc))
            result["cleanup"] = {"status": "clean" if self.process.poll() is not None else "unknown"}
            return result
        if not isinstance(payload, dict):
            result = _base_result(self.started_at, self.started_monotonic, status="failed", reason="invalid-worker-result")
            result["cleanup"] = {"status": "clean"}
            return result
        if stderr.strip() and payload.get("terminal", {}).get("status") != "completed":
            payload.setdefault("diagnostic", _sanitize_diagnostic(stderr))
        return payload

    def cancel(self, reason: str = "cancelled") -> dict[str, Any]:
        def group_alive(group_id: int | None) -> bool:
            # poll() also reaps the direct worker when it has exited; without
            # that waitpid a zombie can make killpg(..., 0) look live forever.
            self.process.poll()
            if group_id is None:
                return self.process.poll() is None
            try:
                os.killpg(group_id, 0)
            except ProcessLookupError:
                return False
            except OSError:
                return True
            return True

        pgid: int | None = None
        if self.process.poll() is None:
            try:
                pgid = os.getpgid(self.process.pid)
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError:
                self.process.terminate()

        deadline = time.monotonic() + 2.0
        while group_alive(pgid) and time.monotonic() < deadline:
            time.sleep(0.05)
        if group_alive(pgid):
            try:
                if pgid is not None:
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    self.process.kill()
            except ProcessLookupError:
                pass
            kill_deadline = time.monotonic() + 2.0
            while group_alive(pgid) and time.monotonic() < kill_deadline:
                time.sleep(0.05)
        try:
            self.process.communicate(timeout=2.0)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.communicate()

        group_reaped = not group_alive(pgid)
        result = _base_result(
            self.started_at,
            self.started_monotonic,
            status="timed-out" if reason == "timeout" else "cancelled",
            reason=reason,
        )
        result["cleanup"] = {
            "status": "clean" if group_reaped else "unproven",
            "method": "process-group-term-kill-reap",
            "process_group_reaped": group_reaped,
        }
        return result


def start_runtime(
    root: Path,
    *,
    workspace: Path,
    session_root: Path,
    prompt: str,
    explicit_opt_in: bool = False,
    profile_name: str = SUPPORTED_PROFILE,
    model: str = "deepseek-v4-flash",
    max_tokens: int | None = None,
    session_id: str | None = None,
    env_override: Mapping[str, str] | None = None,
    worker_command: Sequence[str] | None = None,
    capability_override: Mapping[str, Any] | None = None,
) -> RuntimeHandle:
    """Start one isolated DSH worker after exact capability and scope checks."""
    capability = dict(capability_override or inspect_capability(root, explicit_opt_in=explicit_opt_in))
    _require_available(capability, profile_name)
    if not prompt.strip():
        raise AdapterError("invalid_prompt", "DeepSeek Harness prompt must not be empty")
    if max_tokens is not None and max_tokens <= 0:
        raise AdapterError("invalid_max_tokens", "max_tokens must be a positive integer")
    resolved_workspace, resolved_sessions = _resolved_workspace(workspace, session_root)
    request = {
        "workspace": str(resolved_workspace),
        "session_root": str(resolved_sessions),
        "prompt": prompt,
        "profile": profile_name,
        "model": model,
        "max_tokens": max_tokens,
        "session_id": session_id or f"dev-platform-{uuid.uuid4().hex}",
        "cordis": str(OBSERVATION_CONFIG),
    }
    command = list(worker_command or (sys.executable, str(Path(__file__).resolve()), "_worker"))
    env = os.environ.copy()
    if env_override:
        env.update({str(key): str(value) for key, value in env_override.items()})
    env["DSH_MODEL"] = model
    started_at = _utc_now()
    started_monotonic = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=resolved_workspace,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        start_new_session=True,
    )
    assert process.stdin is not None
    try:
        process.stdin.write(json.dumps(request, separators=(",", ":")))
        process.stdin.close()
        process.stdin = None
    except BaseException:
        process.kill()
        process.wait()
        raise
    return RuntimeHandle(process=process, started_at=started_at, started_monotonic=started_monotonic)


def _worker_result(request: Mapping[str, Any]) -> dict[str, Any]:
    started_at = _utc_now()
    started_monotonic = time.monotonic()
    try:
        sdk_version = _installed_version(SDK_DISTRIBUTION)
        runtime_version = _installed_version(RUNTIME_DISTRIBUTION)
        if sdk_version != PINNED_SDK_VERSION or runtime_version != PINNED_SDK_VERSION:
            raise AdapterError(
                "incompatible_version",
                f"worker requires exact DSH SDK/runtime {PINNED_SDK_VERSION}; observed {sdk_version}/{runtime_version}",
            )
        from deepseek_harness import DeepSeekHarness

        harness = DeepSeekHarness(
            provider="deepseek-official",
            model=str(request["model"]),
            max_tokens=request.get("max_tokens"),
            cwd=str(request["workspace"]),
            runtime_cwd=str(request["workspace"]),
            session_root=str(request["session_root"]),
            cordis=str(request["cordis"]),
            shutdown_timeout_seconds=2.0,
        )
        with harness:
            run_result = harness.run(str(request["prompt"]), session_id=str(request["session_id"]))
        terminal_status = "completed" if run_result.finish_reason == "completed" else "failed"
        result = _base_result(
            started_at,
            started_monotonic,
            status=terminal_status,
            reason=run_result.finish_reason or "unknown",
        )
        result["execution"].update(
            {
                "id": run_result.session_id,
                "kind": "runtime-execution",
                "source": SOURCE_PLATFORM_SELECTED,
            }
        )
        response = run_result.final_response
        result["result"] = {
            "text": response[:16000],
            "truncated": len(response) > 16000,
        }
        result["execution"]["efficiency"]["usage"] = normalize_usage(run_result.events)
        result["cleanup"] = {"status": "clean", "method": "sdk-context-close"}
        return result
    except Exception as exc:  # noqa: BLE001 - worker boundary must return a bounded terminal failure
        result = _base_result(started_at, started_monotonic, status="failed", reason=type(exc).__name__)
        result["diagnostic"] = _sanitize_diagnostic(str(exc))
        result["cleanup"] = {"status": "attempted", "method": "sdk-worker-finalization"}
        return result


def _worker_main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise TypeError("worker request must be a JSON object")
        result = _worker_result(request)
    except Exception as exc:  # noqa: BLE001 - invalid worker input must still produce one bounded record
        now = time.monotonic()
        result = _base_result(_utc_now(), now, status="failed", reason="invalid-worker-request")
        result["diagnostic"] = _sanitize_diagnostic(str(exc))
        result["cleanup"] = {"status": "clean"}
    print(json.dumps(result, separators=(",", ":"), sort_keys=True), flush=True)
    return 0 if result.get("terminal", {}).get("status") == "completed" else 1


class _SmokeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, *, stall: bool) -> None:
        super().__init__(("127.0.0.1", 0), _SmokeHandler)
        self.stall = stall
        self.request_seen = threading.Event()
        self.release = threading.Event()


class _SmokeHandler(BaseHTTPRequestHandler):
    server: _SmokeServer

    def log_message(self, _format: str, *_args: object) -> None:
        return None

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        if length:
            self.rfile.read(length)
        self.server.request_seen.set()
        if self.server.stall:
            self.server.release.wait(timeout=30)
            return
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        payloads = (
            {"choices": [{"delta": {"role": "assistant", "content": None}}]},
            {"choices": [{"delta": {"content": "DSH_SMOKE_OK"}}]},
            {
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            },
        )
        try:
            for payload in payloads:
                self.wfile.write(f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
        except (BrokenPipeError, ConnectionResetError):
            pass


def _start_smoke_server(*, stall: bool) -> tuple[_SmokeServer, threading.Thread, str]:
    server = _SmokeServer(stall=stall)
    thread = threading.Thread(target=server.serve_forever, name="dsh-smoke-provider", daemon=True)
    thread.start()
    host, port = server.server_address
    return server, thread, f"http://{host}:{port}"


def run_smoke(root: Path, integration_root: Path) -> dict[str, Any]:
    capability = inspect_capability(root, explicit_opt_in=True)
    if capability.get("status") != "available":
        return {"status": "blocked", "capability": capability}
    before = snapshot(integration_root)
    with tempfile.TemporaryDirectory(prefix="dev-platform-dsh-smoke-") as temporary:
        workspace = Path(temporary) / "workspace"
        workspace.mkdir()
        sessions = workspace / ".dsh-sessions"
        common_env = {"DEEPSEEK_API_KEY": "keyless-local-smoke"}

        server, thread, base_url = _start_smoke_server(stall=False)
        try:
            completed = start_runtime(
                root,
                workspace=workspace,
                session_root=sessions,
                prompt="Reply with exactly DSH_SMOKE_OK.",
                explicit_opt_in=True,
                env_override={**common_env, "DEEPSEEK_BASE_URL": base_url},
            ).wait(timeout_seconds=60)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        cancel_server, cancel_thread, cancel_url = _start_smoke_server(stall=True)
        try:
            handle = start_runtime(
                root,
                workspace=workspace,
                session_root=sessions,
                prompt="Wait for the provider response.",
                explicit_opt_in=True,
                env_override={**common_env, "DEEPSEEK_BASE_URL": cancel_url},
            )
            if not cancel_server.request_seen.wait(timeout=30):
                cancelled = handle.cancel("smoke-provider-not-reached")
            else:
                cancelled = handle.cancel("smoke-cancel")
        finally:
            cancel_server.release.set()
            cancel_server.shutdown()
            cancel_server.server_close()
            cancel_thread.join(timeout=2)

        try:
            start_runtime(
                root,
                workspace=workspace,
                session_root=sessions,
                prompt="Attempt a write.",
                explicit_opt_in=True,
                profile_name=WRITE_PROFILE,
            )
        except AdapterError as exc:
            write_refusal = {"status": "refused", "code": exc.code, "diagnostic": str(exc)}
        else:  # pragma: no cover - fail-closed invariant
            write_refusal = {"status": "unsafe-launch"}

    containment = check_containment(before, snapshot(integration_root))
    completed_ok = (
        completed.get("terminal", {}).get("status") == "completed"
        and completed.get("result", {}).get("text") == "DSH_SMOKE_OK"
        and completed.get("cleanup", {}).get("status") == "clean"
    )
    cancelled_ok = (
        cancelled.get("terminal", {}).get("status") == "cancelled"
        and cancelled.get("cleanup", {}).get("process_group_reaped") is True
    )
    passed = completed_ok and cancelled_ok and write_refusal.get("code") == "containment_unavailable" and not containment.violated
    return {
        "status": "passed" if passed else "failed",
        "backend": BACKEND,
        "version": PINNED_SDK_VERSION,
        "complete_run": completed,
        "cancel_run": cancelled,
        "write_profile": write_refusal,
        "integration_containment": {
            "status": "clean" if not containment.violated else "violated",
            "new_changes": list(containment.new_changes),
            "disappeared_changes": list(containment.disappeared_changes),
            "head_moved": containment.head_moved,
        },
    }


def _print(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    capability_parser = subparsers.add_parser("capability", help="inspect the optional pinned backend")
    capability_parser.add_argument("--enable-experimental", action="store_true")

    run_parser = subparsers.add_parser("run", help="run one explicit observation-only DSH request")
    run_parser.add_argument("--enable-experimental", action="store_true")
    run_parser.add_argument("--profile", choices=(SUPPORTED_PROFILE, WRITE_PROFILE), default=SUPPORTED_PROFILE)
    run_parser.add_argument("--workspace", required=True)
    run_parser.add_argument("--session-root", required=True)
    run_parser.add_argument("--prompt", required=True)
    run_parser.add_argument("--model", default="deepseek-v4-flash")
    run_parser.add_argument("--max-tokens", type=int)
    run_parser.add_argument("--timeout-seconds", type=float, default=600.0)

    smoke_parser = subparsers.add_parser("smoke", help="run a host-level keyless real-runtime smoke")
    smoke_parser.add_argument("--enable-experimental", action="store_true", required=True)
    smoke_parser.add_argument("--integration-root")

    subparsers.add_parser("_worker", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.command == "_worker":
        return _worker_main()

    root = current_worktree_root()
    if args.command == "capability":
        payload = inspect_capability(root, explicit_opt_in=args.enable_experimental)
        _print(payload)
        return 0 if payload.get("status") == "available" else 2
    if args.command == "run":
        try:
            handle = start_runtime(
                root,
                workspace=Path(args.workspace),
                session_root=Path(args.session_root),
                prompt=args.prompt,
                explicit_opt_in=args.enable_experimental,
                profile_name=args.profile,
                model=args.model,
                max_tokens=args.max_tokens,
            )
            payload = handle.wait(timeout_seconds=args.timeout_seconds)
        except AdapterError as exc:
            payload = {"status": "blocked", "code": exc.code, "diagnostic": str(exc)}
            _print(payload)
            return 2
        _print(payload)
        return 0 if payload.get("terminal", {}).get("status") == "completed" else 1
    if args.command == "smoke":
        integration = Path(args.integration_root).resolve() if args.integration_root else main_root()
        payload = run_smoke(root, integration)
        _print(payload)
        return 0 if payload.get("status") == "passed" else 2
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
