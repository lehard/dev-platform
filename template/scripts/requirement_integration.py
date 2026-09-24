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
import shutil
import subprocess
import tomllib
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
    try:
        provenance = json.loads((archive / ".managed-task.json").read_text(encoding="utf-8"))
        checks = json.loads((archive / "automated-checks.json").read_text(encoding="utf-8"))
        tasks = (archive / "tasks.md").read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        raise RequirementIntegrationError("archived managed provenance, tasks or automated checks are unavailable") from exc
    if provenance.get("source_issue") != source_issue or provenance.get("change") != change:
        raise RequirementIntegrationError("archived managed provenance does not match the child")
    task_lines = [line.strip() for line in tasks.splitlines() if re.match(r"^\s*-\s*\[[ xX]\]", line)]
    if not task_lines or any(re.match(r"^-\s*\[ \]", line) for line in task_lines):
        raise RequirementIntegrationError("archived managed tasks are incomplete")
    if (checks.get("outcome") != "success" or not isinstance(checks.get("executed_commands"), list)
            or not checks["executed_commands"] or any(command.get("outcome") != "success" for command in checks["executed_commands"])):
        raise RequirementIntegrationError("archived automated checks do not prove success")
    text = verification.read_text(encoding="utf-8")
    lines = {line.strip() for line in text.splitlines()}
    if "OpenSpec-Verify: PASS" not in lines or not any(line.startswith("Verification-Method:") and line.split(":", 1)[1].strip() for line in lines):
        raise RequirementIntegrationError("archived verification receipt lacks a truthful PASS method")
    head = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "symbolic-ref", "--short", "HEAD")
    for relative in (verification_rel, f"{archive_rel}/.managed-task.json", f"{archive_rel}/automated-checks.json", f"{archive_rel}/tasks.md"):
        if _git(root, "show", f"{head}:{relative}") != (root / relative).read_text(encoding="utf-8").strip():
            raise RequirementIntegrationError(f"archived evidence differs from the exact committed child head: {relative}")
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


