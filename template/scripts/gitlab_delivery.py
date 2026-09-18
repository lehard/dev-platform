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
    iid = mr.get("iid") or mr.get("id")
    url = mr.get("web_url") or mr.get("webUrl") or "[GitLab MR URL unavailable]"
    pipelines = _glab(root, ["mr", "pipelines", str(iid), "--output", "json"])
    pipeline_status = "unknown"
    if pipelines.returncode == 0:
        try:
            payload = json.loads(pipelines.stdout)
            if isinstance(payload, list) and payload and isinstance(payload[0], dict):
                pipeline_status = str(payload[0].get("status", "unknown"))
        except json.JSONDecodeError:
            pass
    print(f"GitLab merge request {iid}: {url}")
    print(f"GitLab CI status: {pipeline_status}")
    print("GitLab delivery stops at human merge/acceptance by configured policy.")
    return 0


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
