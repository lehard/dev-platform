#!/usr/bin/env python3
"""Handoff gate of queue and lifecycle changes: a live scenario receipt bound to the content of the declared paths.

The receipt is written by `scripts/live_scenarios.py run` on the operator Mac and kept in the integration checkout's
ignored `.claude/`. It binds to the declared paths at the tested head, so a later commit outside them keeps it.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

GATE_FILE = Path("dev-platform") / "live-scenario-gate.toml"
RUN_COMMAND = "python3 scripts/live_scenarios.py run --workdir <directory>"


class LiveGateError(RuntimeError):
    """Handoff is refused; the message names the receipt or scenario."""


@dataclass(frozen=True)
class Gate:
    paths: tuple[str, ...]
    scenarios: tuple[str, ...]
    known_failures: dict[str, str]


def load_gate(root: Path) -> Gate:
    path = root / GATE_FILE
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return Gate(tuple(data["paths"]), tuple(data["scenarios"]), dict(data["known_failures"]))
    except (OSError, KeyError, tomllib.TOMLDecodeError) as error:
        raise LiveGateError(f"cannot read {path}: {error!r}") from error


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    if done.returncode:
        raise LiveGateError(f"git {' '.join(args)} exited {done.returncode}: {done.stderr.strip()[-500:]}")
    return done.stdout


def content_digest(root: Path, gate: Gate, revision: str) -> str:
    return hashlib.sha256(_git(root, "ls-tree", "-r", revision, "--", *gate.paths).encode("utf-8")).hexdigest()


def receipt_path(root: Path, digest: str) -> Path:
    common = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    return common.parent / ".claude" / "live-scenario-receipts" / f"{digest}.json"


def write_receipt(root: Path, head: str, results: list[dict[str, str]]) -> Path:
    gate = load_gate(root)
    digest = content_digest(root, gate, head)
    path = receipt_path(root, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"digest": digest, "head": head, "results": results}, indent=2) + "\n", encoding="utf-8")
    return path


def changed_paths(root: Path, gate: Gate, main_branch: str) -> list[str]:
    base = _git(root, "merge-base", "HEAD", f"origin/{main_branch}").strip()
    return [path for path in _git(root, "diff", "--name-only", base, "HEAD").split("\n") if path in gate.paths]


def require_receipt(root: Path, main_branch: str) -> list[str]:
    """Refuse a declared-path change without a green receipt for its content; return known failures to report."""
    gate = load_gate(root)
    changed = changed_paths(root, gate, main_branch)
    if not changed:
        return []
    path = receipt_path(root, content_digest(root, gate, "HEAD"))
    if not path.is_file():
        raise LiveGateError(f"no live scenario receipt for the content of {', '.join(changed[:5])}; run: {RUN_COMMAND}")
    results = {item["scenario"]: item for item in json.loads(path.read_text(encoding="utf-8"))["results"]}
    missing = [name for name in gate.scenarios if name not in results]
    if missing:
        raise LiveGateError(f"live scenario receipt {path.name} lacks {', '.join(missing)}; run: {RUN_COMMAND}")
    known = []
    for name in gate.scenarios:
        item = results[name]
        if item["result"] == "passed":
            continue
        if name not in gate.known_failures:
            raise LiveGateError(f"live scenario {name} is red at step {item.get('step')!r}: {item.get('observed', '')[:500]}")
        known.append(f"known live scenario failure {name}: {gate.known_failures[name]}")
    return known
