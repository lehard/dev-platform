from __future__ import annotations

import argparse
import re
import subprocess

from _platform_common import current_worktree_root, harness_mode, profile, read_platform_config, run_git


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    if not cleaned:
        raise argparse.ArgumentTypeError("slug must contain letters or numbers")
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser(description="Start work using the configured dev-platform workflow profile.")
    parser.add_argument("slug", type=slug)
    parser.add_argument("--task", required=True)
    parser.add_argument("--scope", default="")
    args = parser.parse_args()
    root = current_worktree_root()
    config = read_platform_config(root)
    if harness_mode(config) != "platform":
        raise SystemExit("harness_mode=project: use the repository-owned task/worktree entrypoint described by its AGENTS.md.")
    prof = profile(config)
    main_branch = str(config.get("main_branch", "main"))
    doctor = subprocess.run(["python3", str(root / "scripts" / "agent_doctor.py")], cwd=root)
    if doctor.returncode != 0:
        raise SystemExit(doctor.returncode)
    subprocess.run(["python3", str(root / "scripts" / "project_sync.py")], cwd=root, check=True)
    if prof == "light":
        checked_out = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
        if checked_out != main_branch:
            raise SystemExit(f"light profile expects {main_branch!r} checked out; found {checked_out!r}.")
        print(f"Ready on synchronized {main_branch}. Single-agent light workflow has no task branch.")
        return 0
    if prof == "standard":
        branch = f"agent/{args.slug}"
        exists = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root, check=False)
        if exists.returncode == 0:
            raise SystemExit(f"Branch already exists: {branch}")
        run_git(["switch", "-c", branch, main_branch], cwd=root)
        print(f"Created feature branch: {branch}")
        return 0
    if prof == "multi-agent":
        return subprocess.run(["python3", str(root / "scripts" / "start_worktree.py"), args.slug, "--task", args.task, "--scope", args.scope, "--skip-sync"], cwd=root).returncode
    raise SystemExit(f"Unknown workflow_profile: {prof}")


if __name__ == "__main__":
    raise SystemExit(main())
