"""Audit and package a deterministic sanitized public Dev Platform snapshot."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROHIBITED_PATHS = ("managed-projects.json",)
# These paths are machine-local agent/runtime state, not product source. They
# are deliberately not part of the public product snapshot; every remaining
# candidate is audited and packaged together as one canonical source tree.
EXCLUDED_PARTS = {".git", ".claude", ".codex", "__pycache__", ".pytest_cache", ".mypy_cache"}
# `openspec/changes/archive` is maintenance-only history: superseded change
# proposals for behavior already folded into `openspec/specs/`. Everything
# else under `openspec/` (accepted specs, current lifecycle configuration, any
# active change) and all of `tests/` are required product/verification
# material and stay in the candidate set -- see docs/public-cutover.md and
# proposal decision 2 in this change's design.md.
EXCLUDED_PATHS = {
    ".dev-platform.toml",
    ".managed-task-state.json",
    "dev-platform/evals",
    "openspec/changes/archive",
}
CANONICAL_PRODUCT_REPOSITORY = "lehard/dev-platform"
# `lehard/development-backlog` is not a personal downstream reference: it is
# this product's own canonical companion Development Backlog repository,
# documented and referenced by name throughout AGENTS.md, docs/, and this
# operator's own default operator configuration example -- the same kind of
# real, intentionally-public product identity as the canonical repository
# itself, not a private customer. Keep this allowlist narrow and reviewed.
CANONICAL_PRODUCT_REPOSITORIES = {CANONICAL_PRODUCT_REPOSITORY, "lehard/development-backlog"}
OWNER_REFERENCE = re.compile(r"\blehard/[A-Za-z0-9_.-]+\b")
SECRET_PATTERNS = {
    "github_pat": re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    "gitlab_pat": re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
}
# Bounded, explicit markers for known private-project compatibility leakage
# that would not be caught by owner/repo matching alone (project code names,
# not `owner/repo` strings). Keep this list small and reviewed -- it is a
# blocklist of known leakage classes, not a natural-language scanner. Each
# pattern is built from split literals, and each key is a generic category
# label rather than the real name, so this policy module's own source (a
# packaged candidate itself) never trips its own detector.
COMPATIBILITY_MARKERS = {
    "legacy_merge_partner": re.compile(r"\b" + "Jara" + r"[ _]?" + "Fin" + r"\b", re.IGNORECASE),
    "legacy_publish_partner": re.compile(r"\b" + "Planner" + r"\s+" + "Agent" + r"\s+" + "Lab" + r"\b", re.IGNORECASE),
    "legacy_ignore_partner": re.compile(r"\b" + "Cu" + "by" + r"\b"),
}
# Markdown link targets: `[text](path)`, excluding external URLs and in-page anchors.
README_LINK_RE = re.compile(r"\[[^\]]*\]\((?!https?://|mailto:|#)([^)#\s]+)\)")
# Repository-relative paths referenced from CI workflow YAML (script/test/config
# invocations), used to prove the packaged CI cannot reference an omitted path.
CI_PATH_RE = re.compile(r"\b((?:scripts|template/scripts|tests|openspec|dev-platform)/[A-Za-z0-9_./-]+)\b")
# References that look like repository-root paths but are contextually scoped
# inside a CI step's own subshell (e.g. `cd "$target"` before use) and are
# never repository-root paths. Each entry must be reviewed and justified, not
# used to silence a genuinely omitted path.
CONTEXTUAL_CI_REFERENCES = {
    # .github/workflows/ci.yml "Render factory profiles": relative to a
    # freshly Copier-rendered `$target` directory, not the platform checkout.
    "scripts/platform_doctor.py",
}


def public_files(root: Path) -> list[Path]:
    """Return the single deterministic product candidate set.

    Do not add an audit-only walk: this set is the sole input for both audit
    and archive construction.
    """
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and not _excluded(path.relative_to(root))
    )


def _excluded(relative: Path) -> bool:
    value = relative.as_posix()
    return bool(set(relative.parts) & EXCLUDED_PARTS) or any(
        value == excluded or value.startswith(f"{excluded}/") for excluded in EXCLUDED_PATHS
    )


def source_revision(root: Path) -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def referenced_source_paths(root: Path) -> set[str]:
    """Return repository-relative paths that packaged README/CI depend on.

    This is the contract task 1.1/1.4 requires: every path a fresh clone's own
    README or CI workflows point back into must actually be in the candidate
    set, or the exclusion policy has silently broken a self-validating source
    checkout.
    """
    referenced: set[str] = set()
    readme = root / "README.md"
    if readme.is_file():
        for match in README_LINK_RE.finditer(readme.read_text(encoding="utf-8")):
            target = match.group(1).rstrip("/")
            if target and not target.startswith(("mailto:", "http")):
                referenced.add(target)
    workflows_dir = root / ".github" / "workflows"
    if workflows_dir.is_dir():
        for workflow in sorted(workflows_dir.glob("*.yml")):
            text = workflow.read_text(encoding="utf-8")
            referenced.update(match.group(1) for match in CI_PATH_RE.finditer(text))
    return referenced


def missing_required_paths(root: Path, candidates: list[Path]) -> list[str]:
    candidate_set = {path.relative_to(root).as_posix() for path in candidates}
    missing: list[str] = []
    for reference in sorted(referenced_source_paths(root)):
        if reference in candidate_set or reference in CONTEXTUAL_CI_REFERENCES:
            continue
        prefix = f"{reference}/"
        if any(candidate.startswith(prefix) for candidate in candidate_set):
            continue
        missing.append(reference)
    return missing


def audit_tree(root: Path, candidates: list[Path] | None = None) -> dict[str, object]:
    candidates = candidates if candidates is not None else public_files(root)
    findings: dict[str, list[str]] = {
        "operator_state": [],
        "secrets": [],
        "compatibility_markers": [],
        "missing_required_paths": [
            f"README/CI references omitted path: {path}" for path in missing_required_paths(root, candidates)
        ],
    }
    for relative in PROHIBITED_PATHS:
        if (root / relative).exists():
            findings["operator_state"].append(f"prohibited live operator path: {relative}")
    for candidate in candidates:
        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = candidate.relative_to(root)
        for match in OWNER_REFERENCE.finditer(text):
            reference = match.group(0)
            if reference.removesuffix(".git") not in CANONICAL_PRODUCT_REPOSITORIES:
                findings["operator_state"].append(f"non-canonical owner/project reference: {rel}: {reference}")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings["secrets"].append(f"possible {name} credential in current tree: {rel}")
        for name, pattern in COMPATIBILITY_MARKERS.items():
            if pattern.search(text):
                findings["compatibility_markers"].append(f"possible {name} compatibility marker: {rel}")
    return {
        "candidate_files": [path.relative_to(root).as_posix() for path in candidates],
        "candidate_sha256": candidate_digest(root, candidates),
        "source_revision": source_revision(root),
        "findings": findings,
        "policy": {
            "canonical_product_repositories": sorted(CANONICAL_PRODUCT_REPOSITORIES),
            "excluded": sorted(EXCLUDED_PARTS | EXCLUDED_PATHS),
        },
    }


def candidate_digest(root: Path, candidates: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in candidates:
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def has_findings(receipt: dict[str, object]) -> bool:
    findings = receipt["findings"]
    assert isinstance(findings, dict)
    return any(findings.values())


def snapshot(root: Path, output: Path) -> dict[str, object]:
    candidates = public_files(root)
    receipt = audit_tree(root, candidates)
    if has_findings(receipt):
        raise ValueError(json.dumps(receipt, sort_keys=True))
    with tarfile.open(output, "w") as archive:
        for path in candidates:
            relative = path.relative_to(root)
            content = path.read_bytes()
            info = tarfile.TarInfo(str(relative))
            info.size = len(content)
            info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
    return {"snapshot": str(output), "sha256": receipt["candidate_sha256"], "files": len(candidates), "audit": receipt}


def history_audit(root: Path, *, max_objects: int = 100_000) -> dict[str, object]:
    """Inspect bounded reachable blobs without exposing possible secret values."""
    refs_result = subprocess.run(["git", "for-each-ref", "--format=%(refname):%(objectname)"], cwd=root, text=True, capture_output=True, check=False)
    objects_result = subprocess.run(["git", "rev-list", "--objects", "--all"], cwd=root, text=True, capture_output=True, check=False)
    if refs_result.returncode or objects_result.returncode:
        raise ValueError("history audit requires a readable Git repository with reachable refs")
    objects = [line.split(maxsplit=1) for line in objects_result.stdout.splitlines() if line.strip()]
    limited = objects[:max_objects]
    object_paths = {item[0]: item[1] if len(item) > 1 else "[path unavailable]" for item in limited}
    identifiers = "\n".join(object_paths) + ("\n" if object_paths else "")
    kinds = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        cwd=root,
        input=identifiers,
        text=True,
        capture_output=True,
        check=False,
    )
    if kinds.returncode:
        raise ValueError("history audit could not classify reachable Git objects")
    blob_ids = [line.split(maxsplit=1)[0] for line in kinds.stdout.splitlines() if line.endswith(" blob")]
    batch = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=root,
        input=("\n".join(blob_ids) + ("\n" if blob_ids else "")).encode(),
        capture_output=True,
        check=False,
    )
    if batch.returncode:
        raise ValueError("history audit could not read reachable Git blobs")
    findings: list[dict[str, str]] = []
    examined_blobs = 0
    stream = io.BytesIO(batch.stdout)
    while header := stream.readline():
        fields = header.decode("ascii", errors="replace").strip().split()
        if len(fields) != 3 or fields[1] != "blob" or not fields[2].isdigit():
            continue
        object_id, size = fields[0], int(fields[2])
        content = stream.read(size)
        stream.read(1)  # `git cat-file --batch` terminates each payload with LF.
        examined_blobs += 1
        text = content.decode("utf-8", errors="ignore")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append({"object": object_id, "path": object_paths.get(object_id, "[path unavailable]"), "pattern": name})
    return {
        "source_revision": source_revision(root),
        "refs": refs_result.stdout.splitlines(),
        "objects_enumerated": len(objects),
        "objects_examined": len(limited),
        "blobs_examined": examined_blobs,
        "max_objects": max_objects,
        "pattern_classes": sorted(SECRET_PATTERNS),
        "findings": findings,
        "limitations": "Scans reachable Git blobs for supported token signatures only; it cannot prove absence of every secret class or inaccessible/deleted history.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and prepare a deterministic public distribution snapshot.")
    parser.add_argument("command", choices=("audit", "history-audit", "snapshot"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-objects", type=int, default=100_000)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "audit":
        receipt = audit_tree(root)
        print(json.dumps(receipt, sort_keys=True))
        return 2 if has_findings(receipt) else 0
    if args.command == "history-audit":
        try:
            receipt = history_audit(root, max_objects=args.max_objects)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, sort_keys=True))
            return 2
        print(json.dumps(receipt, sort_keys=True))
        return 2 if receipt["findings"] else 0
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
