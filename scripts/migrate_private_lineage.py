#!/usr/bin/env python3
"""One-time, idempotent current-tree redaction of legacy public lineage.

Mapping comments are verified on the original private Issues before any
public file is changed. The original Git commits remain historical evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
from private_lineage import handle_for_issue  # noqa: E402
from requirement_integration import _digest  # noqa: E402


BACKLOG_REF_RE = re.compile(r"lehard/development-backlog#[1-9][0-9]*")


def encoded(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def redact_record(path: Path, source: str, handle: str, *, receipt: bool) -> None:
    original = path.read_bytes()
    payload = json.loads(original)
    target = payload["managed_checkout"] if receipt else payload
    if target.get("source_issue") != source:
        raise RuntimeError("legacy archive identity differs from expected source")
    del target["source_issue"]
    target["private_lineage_handle"] = handle
    payload["identity_redaction"] = {
        "version": 1,
        "method": "private-lineage-current-tree-migration",
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "after_original_verification": True,
    }
    path.write_text(encoded(payload), encoding="utf-8")


def migrate_archives() -> int:
    archive_root = ROOT / "openspec" / "changes" / "archive"
    candidates = sorted(archive_root.glob("**/.managed-task.json"))
    pending: list[tuple[Path, str, str]] = []
    for path in candidates:
        payload = json.loads(path.read_text(encoding="utf-8"))
        source = payload.get("source_issue")
        if isinstance(source, str) and BACKLOG_REF_RE.fullmatch(source):
            pending.append((path, source, payload["change"]))
    mappings = {(source, change): handle_for_issue(ROOT, source, change, create=True) for _, source, change in pending}
    for path, source, change in pending:
        handle = mappings[(source, change)]
        checks = path.with_name("automated-checks.json")
        if not checks.is_file():
            raise RuntimeError("legacy archive lacks automated check receipt")
        redact_record(path, source, handle, receipt=False)
        redact_record(checks, source, handle, receipt=True)
    return len(pending)


def migrate_integration_manifest() -> bool:
    directory = ROOT / "dev-platform" / "requirement-integrations"
    files = sorted(directory.glob("*.json"))
    pending: list[tuple[Path, dict]] = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload.get("requirement"), str) and BACKLOG_REF_RE.fullmatch(payload["requirement"]):
            pending.append((path, payload))
    if not pending:
        return False
    if len(pending) != 1:
        raise RuntimeError("legacy integration manifest migration is ambiguous")
    path, payload = pending[0]
    requirement = payload.pop("requirement")
    requirement_handle = handle_for_issue(ROOT, requirement, "requirement-integration", create=True)
    payload["private_requirement_handle"] = requirement_handle
    for child in payload["children"]:
        source = child.pop("source_issue")
        child["private_lineage_handle"] = handle_for_issue(ROOT, source, child["change"], create=True)
    payload["identity_redaction"] = {"version": 1, "method": "private-lineage-current-tree-migration", "after_original_verification": True}
    payload.pop("digest")
    payload["digest"] = _digest(payload)
    generation = payload.get("generation", "legacy")
    replacement = directory / f"private-lineage-{requirement_handle}-integration-{generation}-merge.json"
    if replacement.exists():
        raise RuntimeError("redacted integration manifest path already exists")
    replacement.write_text(encoded(payload), encoding="utf-8")
    path.unlink()
    return True


def main() -> int:
    archives = migrate_archives()
    manifest = migrate_integration_manifest()
    print(f"redacted {archives} archived managed records; integration manifest redacted: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
