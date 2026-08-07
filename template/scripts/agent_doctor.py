from __future__ import annotations

import argparse
import shutil
import subprocess

from _platform_common import current_worktree_root, fetch_main, main_root, profile, publish_mode, read_platform_config, relation, require_origin, run_git


def report(kind: str, message: str) -> None:
    print(f"[{kind}] {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether an agent can safely start or finish work against current GitHub state.")
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args()
    root = current_worktree_root()
    integration = main_root()
    config = read_platform_config(root)
    branch = str(config.get("main_branch", "main"))
    prof = profile(config)
    mode = publish_mode(config)
    failures = 0
    report("ok", f"workflow_profile={prof}; publish_mode={mode}")
    try:
        require_origin(integration, args.remote)
        report("ok", f"remote {args.remote} configured")
    except SystemExit as exc:
        report("fail", str(exc))
        return 1
    if not args.no_fetch:
        try:
            fetch_main(integration, args.remote, branch)
            report("ok", f"fetched {args.remote}/{branch}")
        except Exception as exc:
            report("fail", f"fetch failed: {exc}")
            failures += 1
    local_state = relation(integration, branch, f"{args.remote}/{branch}")
    if local_state == "equal":
        report("ok", f"local {branch} equals {args.remote}/{branch}")
    elif local_state == "behind":
        report("warn", f"local {branch} is behind; run scripts/project_sync.py before starting new work")
    elif local_state == "ahead":
        report("warn", f"local {branch} is ahead; publish/reconcile before starting unrelated work")
    else:
        report("fail", f"local {branch} and {args.remote}/{branch} are {local_state}")
        failures += 1
    current = run_git(["branch", "--show-current"], cwd=root).stdout.strip() or "DETACHED"
    report("ok", f"current branch={current}")
    if run_git(["status", "--porcelain"], cwd=root).stdout.strip():
        report("warn", "current worktree is dirty")
    if mode == "pr":
        if shutil.which("gh"):
            auth = subprocess.run(["gh", "auth", "status"], cwd=root, text=True, capture_output=True)
            if auth.returncode == 0:
                report("ok", "GitHub CLI authenticated for PR publishing")
            else:
                report("fail", "GitHub CLI is installed but not authenticated; run gh auth login")
                failures += 1
        else:
            report("fail", "publish_mode=pr requires GitHub CLI (gh)")
            failures += 1
    if prof == "multi-agent":
        board = integration / config.get("paths", {}).get("agent_board", ".claude/agents-board.json")
        report("ok" if board.exists() else "warn", f"agent board: {board}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
