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
# proposal decision 2 in this change's design.md. `dev-platform/evals/` is
# generic capability eval fixture data required by `tests/test_template_contract.py`
# and `tests/test_capability_manager.py` (it must byte-match `template/dev-platform/evals/`),
# not local/sensitive state, so it also stays; only `.dev-platform.toml` (this
# specific checkout's own operator-opt-in config) and coordination state are
# excluded as genuinely central-checkout-local.
EXCLUDED_PATHS = {
    ".dev-platform.toml",
    ".managed-task-state.json",
    "openspec/changes/archive",
}
# `.managed-task.json` is the per-task Development Backlog provenance receipt
# that `start_managed_task.py` materializes into the *active* (not yet
# archived) change directory it imports -- it necessarily records this
# operator's real source-issue reference (e.g. the concrete Development
# Backlog repository/number) while the task is in flight. That is genuine
# operator/task-tracking state, not product source: once a change is
# archived it moves under the already-excluded `openspec/changes/archive`,
# and a fresh clone never needs an in-flight task's own provenance file to be
# developable/testable. Matched by filename (like `.git`/`__pycache__`)
# rather than a full path so it is excluded under any active change.
EXCLUDED_PARTS = EXCLUDED_PARTS | {".managed-task.json"}
CANONICAL_PRODUCT_REPOSITORY = "lehard/dev-platform"
# Only this repository's own canonical identity is product identity. A
# companion Development Backlog repository, managed-project registry, bot
# account, GitHub Project, or downstream repository is operator state, even
# when the current operator happens to use a real, named repository for it --
# see design.md decision 1 in `finalize-public-snapshot-identity-boundary`.
# Keep this allowlist to exactly the canonical source identity; do not widen
# it back to cover a companion operator repository.
CANONICAL_PRODUCT_REPOSITORIES = {CANONICAL_PRODUCT_REPOSITORY}
OWNER_REFERENCE = re.compile(r"\blehard/[A-Za-z0-9_.-]+\b")
SECRET_PATTERNS = {
    "github_pat": re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    "gitlab_pat": re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
}
# Bounded, versioned schema for an external one-shot cutover policy: private
# repository/compatibility-marker deny data needed only to sanitize the
# pre-cutover source before a fresh-history cutover. This module never
# encodes those private values itself (not even through split literals or
# other self-avoidance tricks) -- see design.md decisions 4/5/6. The policy
# is data, not a plugin framework; keep the schema this small.
CUTOVER_POLICY_VERSION = 1
POLICY_LABEL_RE = re.compile(r"^[a-z][a-z0-9_]*$")
POLICY_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class CutoverPolicyError(ValueError):
    """An explicitly requested external cutover policy could not be trusted."""
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


def public_files(root: Path, *, extra_excluded: frozenset[str] = frozenset()) -> list[Path]:
    """Return the single deterministic product candidate set.

    Do not add an audit-only walk: this set is the sole input for both audit
    and archive construction. `extra_excluded` carries a supplied external
    cutover-policy file's own repository-relative path (when it happens to
    live inside `root`) so that private deny data is never itself packaged.
    """
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and not _excluded(path.relative_to(root), extra_excluded)
    )


def _excluded(relative: Path, extra_excluded: frozenset[str] = frozenset()) -> bool:
    value = relative.as_posix()
    excluded_paths = EXCLUDED_PATHS | extra_excluded
    return bool(set(relative.parts) & EXCLUDED_PARTS) or any(
        value == excluded or value.startswith(f"{excluded}/") for excluded in excluded_paths
    )


