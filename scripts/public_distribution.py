"""Audit and package a deterministic sanitized public Dev Platform snapshot."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROHIBITED_PATHS = ("managed-projects.json",)
GENERIC_SURFACES = (".dev-platform.toml", "copier.yml", "template")
OWNER_DEFAULTS = ("lehard/development-backlog", "dev-platform-bot-lehard", 'project_owner = "lehard"')
SECRET_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)
EXCLUDED_PARTS = {".git", ".claude", ".codex", "__pycache__", ".pytest_cache"}


def public_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and not any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts)
    )


def audit_tree(root: Path) -> dict[str, list[str]]:
    findings = {"operator_state": [], "secrets": []}
    for relative in PROHIBITED_PATHS:
        if (root / relative).exists():
            findings["operator_state"].append(f"prohibited live operator path: {relative}")
    for surface in GENERIC_SURFACES:
        path = root / surface
        paths = [path] if path.is_file() else list(path.rglob("*")) if path.exists() else []
        for candidate in paths:
            if not candidate.is_file():
                continue
            try:
                text = candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            rel = candidate.relative_to(root)
            for value in OWNER_DEFAULTS:
                if value in text:
                    findings["operator_state"].append(f"owner default in generic surface: {rel}: {value}")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    findings["secrets"].append(f"possible credential in current tree: {rel} ({pattern.pattern})")
    return findings


def snapshot(root: Path, output: Path) -> dict[str, object]:
    findings = audit_tree(root)
    if findings["operator_state"] or findings["secrets"]:
        raise ValueError(json.dumps(findings, sort_keys=True))
    digest = hashlib.sha256()
    with tarfile.open(output, "w") as archive:
        for path in public_files(root):
            relative = path.relative_to(root)
            content = path.read_bytes()
            digest.update(str(relative).encode() + b"\0" + content)
            info = tarfile.TarInfo(str(relative))
            info.size = len(content)
            info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
    return {"snapshot": str(output), "sha256": digest.hexdigest(), "files": len(public_files(root))}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and prepare a deterministic public distribution snapshot.")
    parser.add_argument("command", choices=("audit", "snapshot"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    findings = audit_tree(root)
    if args.command == "audit":
        print(json.dumps(findings, sort_keys=True))
        return 2 if findings["operator_state"] or findings["secrets"] else 0
    if args.output is None:
        parser.error("snapshot requires --output")
    try:
        result = snapshot(root, args.output.resolve())
    except ValueError as exc:
        print(exc)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
