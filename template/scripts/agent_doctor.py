from __future__ import annotations

import argparse
import shutil
import stat
import subprocess
from pathlib import Path

from _platform_common import current_worktree_root, fetch_main, harness_mode, main_root, profile, publish_mode, read_platform_config, relation, require_origin, run_git


CONFLICT_STATUS_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
HOOK_MARKER = b"Managed by dev-platform"


def report(kind: str, message: str) -> None:
    print(f"[{kind}] {message}")


def main_copy_status(root: Path) -> tuple[list[str], list[str]]:
    raw = run_git(["status", "--porcelain", "--untracked-files=all"], cwd=root).stdout
    dirty: list[str] = []
    conflicted: list[str] = []
    for line in raw.splitlines():
        if not line:
            continue
        path = line[3:]
        if line[:2] in CONFLICT_STATUS_CODES:
            conflicted.append(path)
        else:
            dirty.append(path)
    return dirty, conflicted


def ensure_git_hooks(root: Path) -> tuple[dict[str, str], int]:
    results: dict[str, str] = {}
    failures = 0
    source_dir = root / "scripts" / "git_hooks"
    hooks_dir = root / ".git" / "hooks"
    if not source_dir.is_dir() or not hooks_dir.parent.is_dir():
        return results, failures
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(source_dir.iterdir()):
        if not source.is_file() or source.name.startswith("."):
            continue
        target = hooks_dir / source.name
        content = source.read_bytes()
        if target.exists():
            existing = target.read_bytes()
            if existing == content:
                mode = stat.S_IMODE(target.stat().st_mode)
                if mode & 0o111 != 0o111:
                    target.chmod(mode | 0o111)
                results[source.name] = "up-to-date"
                continue
            if HOOK_MARKER not in existing:
                results[source.name] = "foreign-hook-kept"
                failures += 1
                continue
            results[source.name] = "updated"
        else:
            results[source.name] = "installed"
        target.write_bytes(content)
        target.chmod(0o775)
    return results, failures


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
    harness = harness_mode(config)
    failures = 0
    report("ok", f"workflow_profile={prof}; harness_mode={harness}; publish_mode={mode}")
    if harness != "platform":
        report("ok", "project-owned harness selected; repository AGENTS.md owns task/worktree/merge mechanics")
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
        report("warn", f"local {branch} is behind; synchronize before starting new work")
    elif local_state == "ahead":
        report("warn", f"local {branch} is ahead; publish/reconcile before starting unrelated work")
    else:
        report("fail", f"local {branch} and {args.remote}/{branch} are {local_state}")
        failures += 1
    current = run_git(["branch", "--show-current"], cwd=root).stdout.strip() or "DETACHED"
    report("ok", f"current branch={current}")
    if run_git(["status", "--porcelain"], cwd=root).stdout.strip():
        report("warn", "current worktree is dirty")
    if mode == "pr" and harness == "platform":
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
    if prof == "multi-agent" and harness == "platform":
        hook_results, hook_failures = ensure_git_hooks(integration)
        for name, state in sorted(hook_results.items()):
            report("fail" if state == "foreign-hook-kept" else "ok", f"git hook {name}: {state}")
        failures += hook_failures
        dirty, conflicted = main_copy_status(integration)
        if conflicted:
            report("fail", "integration copy has unresolved conflicts: " + ", ".join(conflicted[:5]))
            failures += 1
        elif dirty:
            report("fail", "integration copy is dirty and would block all agent integration: " + ", ".join(dirty[:5]))
            failures += 1
        else:
            report("ok", "integration copy is clean")
        board = integration / config.get("paths", {}).get("agent_board", ".claude/agents-board.json")
        report("ok" if board.exists() else "warn", f"agent board: {board}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