def load_cutover_policy(path: Path) -> dict[str, object]:
    """Load and validate an external one-shot cutover policy file.

    Fails closed (raises `CutoverPolicyError`) on anything unreadable,
    malformed, or ambiguous -- see the accepted requirement "External cutover
    policy is explicit and fail-closed". Returns compiled markers plus
    non-sensitive provenance; never returns anything that copies the raw
    policy content back into a generated artifact.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CutoverPolicyError(f"cutover policy is unreadable: {path}") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CutoverPolicyError(f"cutover policy is not valid JSON: {path}") from exc
    if not isinstance(data, dict) or data.get("version") != CUTOVER_POLICY_VERSION:
        raise CutoverPolicyError(f"cutover policy must be a JSON object with version={CUTOVER_POLICY_VERSION}: {path}")
    prohibited_repositories = data.get("prohibited_repositories", {})
    compatibility_markers = data.get("compatibility_markers", {})
    if not isinstance(prohibited_repositories, dict) or not isinstance(compatibility_markers, dict):
        raise CutoverPolicyError(
            f"cutover policy prohibited_repositories/compatibility_markers must be label-keyed objects: {path}"
        )
    for label, value in prohibited_repositories.items():
        if not POLICY_LABEL_RE.match(label) or not isinstance(value, str) or not POLICY_REPOSITORY_RE.match(value):
            raise CutoverPolicyError(f"cutover policy prohibited_repositories entry '{label}' is invalid")
    compiled_markers: dict[str, re.Pattern[str]] = {}
    for label, pattern in compatibility_markers.items():
        if not POLICY_LABEL_RE.match(label) or not isinstance(pattern, str) or not pattern:
            raise CutoverPolicyError(f"cutover policy compatibility_markers entry '{label}' is invalid")
        try:
            compiled_markers[label] = re.compile(pattern)
        except re.error as exc:
            raise CutoverPolicyError(f"cutover policy compatibility_markers entry '{label}' is not a valid pattern: {exc}") from None
    return {
        "prohibited_repositories": dict(prohibited_repositories),
        "compatibility_markers": compiled_markers,
        "provenance": {
            "path_basename": path.name,
            "version": CUTOVER_POLICY_VERSION,
            "digest": hashlib.sha256(raw).hexdigest(),
        },
    }


def policy_extra_excluded(root: Path, policy_path: Path | None) -> frozenset[str]:
    """Exclude a supplied cutover-policy file's own relative path, if inside `root`."""
    if policy_path is None:
        return frozenset()
    resolved = policy_path.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError:
        return frozenset()
    return frozenset({relative.as_posix()})


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


def audit_tree(
    root: Path,
    candidates: list[Path] | None = None,
    *,
    cutover_policy_path: Path | None = None,
) -> dict[str, object]:
    policy = load_cutover_policy(cutover_policy_path) if cutover_policy_path is not None else None
    if candidates is None:
        candidates = public_files(root, extra_excluded=policy_extra_excluded(root, cutover_policy_path))
    prohibited_repositories: dict[str, str] = policy["prohibited_repositories"] if policy else {}
    compatibility_markers: dict[str, re.Pattern[str]] = policy["compatibility_markers"] if policy else {}
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
        # Diagnostics below name only the finding's label/path, never the raw
        # deny value from the external policy -- see design.md decision 5.
        for label, repository in prohibited_repositories.items():
            if repository in text:
                findings["operator_state"].append(
                    f"prohibited repository reference from cutover policy ({label}): {rel}"
                )
        for label, pattern in compatibility_markers.items():
            if pattern.search(text):
                findings["compatibility_markers"].append(
                    f"possible {label} compatibility marker (external cutover policy): {rel}"
                )
    receipt_policy: dict[str, object] = {
        "canonical_product_repositories": sorted(CANONICAL_PRODUCT_REPOSITORIES),
        "excluded": sorted(EXCLUDED_PARTS | EXCLUDED_PATHS),
    }
    if policy is not None:
        receipt_policy["cutover_policy"] = policy["provenance"]
    return {
        "candidate_files": [path.relative_to(root).as_posix() for path in candidates],
        "candidate_sha256": candidate_digest(root, candidates),
        "source_revision": source_revision(root),
        "findings": findings,
        "policy": receipt_policy,
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


def snapshot(root: Path, output: Path, *, cutover_policy_path: Path | None = None) -> dict[str, object]:
    candidates = public_files(root, extra_excluded=policy_extra_excluded(root, cutover_policy_path))
    receipt = audit_tree(root, candidates, cutover_policy_path=cutover_policy_path)
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
    parser.add_argument(
        "--cutover-policy",
        type=Path,
        default=None,
        help=(
            "Path to an explicit external one-shot cutover policy JSON file "
            "(prohibited_repositories/compatibility_markers). Applies to "
            "audit/snapshot only; missing/malformed input fails closed."
        ),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "audit":
        try:
            receipt = audit_tree(root, cutover_policy_path=args.cutover_policy)
        except CutoverPolicyError as exc:
            print(json.dumps({"error": str(exc)}, sort_keys=True))
            return 2
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
        result = snapshot(root, args.output.resolve(), cutover_policy_path=args.cutover_policy)
    except ValueError as exc:
        print(exc)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