def require_independent_publication_exception(root: Path, delivery: Any) -> str | None:
    """Require a committed reason before separately publishing a linked child."""
    import managed_task
    import requirement_intake

    source_issue = getattr(delivery, "source_issue", None)
    archive = getattr(delivery, "path", None)
    if not isinstance(source_issue, str) or not isinstance(archive, Path):
        raise RequirementIntegrationError("managed publication has no canonical source and archive identity")
    issue = managed_task.fetch_issue(root, *managed_task.issue_ref(source_issue))
    body = str(issue.get("body") or "")
    parents = re.findall(r"^Requirement: (\S+/\S+#\d+)\s*$", body, re.MULTILINE)
    if not parents:
        return None
    if len(parents) != 1 or requirement_intake.CHILD_LABEL not in managed_task.issue_labels(issue):
        raise RequirementIntegrationError("linked child has ambiguous Requirement provenance")
    parent = managed_task.fetch_issue(root, *managed_task.issue_ref(parents[0]))
    if (requirement_intake.REQUIREMENT_LABEL not in managed_task.issue_labels(parent)
            or source_issue not in requirement_intake.parse_requirement_body(str(parent.get("body") or ""))["children"]):
        raise RequirementIntegrationError("linked child is not reciprocally listed by its Requirement")
    verification = archive / "verification.md"
    try:
        lines = verification.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RequirementIntegrationError("linked child has no archived verification receipt") from exc
    reasons = [line.split(":", 1)[1].strip() for line in lines if line.startswith("Requirement-Integration-Exception:")]
    if len(reasons) != 1 or len(reasons[0]) < 12:
        raise RequirementIntegrationError(
            f"{source_issue} is linked to {parents[0]}; independent publication requires one "
            "'Requirement-Integration-Exception: <reason>' line in archived verification.md"
        )
    relative = verification.resolve().relative_to(root.resolve()).as_posix()
    if _git(root, "show", f"HEAD:{relative}") != verification.read_text(encoding="utf-8").strip():
        raise RequirementIntegrationError("independent-publication reason is not committed at the exact head")
    return reasons[0]


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
    claimed: dict[str, tuple[str, str]] = {}
    children: list[dict[str, str]] = []
    replayed = False
    for receipt in receipts:
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
        common_base = _git(root, "merge-base", base, receipt.head)
        if not common_base:
            raise RequirementIntegrationError(f"child head has no common base with candidate: {receipt.source_issue}")
        previous_head = children[-1]["head"] if children else None
        dependent = previous_head is not None and subprocess.run(
            ["git", "merge-base", "--is-ancestor", previous_head, receipt.head], cwd=root, capture_output=True,
        ).returncode == 0
        delta_base = previous_head if dependent else common_base
        replayed |= common_base != base
        paths = [item for item in _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", delta_base, receipt.head).splitlines() if item]
        overlap = sorted(
            path for path in paths if path in claimed and subprocess.run(
                ["git", "merge-base", "--is-ancestor", claimed[path][1], receipt.head], cwd=root, capture_output=True,
            ).returncode != 0
        )
        if overlap:
            raise RequirementIntegrationError(
                f"child edits overlap ({receipt.source_issue} with {claimed[overlap[0]][0]}): {', '.join(overlap[:5])}"
            )
        claimed.update({path: (receipt.source_issue, receipt.head) for path in paths})
        children.append({"source_issue": receipt.source_issue, "change": receipt.change, "source_branch": receipt.source_branch, "head": receipt.head,
                         "delta_base": delta_base, "digest": receipt.digest})
    unsigned = {"version": 1, "requirement": requirement, "base": base, "children": children}
    if replayed:
        unsigned["generation"] = base[:12]
    return {**unsigned, "digest": _digest(unsigned)}


def _registered_worktrees(root: Path) -> dict[Path, str]:
    listing = _git(root, "worktree", "list", "--porcelain")
    result: dict[Path, str] = {}
    path: Path | None = None
    for line in [*listing.splitlines(), ""]:
        if line.startswith("worktree "):
            path = Path(line[9:]).resolve()
        elif line.startswith("branch refs/heads/") and path is not None:
            result[path] = line.removeprefix("branch refs/heads/")
        elif not line:
            path = None
    return result


def _candidate_manifest_path(requirement: str) -> Path:
    if ISSUE_RE.fullmatch(requirement) is None:
        raise RequirementIntegrationError("Requirement identity is invalid")
    return Path("dev-platform/requirement-integrations") / (_candidate_slug(requirement) + ".json")


def _candidate_slug(requirement: str, generation: str | None = None) -> str:
    if ISSUE_RE.fullmatch(requirement) is None:
        raise RequirementIntegrationError("Requirement identity is invalid")
    number = requirement.rsplit("#", 1)[1]
    digest = hashlib.sha256(requirement.lower().encode("utf-8")).hexdigest()[:12]
    slug = f"requirement-{number}-{digest}-integration"
    if generation is not None:
        if not re.fullmatch(r"[0-9a-f]{12}", generation):
            raise RequirementIntegrationError("candidate generation is invalid")
        slug += f"-{generation}"
    return slug


def _provision_local_contract(root: Path, worktree: Path) -> None:
    source = root / ".dev-platform.toml"
    if not source.is_file():
        return
    ignored = subprocess.run(["git", "check-ignore", "-q", ".dev-platform.toml"], cwd=root).returncode == 0
    if not ignored:
        if not (worktree / ".dev-platform.toml").is_file():
            raise RequirementIntegrationError("tracked source contract is absent from candidate")
        return
    target = worktree / ".dev-platform.toml"
    if target.exists() or target.is_symlink():
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            raise RequirementIntegrationError("candidate local source contract differs from integration checkout")
        return
    shutil.copy2(source, target)


def _project_topology(root: Path) -> tuple[str, Path]:
    config_path = root / ".dev-platform.toml"
    if config_path.is_file():
        try:
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RequirementIntegrationError(f"cannot read platform source contract: {exc}") from exc
    else:
        config = {}
    main_branch = config.get("main_branch", "main")
    configured = config.get("paths", {}).get("worktrees", ".claude/worktrees")
    if not isinstance(main_branch, str) or not main_branch or not isinstance(configured, str):
        raise RequirementIntegrationError("platform topology is invalid")
    configured_path = Path(configured)
    if configured_path.is_absolute() or ".." in configured_path.parts:
        raise RequirementIntegrationError("worktree root must be repository-relative")
    return main_branch, (root / configured_path).resolve()


def _child_commit_message(child: dict[str, str]) -> str:
    return (f"Integrate {child['source_issue']} ({child['change']})\n\n"
            f"Requirement-Child: {child['source_issue']}\n"
            f"Requirement-Head: {child['head']}\n"
            f"Requirement-Delta-Base: {child['delta_base']}\n"
            f"Requirement-Receipt: {child['digest']}")


def compose_candidate(root: Path, *, manifest: dict[str, Any], receipt_paths: list[Path], worktree: Path, branch: str) -> dict[str, Any]:
    """Create or resume an owned candidate worktree from exact child trees.

    No existing worktree or branch is removed, reset, cleaned, or overwritten.
    A partial uncommitted application is reported for explicit recovery.
    """
    root = root.resolve()
    worktree = worktree.resolve()
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise RequirementIntegrationError("candidate manifest has an unsupported version")
    unsigned = {key: value for key, value in manifest.items() if key != "digest"}
    if manifest.get("digest") != _digest(unsigned):
        raise RequirementIntegrationError("candidate manifest digest does not match its content")
    requirement = manifest.get("requirement")
    if not isinstance(requirement, str) or not ISSUE_RE.fullmatch(requirement):
        raise RequirementIntegrationError("candidate Requirement is invalid")
    expected_branch = "agent/" + _candidate_slug(requirement, manifest.get("generation"))
    if branch != expected_branch:
        raise RequirementIntegrationError(f"candidate branch must be {expected_branch}")
    main_branch, allowed_parent = _project_topology(root)
    if _registered_worktrees(root).get(root) != main_branch:
        raise RequirementIntegrationError("compose must run from the shared integration checkout on main")
    if worktree.parent != allowed_parent or worktree.name != expected_branch.removeprefix("agent/"):
        raise RequirementIntegrationError("candidate worktree must be its dedicated configured worktree path")
    base = manifest.get("base")
    children = manifest.get("children")
    if not isinstance(base, str) or not SHA_RE.fullmatch(base) or not isinstance(children, list) or len(children) < 2:
        raise RequirementIntegrationError("candidate base or child list is invalid")
    has_origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, capture_output=True).returncode == 0
    if has_origin:
        _git(root, "fetch", "origin", main_branch)
    authoritative = _git(root, "rev-parse", f"refs/remotes/origin/{main_branch}" if has_origin else f"refs/heads/{main_branch}")
    if authoritative != base:
        raise RequirementIntegrationError("authoritative main changed after candidate assembly")
    if assemble_candidate(root, requirement=requirement, base=base, receipt_paths=receipt_paths) != manifest:
        raise RequirementIntegrationError("child handoff evidence changed after candidate assembly")
    registered = _registered_worktrees(root)
    if worktree in registered:
        if registered[worktree] != branch:
            raise RequirementIntegrationError("candidate worktree belongs to another branch")
    else:
        if worktree.exists():
            raise RequirementIntegrationError("candidate path exists but is not a registered worktree")
        branch_exists = subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/heads/" + branch], cwd=root)
        if branch_exists.returncode == 0:
            raise RequirementIntegrationError("candidate branch exists outside its dedicated worktree")
        if branch_exists.returncode != 1:
            raise RequirementIntegrationError("cannot inspect candidate branch")
        worktree.parent.mkdir(parents=True, exist_ok=True)
        _git(root, "worktree", "add", "-b", branch, str(worktree), base)
    _provision_local_contract(root, worktree)
    if _git(worktree, "status", "--porcelain"):
        raise RequirementIntegrationError("candidate worktree has uncommitted changes; refusing takeover")
    commits = _git(worktree, "rev-list", "--reverse", f"{base}..HEAD").splitlines()
    if len(commits) > len(children) + 1:
        raise RequirementIntegrationError("candidate branch has unexpected commits")
    for index, commit in enumerate(commits[:len(children)]):
        child = children[index]
        if not isinstance(child, dict) or _git(worktree, "show", "-s", "--format=%B", commit) != _child_commit_message(child):
            raise RequirementIntegrationError("candidate branch has unexpected child provenance or order")
        previous = base if index == 0 else commits[index - 1]
        if _git(worktree, "diff", "--binary", previous, commit) != _git(root, "diff", "--binary", child["delta_base"], child["head"]):
            raise RequirementIntegrationError("candidate child commit differs from its exact source tree change")
    if len(commits) == len(children) + 1:
        expected_path = _candidate_manifest_path(requirement)
        if _git(worktree, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD") != expected_path.as_posix():
            raise RequirementIntegrationError("candidate manifest commit has unexpected changes")
        if _git(worktree, "show", "-s", "--format=%B", "HEAD") != f"Bind integrated Requirement {requirement} candidate":
            raise RequirementIntegrationError("candidate manifest commit has unexpected provenance")
        existing = _git(worktree, "show", f"HEAD:{expected_path.as_posix()}")
        expected = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        if existing != expected:
            raise RequirementIntegrationError("candidate branch has a different committed integration manifest")
        return {"worktree": str(worktree), "branch": branch, "head": _git(worktree, "rev-parse", "HEAD"), "resumed": True}
    for child in children[len(commits):]:
        if not isinstance(child, dict) or not SHA_RE.fullmatch(str(child.get("head", ""))):
            raise RequirementIntegrationError("candidate child provenance is malformed")
        if _git(root, "rev-parse", str(child.get("source_branch", ""))) != child["head"]:
            raise RequirementIntegrationError(f"child branch changed before composition: {child.get('source_issue')}")
        patch = subprocess.run(
            ["git", "diff", "--binary", child["delta_base"], child["head"]], cwd=root, capture_output=True, check=True,
        ).stdout
        if not patch:
            raise RequirementIntegrationError(f"child has no tree change: {child['source_issue']}")
        applied = subprocess.run(["git", "apply", "--index", "-"], cwd=worktree, input=patch, capture_output=True)
        if applied.returncode:
            raise RequirementIntegrationError(
                f"candidate application failed for {child['source_issue']}: {applied.stderr.decode(errors='replace').strip()}"
            )
        _git(worktree, "commit", "-m", _child_commit_message(child))
    manifest_path = worktree / _candidate_manifest_path(requirement)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _git(worktree, "add", str(manifest_path.relative_to(worktree)))
    _git(worktree, "commit", "-m", f"Bind integrated Requirement {requirement} candidate")
    return {"worktree": str(worktree), "branch": branch, "head": _git(worktree, "rev-parse", "HEAD"), "resumed": False}


def _validate_candidate_checkout(root: Path, manifest: dict[str, Any]) -> tuple[str, str]:
    requirement = manifest.get("requirement")
    if not isinstance(requirement, str) or not ISSUE_RE.fullmatch(requirement):
        raise RequirementIntegrationError("candidate Requirement identity is invalid")
    unsigned = {key: value for key, value in manifest.items() if key != "digest"}
    if manifest.get("digest") != _digest(unsigned):
        raise RequirementIntegrationError("candidate manifest digest is invalid")
    base = manifest.get("base")
    children = manifest.get("children")
    if not isinstance(base, str) or not SHA_RE.fullmatch(base) or not isinstance(children, list) or len(children) < 2:
        raise RequirementIntegrationError("candidate history manifest is malformed")
    branch = "agent/" + _candidate_slug(requirement, manifest.get("generation"))
    if _git(root, "symbolic-ref", "--short", "HEAD") != branch:
        raise RequirementIntegrationError("candidate checkout is not on its exact integration branch")
    path = _candidate_manifest_path(requirement)
    try:
        committed = json.loads(_git(root, "show", f"HEAD:{path.as_posix()}"))
    except (RequirementIntegrationError, json.JSONDecodeError) as exc:
        raise RequirementIntegrationError("candidate manifest is not committed at the exact branch head") from exc
    if committed != manifest or json.loads((root / path).read_text(encoding="utf-8")) != manifest:
        raise RequirementIntegrationError("candidate checkout does not match its committed manifest")
    commits = _git(root, "rev-list", "--reverse", f"{base}..HEAD").splitlines()
    if len(commits) != len(children) + 1:
        raise RequirementIntegrationError("candidate history does not contain every exact child and manifest commit")
    for index, child in enumerate(children):
        commit = commits[index]
        previous = base if index == 0 else commits[index - 1]
        if (not isinstance(child, dict) or _git(root, "show", "-s", "--format=%B", commit) != _child_commit_message(child)
                or _git(root, "diff", "--binary", previous, commit) != _git(root, "diff", "--binary", child["delta_base"], child["head"])):
            raise RequirementIntegrationError("candidate history differs from exact child provenance")
    if (_git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD") != path.as_posix()
            or _git(root, "show", "-s", "--format=%B", "HEAD") != f"Bind integrated Requirement {requirement} candidate"):
        raise RequirementIntegrationError("candidate manifest commit has unexpected content")
    if _git(root, "status", "--porcelain"):
        raise RequirementIntegrationError("candidate worktree has uncommitted changes")
    return branch, _git(root, "rev-parse", "HEAD")


def _verify_parent_links(integration: Path, manifest: dict[str, Any]) -> None:
    import requirement_intake

    requirement = manifest["requirement"]
    parent = requirement_intake.fetch_issue(integration, *requirement_intake.issue_ref(requirement))
    if requirement_intake.REQUIREMENT_LABEL not in requirement_intake.managed_task.issue_labels(parent):
        raise RequirementIntegrationError("integration parent is not a Requirement")
    linked = requirement_intake.parse_requirement_body(str(parent.get("body") or ""))["children"]
    for child in manifest["children"]:
        source = child["source_issue"]
        if source not in linked:
            raise RequirementIntegrationError(f"candidate child is not linked to Requirement: {source}")
        issue = requirement_intake.fetch_issue(integration, *requirement_intake.issue_ref(source))
        if requirement_intake.CHILD_LABEL not in requirement_intake.managed_task.issue_labels(issue):
            raise RequirementIntegrationError(f"candidate child lacks internal-change identity: {source}")


def _run_full_checks(root: Path) -> None:
    commands = [
        ["python3", "-m", "compileall", "-q", "template/scripts", "scripts"],
        ["python3", "scripts/managed_projects.py", "validate"],
        ["python3", "scripts/run_test_groups.py", "--all"],
        ["python3", "template/scripts/openspec_lifecycle.py", "check"],
    ]
    for command in commands:
        print("Requirement integration validation:", " ".join(command), flush=True)
        result = subprocess.run(command, cwd=root)
        if result.returncode:
            raise RequirementIntegrationError(f"full candidate validation failed: {' '.join(command)} (exit {result.returncode})")


def _reconcile_exact_merged(root: Path, integration: Path, manifest: dict[str, Any], branch: str, head: str) -> dict[str, Any] | None:
    from _platform_common import github_cli_env, read_platform_config
    from integration_state import serialized_integration
    from managed_project_status import reconcile as reconcile_project
    from publication_state import find_exact_head_pr
    from finish_task import sync_after_remote_pr_merge

    config = read_platform_config(root)
    main_branch = str(config.get("main_branch", "main"))
    env = github_cli_env(root)
    if env is None:
        raise RequirementIntegrationError("GitHub authentication is required to prove exact merged PR state")
    lookup = find_exact_head_pr(root, env, branch, main_branch, head)
    if not lookup.available:
        raise RequirementIntegrationError("exact PR state is unavailable; no terminal status was changed")
    if lookup.exact_merged is None:
        return None
    with serialized_integration(integration, config, 60.0):
        sync_after_remote_pr_merge(root, integration, config, main_branch)
        _verify_parent_links(integration, manifest)
        for child in manifest["children"]:
            reconcile_project(integration, "Done", source_issue=child["source_issue"])
    return {"requirement": manifest["requirement"], "branch": branch, "head": head,
            "pr": lookup.exact_merged.get("url"), "status": "merged-and-reconciled",
            "children": [child["source_issue"] for child in manifest["children"]]}


def publish_candidate(root: Path, *, manifest: dict[str, Any], receipt_paths: list[Path], title: str | None = None) -> dict[str, Any]:
    """Validate and publish one shared candidate through the protected PR primitive."""
    from _platform_common import main_root, pr_merge_mode, publish_mode, read_platform_config

    root = root.resolve()
    integration = main_root().resolve()
    config = read_platform_config(root)
    if publish_mode(config) != "pr":
        raise RequirementIntegrationError("shared Requirement integration requires protected PR publication")
    branch, head = _validate_candidate_checkout(root, manifest)
    merged = _reconcile_exact_merged(root, integration, manifest, branch, head)
    if merged is not None:
        return merged
    composed = compose_candidate(integration, manifest=manifest, receipt_paths=receipt_paths,
                                 worktree=root, branch=branch)
    if composed["head"] != head or not composed["resumed"]:
        raise RequirementIntegrationError("candidate head changed before publication")
    _verify_parent_links(integration, manifest)
    _run_full_checks(root)
    # Reobserve every exact input after potentially long validation, before a
    # push or PR mutation. Existing exact-head PRs are resumed by the existing
    # publisher; a changed source or main stops at this gate.
    composed = compose_candidate(integration, manifest=manifest, receipt_paths=receipt_paths,
                                 worktree=root, branch=branch)
    if composed["head"] != head:
        raise RequirementIntegrationError("candidate head changed after validation")
    command = ["python3", "scripts/project_publish.py", "--mode", "pr",
               "--shared-manifest", _candidate_manifest_path(manifest["requirement"]).as_posix()]
    if title:
        command += ["--title", title]
    command += ["--body", f"Shared Requirement integration for {manifest['requirement']}\n\nExact candidate: {head}\nManifest: {_candidate_manifest_path(manifest['requirement'])}"]
    result = subprocess.run(command, cwd=root)
    if result.returncode:
        raise RequirementIntegrationError(f"protected PR publication did not complete (exit {result.returncode})")
    merged = _reconcile_exact_merged(root, integration, manifest, branch, head)
    if merged is not None:
        return merged
    if pr_merge_mode(config) == "manual":
        return {"requirement": manifest["requirement"], "branch": branch, "head": head,
                "status": "in-review", "children": [child["source_issue"] for child in manifest["children"]]}
    raise RequirementIntegrationError("publisher returned without an exact merged PR; no terminal status was changed")


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
    compose = sub.add_parser("compose", help="create or resume the exact combined candidate in its dedicated worktree")
    compose.add_argument("--manifest", required=True, type=Path)
    compose.add_argument("--worktree", required=True, type=Path)
    compose.add_argument("--branch", required=True)
    compose.add_argument("--receipt", required=True, type=Path, action="append")
    publish = sub.add_parser("publish", help="full-check and publish one exact shared candidate through a protected PR")
    publish.add_argument("--manifest", required=True, type=Path)
    publish.add_argument("--receipt", type=Path, action="append", default=[])
    publish.add_argument("--title")
    recover = sub.add_parser("recover", help="compose and publish a new generation from current main and exact child receipts")
    recover.add_argument("--requirement", required=True)
    recover.add_argument("--receipt", required=True, type=Path, action="append")
    recover.add_argument("--title")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    try:
        if args.command == "ready":
            payload = create_receipt(root, requirement=args.requirement, source_issue=args.source_issue, change=args.change,
                                     archived_contract=args.archived_contract, verification_receipt=args.verification_receipt)
            write_receipt(args.out, payload)
        elif args.command == "assemble":
            payload = assemble_candidate(root, requirement=args.requirement, base=args.base, receipt_paths=args.receipt)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            if args.out.exists() and args.out.read_text(encoding="utf-8") != encoded:
                raise RequirementIntegrationError("refusing to replace a different candidate manifest")
            args.out.write_text(encoded, encoding="utf-8")
        elif args.command == "compose":
            payload = compose_candidate(root, manifest=json.loads(args.manifest.read_text(encoding="utf-8")),
                                        receipt_paths=args.receipt, worktree=args.worktree, branch=args.branch)
        elif args.command == "publish":
            payload = publish_candidate(root, manifest=json.loads(args.manifest.read_text(encoding="utf-8")),
                                        receipt_paths=args.receipt, title=args.title)
        else:
            main_branch, worktree_parent = _project_topology(root)
            if _registered_worktrees(root).get(root) != main_branch or _git(root, "status", "--porcelain"):
                raise RequirementIntegrationError("recovery requires a clean shared integration checkout on main")
            base = _git(root, "rev-parse", "HEAD")
            manifest = assemble_candidate(root, requirement=args.requirement, base=base, receipt_paths=args.receipt)
            slug = _candidate_slug(args.requirement, manifest.get("generation"))
            candidate = worktree_parent / slug
            compose_candidate(root, manifest=manifest, receipt_paths=args.receipt,
                              worktree=candidate, branch="agent/" + slug)
            payload = publish_candidate(candidate, manifest=manifest, receipt_paths=args.receipt, title=args.title)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except RequirementIntegrationError as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
