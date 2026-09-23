#!/usr/bin/env python3
"""Verified, nonterminal handoff and assembly for one Requirement delivery.

This helper deliberately owns only the evidence that is new to shared
delivery.  It neither closes Issues nor changes Project status: the existing
publication and terminal-reconciliation primitives remain the authority once
the assembled candidate has passed their checks and merged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


RECEIPT_VERSION = 1
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ISSUE_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*$")


class RequirementIntegrationError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
    if result.returncode:
        raise RequirementIntegrationError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


@dataclass(frozen=True)
class ReadyForIntegrationReceipt:
    version: int
    requirement: str
    source_issue: str
    change: str
    source_branch: str
    head: str
    verification_receipt: str
    archived_contract: str
    digest: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ReadyForIntegrationReceipt":
        required = {"version", "requirement", "source_issue", "change", "source_branch", "head", "verification_receipt", "archived_contract", "digest"}
        if set(payload) != required:
            raise RequirementIntegrationError("ready-for-integration receipt has unsupported or missing fields")
        receipt = cls(**payload)
        if receipt.version != RECEIPT_VERSION or not ISSUE_RE.fullmatch(receipt.requirement) or not ISSUE_RE.fullmatch(receipt.source_issue):
            raise RequirementIntegrationError("ready-for-integration receipt has invalid identity")
        if (not SHA_RE.fullmatch(receipt.head) or not receipt.change or not receipt.source_branch
                or not receipt.verification_receipt or not receipt.archived_contract):
            raise RequirementIntegrationError("ready-for-integration receipt has invalid provenance")
        if Path(receipt.archived_contract).is_absolute() or Path(receipt.verification_receipt).is_absolute():
            raise RequirementIntegrationError("archive paths must be repository-relative")
        unsigned = asdict(receipt)
        digest = unsigned.pop("digest")
        if digest != _digest(unsigned):
            raise RequirementIntegrationError("ready-for-integration receipt digest does not match its content")
        return receipt


def create_receipt(root: Path, *, requirement: str, source_issue: str, change: str, archived_contract: Path, verification_receipt: Path) -> dict[str, Any]:
    """Create a receipt after archive, without any terminal side effect."""
    if not ISSUE_RE.fullmatch(requirement) or not ISSUE_RE.fullmatch(source_issue):
        raise RequirementIntegrationError("requirement and source issue must be owner/repository#number")
    root = root.resolve()
    archive = archived_contract.resolve()
    verification = verification_receipt.resolve()
    if not archive.is_dir() or not verification.is_file() or not verification.is_relative_to(archive):
        raise RequirementIntegrationError("verification receipt must be inside an existing archived contract")
    if not archive.is_relative_to(root) or not verification.is_relative_to(root):
        raise RequirementIntegrationError("archived contract must be inside the task repository")
    archive_rel = archive.relative_to(root).as_posix()
    verification_rel = verification.relative_to(root).as_posix()
    if not archive_rel.startswith("openspec/changes/archive/") or not archive.name.endswith("-" + change):
        raise RequirementIntegrationError("archive does not identify the exact managed change")
    text = verification.read_text(encoding="utf-8")
    lines = {line.strip() for line in text.splitlines()}
    if "OpenSpec-Verify: PASS" not in lines or not any(line.startswith("Verification-Method:") and line.split(":", 1)[1].strip() for line in lines):
        raise RequirementIntegrationError("archived verification receipt lacks a truthful PASS method")
    head = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "symbolic-ref", "--short", "HEAD")
    if _git(root, "show", f"{head}:{verification_rel}") != text.strip():
        raise RequirementIntegrationError("verification receipt differs from the exact committed child head")
    state_path = root / ".managed-task-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RequirementIntegrationError("managed task identity is missing or invalid") from exc
    if state.get("source_issue") != source_issue or state.get("change") != change:
        raise RequirementIntegrationError("managed task identity does not match the child handoff")
    payload: dict[str, Any] = {
        "version": RECEIPT_VERSION, "requirement": requirement, "source_issue": source_issue,
        "change": change, "source_branch": branch, "head": head,
        "verification_receipt": verification_rel, "archived_contract": archive_rel,
    }
    payload["digest"] = _digest(payload)
    return payload


def write_receipt(path: Path, payload: dict[str, Any]) -> ReadyForIntegrationReceipt:
    receipt = ReadyForIntegrationReceipt.from_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(asdict(receipt), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != encoded:
        raise RequirementIntegrationError(f"refusing to replace a different ready-for-integration receipt: {path}")
    path.write_text(encoded, encoding="utf-8")
    return receipt


def read_receipt(path: Path) -> ReadyForIntegrationReceipt:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RequirementIntegrationError(f"cannot read ready-for-integration receipt {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RequirementIntegrationError("ready-for-integration receipt must be a JSON object")
    return ReadyForIntegrationReceipt.from_payload(payload)


def assemble_candidate(root: Path, *, requirement: str, base: str, receipt_paths: list[Path]) -> dict[str, Any]:
    """Bind an ordered candidate, rejecting stale heads and overlapping paths.

    The caller supplies receipts in semantic dependency order.  This operation
    intentionally stops before writing a worktree or publishing: it is safe to
    retry, and leaves the existing protected worktree/PR authority in charge.
    """
    if not ISSUE_RE.fullmatch(requirement) or not SHA_RE.fullmatch(base):
        raise RequirementIntegrationError("requirement and base are invalid")
    if len(receipt_paths) < 2:
        raise RequirementIntegrationError("shared integration requires at least two child receipts")
    receipts = [read_receipt(path) for path in receipt_paths]
    if any(item.requirement != requirement for item in receipts):
        raise RequirementIntegrationError("all child receipts must belong to the same Requirement")
    identities = [(item.source_issue, item.change) for item in receipts]
    if len(set(identities)) != len(identities) or len({item.head for item in receipts}) != len(receipts):
        raise RequirementIntegrationError("child receipts are ambiguous or duplicate")
    try:
        resolved_base = _git(root, "rev-parse", base)
        _git(root, "cat-file", "-e", f"{base}^{{commit}}")
    except RequirementIntegrationError as exc:
        raise RequirementIntegrationError("candidate base is not an exact resolvable commit") from exc
    if resolved_base != base:
        raise RequirementIntegrationError("candidate base is not an exact resolvable commit")
    claimed: dict[str, str] = {}
    children: list[dict[str, str]] = []
    for receipt, receipt_path in zip(receipts, receipt_paths, strict=True):
        try:
            resolved_head = _git(root, "rev-parse", receipt.head)
            _git(root, "cat-file", "-e", f"{receipt.head}^{{commit}}")
        except RequirementIntegrationError as exc:
            raise RequirementIntegrationError(f"child head is not an exact resolvable commit: {receipt.source_issue}") from exc
        if resolved_head != receipt.head:
            raise RequirementIntegrationError(f"child head is not an exact resolvable commit: {receipt.source_issue}")
        if _git(root, "rev-parse", receipt.source_branch) != receipt.head:
            raise RequirementIntegrationError(f"child branch changed after handoff: {receipt.source_issue}")
        if not _git(root, "show", f"{receipt.head}:{receipt.verification_receipt}"):
            raise RequirementIntegrationError(f"archived verification is absent from child head: {receipt.source_issue}")
        if _git(root, "merge-base", base, receipt.head) != base:
            raise RequirementIntegrationError(f"child head is stale or not based on candidate base: {receipt.source_issue}")
        paths = [item for item in _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", base, receipt.head).splitlines() if item]
        overlap = sorted(path for path in paths if path in claimed)
        if overlap:
            raise RequirementIntegrationError(
                f"child edits overlap ({receipt.source_issue} with {claimed[overlap[0]]}): {', '.join(overlap[:5])}"
            )
        claimed.update({path: receipt.source_issue for path in paths})
        children.append({"source_issue": receipt.source_issue, "change": receipt.change, "head": receipt.head,
                         "receipt": str(receipt_path.resolve()), "digest": receipt.digest})
    unsigned = {"version": 1, "requirement": requirement, "base": base, "children": children}
    return {**unsigned, "digest": _digest(unsigned)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and validate shared Requirement integration evidence.")
    sub = parser.add_subparsers(dest="command", required=True)
    handoff = sub.add_parser("ready", help="write a verified nonterminal child handoff receipt")
    handoff.add_argument("--requirement", required=True)
    handoff.add_argument("--source-issue", required=True)
    handoff.add_argument("--change", required=True)
    handoff.add_argument("--archived-contract", required=True, type=Path)
    handoff.add_argument("--verification-receipt", required=True, type=Path)
    handoff.add_argument("--out", required=True, type=Path)
    assemble = sub.add_parser("assemble", help="bind ordered child heads for a protected integration candidate")
    assemble.add_argument("--requirement", required=True)
    assemble.add_argument("--base", required=True)
    assemble.add_argument("--receipt", required=True, type=Path, action="append")
    assemble.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    try:
        if args.command == "ready":
            payload = create_receipt(root, requirement=args.requirement, source_issue=args.source_issue, change=args.change,
                                     archived_contract=args.archived_contract, verification_receipt=args.verification_receipt)
            write_receipt(args.out, payload)
        else:
            payload = assemble_candidate(root, requirement=args.requirement, base=args.base, receipt_paths=args.receipt)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except RequirementIntegrationError as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
