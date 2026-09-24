#!/usr/bin/env python3
"""Exceptional exact-parent merge of sequential verified Requirement children."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import requirement_integration as ri


def _paths(root: Path, start: str, end: str) -> set[str]:
    return set(ri._git(root, "diff", "--name-only", start, end).splitlines()) - {""}


def _slug(manifest: dict[str, Any]) -> str:
    return ri._candidate_slug(manifest["requirement"], manifest["generation"]) + "-merge"


def _manifest_path(manifest: dict[str, Any]) -> Path:
    return Path("dev-platform/requirement-integrations") / (_slug(manifest) + ".json")


def assemble(root: Path, requirement: str, receipts: list[Path]) -> dict[str, Any]:
    base = ri._git(root, "rev-parse", "HEAD")
    ordinary = ri.assemble_candidate(root, requirement=requirement, base=base, receipt_paths=receipts)
    children = ordinary["children"]
    for previous, current in zip(children, children[1:]):
        if subprocess.run(["git", "merge-base", "--is-ancestor", previous["head"], current["head"]],
                          cwd=root, capture_output=True).returncode:
            raise ri.RequirementIntegrationError("merge recovery requires an exact sequential child chain")
    source = children[-1]["head"]
    common = ri._git(root, "merge-base", base, source)
    if not common:
        raise ri.RequirementIntegrationError("merge recovery has no common base")
    source_paths = sorted(_paths(root, common, source))
    overlap = sorted(set(source_paths) & _paths(root, common, base))
    unsigned = {"version": 1, "mode": "exact-parent-merge", "requirement": requirement,
                "base": base, "source_head": source, "generation": base[:12],
                "children": children, "source_paths": source_paths, "overlap_paths": overlap}
    return {**unsigned, "digest": ri._digest(unsigned)}


def _check_manifest(root: Path, manifest: dict[str, Any], receipts: list[Path]) -> None:
    unsigned = {key: value for key, value in manifest.items() if key != "digest"}
    if manifest.get("mode") != "exact-parent-merge" or manifest.get("digest") != ri._digest(unsigned):
        raise ri.RequirementIntegrationError("merge recovery manifest is invalid")
    if assemble(root, manifest["requirement"], receipts) != manifest:
        raise ri.RequirementIntegrationError("merge recovery inputs changed")


def prepare(root: Path, manifest: dict[str, Any], receipts: list[Path], out: Path) -> dict[str, Any]:
    root = root.resolve()
    main_branch, parent = ri._project_topology(root)
    if ri._registered_worktrees(root).get(root) != main_branch or ri._git(root, "status", "--porcelain"):
        raise ri.RequirementIntegrationError("merge recovery requires clean shared main checkout")
    if subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, capture_output=True).returncode == 0:
        ri._git(root, "fetch", "origin", main_branch)
        authoritative = ri._git(root, "rev-parse", f"origin/{main_branch}")
    else:
        authoritative = ri._git(root, "rev-parse", main_branch)
    if authoritative != manifest["base"]:
        raise ri.RequirementIntegrationError("authoritative main changed before merge preparation")
    _check_manifest(root, manifest, receipts)
    slug = _slug(manifest)
    worktree = parent / slug
    branch = "agent/" + slug
    if out.exists() and out.read_text(encoding="utf-8") != json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n":
        raise ri.RequirementIntegrationError("refusing to replace a different merge manifest")
    if worktree.exists() or subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/heads/" + branch], cwd=root).returncode == 0:
        raise ri.RequirementIntegrationError("merge candidate generation is already occupied")
    worktree.parent.mkdir(parents=True, exist_ok=True)
    ri._git(root, "worktree", "add", "-b", branch, str(worktree), manifest["base"])
    ri._provision_local_contract(root, worktree)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    merged = subprocess.run(["git", "merge", "--no-ff", "--no-commit", manifest["source_head"]],
                            cwd=worktree, capture_output=True, text=True)
    merge_head = (worktree / ".git").is_file() and ri._git(worktree, "rev-parse", "MERGE_HEAD")
    if merge_head != manifest["source_head"]:
        raise ri.RequirementIntegrationError(f"merge did not retain exact source parent: {merged.stderr.strip()}")
    conflicts = ri._git(worktree, "diff", "--name-only", "--diff-filter=U").splitlines()
    if any(path not in manifest["overlap_paths"] for path in conflicts):
        raise ri.RequirementIntegrationError("merge produced conflict outside recorded overlap paths")
    return {"worktree": str(worktree), "branch": branch, "conflicts": conflicts, "status": "needs-resolution"}


def finalize(root: Path, manifest: dict[str, Any], receipts: list[Path]) -> dict[str, Any]:
    root = root.resolve()
    unsigned = {key: value for key, value in manifest.items() if key != "digest"}
    if manifest.get("mode") != "exact-parent-merge" or manifest.get("digest") != ri._digest(unsigned):
        raise ri.RequirementIntegrationError("merge recovery manifest is invalid")
    if len(receipts) != len(manifest["children"]):
        raise ri.RequirementIntegrationError("merge recovery receipt count differs")
    if ri._git(root, "symbolic-ref", "--short", "HEAD") != "agent/" + _slug(manifest):
        raise ri.RequirementIntegrationError("merge candidate branch identity differs")
    if ri._git(root, "rev-parse", "HEAD") != manifest["base"] or ri._git(root, "rev-parse", "MERGE_HEAD") != manifest["source_head"]:
        raise ri.RequirementIntegrationError("merge parents changed before finalization")
    for child, receipt in zip(manifest["children"], receipts):
        if ri.read_receipt(receipt).digest != child["digest"] or ri._git(root, "rev-parse", child["source_branch"]) != child["head"]:
            raise ri.RequirementIntegrationError("child receipt or branch changed before merge finalization")
    if ri._git(root, "diff", "--name-only", "--diff-filter=U"):
        raise ri.RequirementIntegrationError("merge still has unresolved conflicts")
    status = ri._git(root, "status", "--porcelain").splitlines()
    if any(line.startswith("??") for line in status):
        raise ri.RequirementIntegrationError("merge candidate contains unexpected untracked files")
    changed = set(ri._git(root, "diff", "HEAD", "--name-only").splitlines()) - {""}
    if not changed or not changed.issubset(set(manifest["source_paths"])):
        raise ri.RequirementIntegrationError("merge resolution changed paths outside exact child source")
    ri._git(root, "add", "--", *sorted(changed))
    ri._git(root, "commit", "-m", f"Merge verified children for {manifest['requirement']}\n\nRequirement-Source-Head: {manifest['source_head']}")
    if ri._git(root, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:] != [manifest["base"], manifest["source_head"]]:
        raise ri.RequirementIntegrationError("merge commit parents are not exact")
    path = root / _manifest_path(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ri._git(root, "add", path.relative_to(root).as_posix())
    ri._git(root, "commit", "-m", f"Bind merged Requirement {manifest['requirement']} candidate")
    return {"status": "ready", "worktree": str(root), "head": ri._git(root, "rev-parse", "HEAD")}


def _validate_checkout(root: Path, manifest: dict[str, Any], receipts: list[Path]) -> tuple[str, str]:
    unsigned = {key: value for key, value in manifest.items() if key != "digest"}
    if manifest.get("mode") != "exact-parent-merge" or manifest.get("digest") != ri._digest(unsigned):
        raise ri.RequirementIntegrationError("merge recovery manifest is invalid")
    if len(receipts) != len(manifest["children"]):
        raise ri.RequirementIntegrationError("merge recovery receipt count differs")
    if ri._git(root, "symbolic-ref", "--short", "HEAD") != "agent/" + _slug(manifest):
        raise ri.RequirementIntegrationError("merge candidate branch differs")
    if ri._git(root, "status", "--porcelain"):
        raise ri.RequirementIntegrationError("merge candidate is dirty")
    commits = ri._git(root, "rev-list", "--first-parent", "--reverse", f"{manifest['base']}..HEAD").splitlines()
    if len(commits) != 2:
        raise ri.RequirementIntegrationError("merge candidate has unexpected history")
    merge, bind = commits
    if ri._git(root, "rev-list", "--parents", "-n", "1", merge).split()[1:] != [manifest["base"], manifest["source_head"]]:
        raise ri.RequirementIntegrationError("merge candidate parents differ from exact evidence")
    changed = _paths(root, manifest["base"], merge)
    if not changed.issubset(set(manifest["source_paths"])):
        raise ri.RequirementIntegrationError("merge candidate altered an unrelated path")
    path = _manifest_path(manifest).as_posix()
    if ri._git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", bind) != path:
        raise ri.RequirementIntegrationError("merge binding commit has unexpected changes")
    if json.loads(ri._git(root, "show", f"HEAD:{path}")) != manifest:
        raise ri.RequirementIntegrationError("merge manifest is not exact at candidate HEAD")
    for child, receipt in zip(manifest["children"], receipts):
        if ri.read_receipt(receipt).digest != child["digest"] or ri._git(root, "rev-parse", child["source_branch"]) != child["head"]:
            raise ri.RequirementIntegrationError("merge child provenance changed")
    return "agent/" + _slug(manifest), ri._git(root, "rev-parse", "HEAD")


def publish(root: Path, manifest: dict[str, Any], receipts: list[Path], title: str | None) -> dict[str, Any]:
    from _platform_common import main_root, publish_mode, read_platform_config

    root = root.resolve()
    integration = main_root().resolve()
    if publish_mode(read_platform_config(root)) != "pr":
        raise ri.RequirementIntegrationError("merge recovery requires protected PR publication")
    branch, head = _validate_checkout(root, manifest, receipts)
    merged = ri._reconcile_exact_merged(root, integration, manifest, branch, head)
    if merged is not None:
        return merged
    main_branch, _ = ri._project_topology(integration)
    ri._git(integration, "fetch", "origin", main_branch)
    if ri._git(integration, "rev-parse", f"origin/{main_branch}") != manifest["base"]:
        raise ri.RequirementIntegrationError("authoritative main changed before merge publication")
    ri._verify_parent_links(integration, manifest)
    ri._run_full_checks(root)
    _validate_checkout(root, manifest, receipts)
    ri._git(integration, "fetch", "origin", main_branch)
    if ri._git(integration, "rev-parse", f"origin/{main_branch}") != manifest["base"]:
        raise ri.RequirementIntegrationError("authoritative main changed after merge validation")
    command = ["python3", "scripts/project_publish.py", "--mode", "pr",
               "--shared-manifest", _manifest_path(manifest).as_posix()]
    if title:
        command += ["--title", title]
    command += ["--body", f"Shared exact-parent merge for {manifest['requirement']}\n\nCandidate: {head}\nManifest: {_manifest_path(manifest)}"]
    if subprocess.run(command, cwd=root).returncode:
        raise ri.RequirementIntegrationError("protected merge candidate publication did not complete")
    merged = ri._reconcile_exact_merged(root, integration, manifest, branch, head)
    if merged is None:
        raise ri.RequirementIntegrationError("publisher returned without exact merged PR")
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--requirement", required=True)
    prepare_parser.add_argument("--receipt", required=True, action="append", type=Path)
    prepare_parser.add_argument("--out", required=True, type=Path)
    for name in ("finalize", "publish"):
        command = sub.add_parser(name)
        command.add_argument("--manifest", required=True, type=Path)
        command.add_argument("--receipt", required=True, action="append", type=Path)
        if name == "publish":
            command.add_argument("--title")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    try:
        if args.command == "prepare":
            manifest = assemble(root, args.requirement, args.receipt)
            result = prepare(root, manifest, args.receipt, args.out)
        else:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            result = finalize(root, manifest, args.receipt) if args.command == "finalize" else publish(root, manifest, args.receipt, args.title)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (ri.RequirementIntegrationError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
