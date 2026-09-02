#!/usr/bin/env python3
"""Bounded exploratory browser verification adapter.

This adapter lets an agent gather *bounded exploratory evidence* that a real
user-visible web flow works, while deterministic Playwright / project E2E stays
the repeatable acceptance authority.  It deliberately owns no capability
lifecycle mechanics: identity, opt-in, materialization, provenance and
update/removal all come from the optional engineering capability lifecycle
(`capability_manager.py`).

Design constraints (see the ``browser-verification`` capability descriptor and
``docs/engineering/browser-verification.md``):

* Default-deny origins.  ``localhost``, ``127.0.0.1``, ``::1``, ``*.localhost``
  and ``*.test`` are always allowed.  A project widens the set through
  ``dev-platform/browser-verification.toml``.  Production origins must be listed
  under ``production_origins`` *and* granted per run with
  ``--allow-production-origin``; interactive (write/submit) steps against a
  production origin are always refused.
* No durable session leakage.  All browser runtime state is written under the
  git-ignored ``.dev-platform/browser-verification/`` directory, and the durable
  evidence envelope is sanitized (screenshot pointer only, never cookie /
  credential / profile bytes).
* The exploratory backend (`agent-browser`) is development tooling.  When it is
  not installed the adapter reports ``backend-unavailable`` -- an explicit
  outcome distinct from a failing flow -- and never fails a mandatory check that
  did not opt in.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

EVIDENCE_SCHEMA = "browser-verification/evidence@1"
RUN_PLAN_SCHEMA = "browser-verification/run-plan@1"
SCAFFOLD_SCHEMA = "browser-verification/regression-scaffold@1"

# Pinned exploratory backend.  Kept in sync with the capability descriptor
# instruction and docs/engineering/browser-verification.md.
BACKEND = {
    "name": "agent-browser",
    "package": "agent-browser",
    "version": "0.36.0",
    "dist_shasum": "e672393279a620fb6c79f6c00797908631450a04",
    "license": "Apache-2.0",
    "source": "vercel-labs/agent-browser",
}

DEFAULT_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}
DEFAULT_DEV_SUFFIXES = (".localhost", ".test")

RUNTIME_STATE_DIR = Path(".dev-platform/browser-verification")
ALLOWLIST_FILE = Path("dev-platform/browser-verification.toml")

READ_ONLY_STEPS = {"navigate", "wait_for", "snapshot", "assert_text", "assert_no_text", "screenshot", "accessibility"}
INTERACTIVE_STEPS = {"click", "fill", "submit", "press", "type"}
ALL_STEPS = READ_ONLY_STEPS | INTERACTIVE_STEPS

# Filenames that indicate persisted browser session state; durable evidence
# directories must never contain them.
SESSION_STATE_MARKERS = re.compile(
    r"(^|/)(cookies?(\.json|\.sqlite|\.txt)?|.*\.cookies|Cookies|Login Data|Web Data|"
    r"Local Storage|profile\.json|storage_state\.json)$",
    re.IGNORECASE,
)
FORBIDDEN_EVIDENCE_KEYS = {"cookies", "cookie", "credentials", "credential", "password",
                          "authorization", "auth_token", "token", "profile", "storage_state",
                          "screenshot_bytes", "screenshot_base64"}


class BrowserVerificationError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise BrowserVerificationError(f"cannot read {path}: {exc}") from exc


def load_allowlist(root: Path) -> dict[str, Any]:
    """Return the project-owned origin allowlist; an absent file means localhost/test only."""
    path = root / ALLOWLIST_FILE
    if not path.is_file():
        return {"version": 1, "allowlisted_origins": [], "production_origins": []}
    data = _load_toml(path)
    if data.get("version") != 1:
        raise BrowserVerificationError(f"{ALLOWLIST_FILE}: version must be 1")
    for key in ("allowlisted_origins", "production_origins"):
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            raise BrowserVerificationError(f"{ALLOWLIST_FILE}: {key} must be a list of origin strings")
    return {
        "version": 1,
        "allowlisted_origins": sorted({item.strip().rstrip('/') for item in data.get("allowlisted_origins", [])}),
        "production_origins": sorted({item.strip().rstrip('/') for item in data.get("production_origins", [])}),
    }


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        raise BrowserVerificationError(f"target URL is not absolute: {url!r}")
    host = parsed.hostname
    if parsed.port:
        return f"{parsed.scheme}://{host}:{parsed.port}"
    return f"{parsed.scheme}://{host}"


def _is_default_local(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if host in DEFAULT_LOOPBACK_HOSTS:
        return True
    return any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in DEFAULT_DEV_SUFFIXES)


def classify_origin(url: str, allowlist: dict[str, Any]) -> str:
    """Return one of: 'default-local', 'allowlisted', 'production', 'denied'."""
    origin = origin_of(url)
    if _is_default_local(url):
        return "default-local"
    if origin in allowlist["production_origins"]:
        return "production"
    if origin in allowlist["allowlisted_origins"]:
        return "allowlisted"
    return "denied"


def _load_flow(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserVerificationError(f"cannot read flow file {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list) or not data["steps"]:
        raise BrowserVerificationError("flow file must be an object with a non-empty 'steps' list")
    steps: list[dict[str, Any]] = []
    for index, raw in enumerate(data["steps"]):
        if not isinstance(raw, dict) or raw.get("action") not in ALL_STEPS:
            raise BrowserVerificationError(f"flow step {index} needs an 'action' in {sorted(ALL_STEPS)}")
        steps.append(raw)
    return {"name": str(data.get("name") or path.stem), "steps": steps,
            "expected_end_state": data.get("expected_end_state")}


def build_run_plan(root: Path, *, flow_file: Path, base_url: str,
                   allow_production_origin: bool) -> dict[str, Any]:
    allowlist = load_allowlist(root)
    flow = _load_flow(flow_file)
    classification = classify_origin(base_url, allowlist)
    origin = origin_of(base_url)

    if classification == "denied":
        raise BrowserVerificationError(
            f"origin {origin} is not allowed: add it to {ALLOWLIST_FILE} 'allowlisted_origins' "
            f"(non-production) or 'production_origins' (with --allow-production-origin)"
        )
    if classification == "production" and not allow_production_origin:
        raise BrowserVerificationError(
            f"origin {origin} is a production origin; pass --allow-production-origin to authorize this run"
        )

    interactive = sorted({step["action"] for step in flow["steps"] if step["action"] in INTERACTIVE_STEPS})
    if classification == "production" and interactive:
        raise BrowserVerificationError(
            f"production origin {origin} allows read-only exploration only; refused interactive steps: {interactive}"
        )

    return {
        "schema": RUN_PLAN_SCHEMA,
        "flow": flow["name"],
        "base_url": base_url,
        "origin": origin,
        "origin_classification": classification,
        "mode": "exploratory",
        "backend": dict(BACKEND),
        "interactive_steps": interactive,
        "steps": flow["steps"],
        "expected_end_state": flow["expected_end_state"],
        "prepared_at": _now(),
    }


# --------------------------------------------------------------------------- run


def _backend_bin() -> str | None:
    override = os.environ.get("AGENT_BROWSER_BIN")
    if override:
        return override if (Path(override).is_file() or shutil.which(override)) else None
    return shutil.which(BACKEND["package"])


def _backend_call(binary: str, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - explicit dev tooling invocation
        [binary, *args], cwd=str(cwd), capture_output=True, text=True, timeout=120, check=False,
    )


def _drive_flow(run_plan: dict[str, Any], state_dir: Path) -> dict[str, Any]:
    """Drive the flow through the pinned backend and collect bounded observations."""
    binary = _backend_bin()
    if binary is None:
        return {"outcome": "backend-unavailable", "steps": [], "observations": {},
                "detail": f"{BACKEND['package']}@{BACKEND['version']} is not installed"}

    profile_dir = state_dir / "profile"
    (state_dir).mkdir(parents=True, exist_ok=True)
    base = run_plan["base_url"].rstrip("/")
    executed: list[dict[str, Any]] = []
    observations: dict[str, Any] = {"final_url": None, "assertions": []}
    outcome = "expected-state-observed"
    opened = False

    # Keep every backend-authored artifact (profile, screenshots) inside the
    # ignored runtime-state directory.
    os.environ.update({
        "AGENT_BROWSER_PROFILE": str(profile_dir),
        "AGENT_BROWSER_SCREENSHOT_DIR": str(state_dir),
    })

    def _resolve(target: str) -> str:
        return target if target.startswith("http") else base + (target if target.startswith("/") else "/" + target)

    try:
        for step in run_plan["steps"]:
            action = step["action"]
            record: dict[str, Any] = {"action": action, "ok": True}
            try:
                if action == "navigate":
                    url = _resolve(step.get("target", "/"))
                    verb = "open" if not opened else "navigate"
                    result = _backend_call(binary, [verb, url], cwd=state_dir)
                    opened = opened or result.returncode == 0
                    record["ok"] = result.returncode == 0
                    observations["final_url"] = url
                elif action in {"assert_text", "assert_no_text"}:
                    needle = step["text"]
                    scope = step.get("selector") or step.get("ref") or "body"
                    result = _backend_call(binary, ["get", "text", scope], cwd=state_dir)
                    present = needle in (result.stdout or "")
                    want = action == "assert_text"
                    record["ok"] = present is want
                    observations["assertions"].append(
                        {"text": needle, "expected_present": want, "observed_present": present}
                    )
                    if not record["ok"]:
                        outcome = "regression-detected"
                elif action == "screenshot":
                    shot = state_dir / f"{step.get('name', 'screenshot')}.png"
                    result = _backend_call(binary, ["screenshot", str(shot)], cwd=state_dir)
                    record["ok"] = result.returncode == 0
                    record["pointer"] = str(RUNTIME_STATE_DIR / state_dir.name / shot.name)
                elif action in {"accessibility", "snapshot", "wait_for"}:
                    result = _backend_call(binary, ["snapshot"], cwd=state_dir)
                    record["ok"] = result.returncode == 0
                elif action in INTERACTIVE_STEPS:
                    ref = step.get("ref") or step.get("selector") or ""
                    cli = {
                        "click": ["click", ref],
                        "fill": ["fill", ref, step.get("value", "")],
                        "type": ["type", ref, step.get("value", "")],
                        "press": ["press", step.get("key", "Enter")],
                        "submit": ["press", step.get("key", "Enter")],
                    }[action]
                    result = _backend_call(binary, cli, cwd=state_dir)
                    record["ok"] = result.returncode == 0
                else:
                    record["ok"] = False
                    record["error"] = f"unsupported action {action!r}"
            except (subprocess.SubprocessError, OSError) as exc:
                record["ok"] = False
                record["error"] = str(exc)
                outcome = "flow-error"
            executed.append(record)
            if not record["ok"] and outcome == "expected-state-observed":
                outcome = "flow-error"
    finally:
        if opened:
            _backend_call(binary, ["close", "--all"], cwd=state_dir)

    return {"outcome": outcome, "steps": executed, "observations": observations}


def _assert_evidence_sanitized(evidence: dict[str, Any]) -> None:
    serialized = json.dumps(evidence).lower()
    for key in FORBIDDEN_EVIDENCE_KEYS:
        if f'"{key}"' in serialized:
            raise BrowserVerificationError(f"refusing to write evidence containing a {key!r} field")


def _reject_session_state(evidence_dir: Path) -> None:
    if not evidence_dir.exists():
        return
    for path in evidence_dir.rglob("*"):
        if path.is_file() and SESSION_STATE_MARKERS.search(path.as_posix()):
            raise BrowserVerificationError(
                f"evidence directory contains browser session state ({path.name}); "
                "keep runtime state under .dev-platform/browser-verification/"
            )


def record_run(root: Path, *, run_plan_path: Path, evidence_dir: Path) -> dict[str, Any]:
    try:
        run_plan = json.loads(run_plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserVerificationError(f"cannot read run plan {run_plan_path}: {exc}") from exc
    if run_plan.get("schema") != RUN_PLAN_SCHEMA:
        raise BrowserVerificationError("run plan schema mismatch; regenerate it with 'plan'")

    _reject_session_state(evidence_dir)
    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    state_dir = root / RUNTIME_STATE_DIR / run_id
    started = _now()
    driven = _drive_flow(run_plan, state_dir)

    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "flow": run_plan["flow"],
        "origin": run_plan["origin"],
        "origin_classification": run_plan.get("origin_classification"),
        "mode": "exploratory",
        "backend": run_plan["backend"],
        "started_at": started,
        "finished_at": _now(),
        "outcome": driven["outcome"],
        "runtime_state_dir": str(RUNTIME_STATE_DIR / run_id),
        "steps": driven["steps"],
        "observations": driven["observations"],
        "expected_end_state": run_plan.get("expected_end_state"),
        "sanitized": True,
        "deterministic_acceptance": "playwright-or-project-e2e-remains-authoritative",
    }
    if driven.get("detail"):
        evidence["detail"] = driven["detail"]
    _assert_evidence_sanitized(evidence)

    evidence_dir.mkdir(parents=True, exist_ok=True)
    out = evidence_dir / "browser-evidence.json"
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence["evidence_path"] = str(out)
    return evidence


# ----------------------------------------------------------------------- promote


def build_regression_scaffold(evidence_path: Path) -> dict[str, Any]:
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserVerificationError(f"cannot read evidence {evidence_path}: {exc}") from exc
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        raise BrowserVerificationError("evidence schema mismatch")

    failed = [a for a in evidence.get("observations", {}).get("assertions", [])
              if a.get("observed_present") is not a.get("expected_present")]
    return {
        "schema": SCAFFOLD_SCHEMA,
        "applied": False,
        "note": "Reviewed work required: this describes a deterministic regression test; it is not written automatically.",
        "flow": evidence.get("flow"),
        "origin": evidence.get("origin"),
        "outcome": evidence.get("outcome"),
        "suggested_test_path": f"tests/e2e/test_{evidence.get('flow', 'flow')}_regression.py",
        "failed_assertions": failed,
        "deterministic_seam": (
            "reproduce the failed assertion(s) above with Playwright / the project E2E suite"
            if failed else
            "no failed assertion captured; explain explicitly why no deterministic seam exists yet"
        ),
    }


# -------------------------------------------------------------------------- main


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded exploratory browser verification adapter.")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="resolve a flow against the origin allowlist and emit a bounded run plan")
    plan.add_argument("--flow-file", required=True, type=Path)
    plan.add_argument("--base-url", required=True)
    plan.add_argument("--allow-production-origin", action="store_true",
                      help="authorize a single run against an origin listed in production_origins")
    plan.add_argument("--out", type=Path, help="write the run plan JSON to this path as well as stdout")

    run = sub.add_parser("run", help="drive the flow through the pinned backend and write bounded evidence")
    run.add_argument("--run-plan", required=True, type=Path)
    run.add_argument("--evidence-dir", required=True, type=Path)

    promote = sub.add_parser("promote", help="describe a deterministic regression scaffold (never writes tests)")
    promote.add_argument("--evidence", required=True, type=Path)

    sub.add_parser("backend-info", help="print the pinned exploratory backend and its install state")

    args = parser.parse_args(argv)
    root = Path.cwd().resolve()
    try:
        if args.command == "plan":
            payload = build_run_plan(root, flow_file=args.flow_file, base_url=args.base_url,
                                     allow_production_origin=args.allow_production_origin)
            if args.out:
                args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            _emit(payload)
            return 0
        if args.command == "run":
            payload = record_run(root, run_plan_path=args.run_plan, evidence_dir=args.evidence_dir)
            _emit(payload)
            return 0 if payload["outcome"] in {"expected-state-observed", "regression-detected"} else 1
        if args.command == "promote":
            _emit(build_regression_scaffold(args.evidence))
            return 0
        if args.command == "backend-info":
            _emit({"backend": dict(BACKEND), "installed": _backend_bin() is not None})
            return 0
        raise BrowserVerificationError(f"unsupported command: {args.command}")
    except BrowserVerificationError as exc:
        print(f"Browser verification blocked: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
