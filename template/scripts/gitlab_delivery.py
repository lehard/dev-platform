"""Bounded GitLab delivery adapter for the provider-neutral standard lifecycle."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from _platform_common import current_worktree_root, read_platform_config, run_git


def _glab(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    if not shutil.which("glab"):
        raise SystemExit("GitLab delivery requires the glab CLI; install/authenticate it before publication.")
    return subprocess.run(["glab", *args], cwd=root, text=True, capture_output=True, check=False)


def _branch(root: Path) -> str:
    branch = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
    if not branch:
        raise SystemExit("Detached HEAD is not publishable through the GitLab adapter.")
    return branch


def _clean(root: Path) -> None:
    if run_git(["status", "--porcelain"], cwd=root).stdout.strip():
        raise SystemExit("Task worktree is dirty. Commit or resolve changes before publication.")


def _find_mr(root: Path, branch: str, target: str) -> dict | None:
    result = _glab(root, ["mr", "list", "--source-branch", branch, "--target-branch", target, "--output", "json"])
    if result.returncode:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return payload[0] if isinstance(payload, list) and payload and isinstance(payload[0], dict) else None


def _field(record: dict, *names: str) -> str | None:
    for name in names:
        value = record.get(name)
        if isinstance(value, str) and value:
            return value
    return None


def _exact_mr(root: Path, candidate: dict, branch: str, target: str, head: str) -> dict:
    iid = candidate.get("iid") or candidate.get("id")
    if not iid:
        raise SystemExit("GitLab returned a merge request without an identifier.")
    viewed = _glab(root, ["mr", "view", str(iid), "--output", "json"])
    if viewed.returncode:
        raise SystemExit("GitLab could not read the selected merge request for exact-head verification.")
    try:
        mr = json.loads(viewed.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("GitLab returned unreadable merge-request evidence.") from exc
    if not isinstance(mr, dict):
        raise SystemExit("GitLab returned invalid merge-request evidence.")
    source = _field(mr, "source_branch", "sourceBranch")
    destination = _field(mr, "target_branch", "targetBranch")
    mr_head = _field(mr, "sha", "head_sha", "headSha")
    if source != branch or destination != target or mr_head != head:
        raise SystemExit(
            "GitLab merge request does not prove the exact published task HEAD "
            f"(source={source!r}, target={destination!r}, head={mr_head!r}, expected={head!r})."
        )
    return mr


def _pipeline_state(root: Path, iid: object, head: str) -> str:
    pipelines = _glab(root, ["mr", "pipelines", str(iid), "--output", "json"])
    if pipelines.returncode:
        raise SystemExit("GitLab pipeline evidence is unreadable for the exact task HEAD.")
    try:
        payload = json.loads(pipelines.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("GitLab returned unreadable pipeline evidence.") from exc
    if not isinstance(payload, list):
        raise SystemExit("GitLab returned invalid pipeline evidence.")
    exact = [item for item in payload if isinstance(item, dict) and _field(item, "sha", "head_sha", "headSha") == head]
    if len(exact) != 1:
        raise SystemExit("GitLab did not return one unambiguous pipeline for the exact published task HEAD.")
    status = _field(exact[0], "status")
    if not status:
        raise SystemExit("GitLab exact-head pipeline has no readable status.")
    return status.lower()


def publish(root: Path, *, title: str | None, body: str | None) -> int:
    config = read_platform_config(root)
    target = str(config.get("main_branch", "main"))
    branch = _branch(root)
    if branch == target:
        raise SystemExit("GitLab merge-request publication requires a feature branch.")
    _clean(root)
    pushed = run_git(["push", "-u", "origin", f"{branch}:{branch}"], cwd=root, check=False)
    if pushed.returncode:
        raise SystemExit("GitLab task branch push failed: " + (pushed.stderr.strip() or pushed.stdout.strip()))
    head = run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    if not head:
        raise SystemExit("Could not determine the exact task HEAD after GitLab push.")
    mr = _find_mr(root, branch, target)
    if mr is None:
        command = ["mr", "create", "--source-branch", branch, "--target-branch", target]
        command += ["--title", title] if title else ["--fill"]
        if body:
            command += ["--description", body]
        created = _glab(root, command)
        if created.returncode:
            raise SystemExit("GitLab merge-request creation failed: " + (created.stderr.strip() or created.stdout.strip()))
        mr = _find_mr(root, branch, target)
    if mr is None:
        raise SystemExit("GitLab did not return an exact merge request for the published task branch.")
    mr = _exact_mr(root, mr, branch, target, head)
    iid = mr.get("iid") or mr.get("id")
    url = mr.get("web_url") or mr.get("webUrl") or "[GitLab MR URL unavailable]"
    pipeline_status = _pipeline_state(root, iid, head)
    print(f"GitLab merge request {iid}: {url}")
    print(f"GitLab CI status for {head}: {pipeline_status}")
    if pipeline_status == "success":
        print("GitLab delivery is ready for human merge/acceptance; no merge or deployment was performed.")
        return 0
    if pipeline_status in {"created", "pending", "preparing", "running", "scheduled", "waiting_for_resource"}:
        print("GitLab CI is not ready; rerun status/finish after the exact-head pipeline reaches a terminal state.")
        return 3
    raise SystemExit(f"GitLab exact-head pipeline is not accepted green terminal state: {pipeline_status}")


def status(root: Path) -> int:
    config = read_platform_config(root)
    target = str(config.get("main_branch", "main"))
    branch = _branch(root)
    mr = _find_mr(root, branch, target)
    print(json.dumps({"provider": "gitlab", "branch": branch, "target": target, "merge_request": mr}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="GitLab delivery adapter")
    parser.add_argument("command", choices=("publish", "status"))
    parser.add_argument("--title")
    parser.add_argument("--body")
    args = parser.parse_args()
    root = current_worktree_root()
    return status(root) if args.command == "status" else publish(root, title=args.title, body=args.body)


if __name__ == "__main__":
    raise SystemExit(main())
