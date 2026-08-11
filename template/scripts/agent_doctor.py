from __future__ import annotations

import argparse
import json
import shutil
import stat
import subprocess
from pathlib import Path

from _platform_common import (
    current_worktree_root,
    fetch_main,
    github_cli_env,
    harness_mode,
    main_root,
    pr_merge_mode,
    profile,
    protected_main,
    publish_mode,
    read_platform_config,
    relation,
    require_origin,
    run_git,
)
import publication_state


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


def run_multi_agent_hygiene(integration: Path) -> None:
    board = subprocess.run(
        ["python3", str(integration / "scripts" / "agent_board.py"), "doctor", "--fix"],
        cwd=integration,
        text=True,
        capture_output=True,
        check=False,
    )
    board_detail = (board.stdout + "\n" + board.stderr).strip()
    if board.returncode == 0:
        report("ok", board_detail or "agent board is healthy")
    else:
        report("warn", "agent board needs attention: " + (board_detail or f"exit {board.returncode}"))

    cleanup = subprocess.run(
        ["python3", str(integration / "scripts" / "worktree_cleanup.py"), "scan"],
        cwd=integration,
        text=True,
        capture_output=True,
        check=False,
    )
    if cleanup.returncode != 0:
        report("warn", "worktree hygiene scan could not complete: " + (cleanup.stderr.strip() or cleanup.stdout.strip() or f"exit {cleanup.returncode}"))
        return
    try:
        payload = json.loads(cleanup.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        report("warn", "worktree hygiene scan returned unreadable output")
        return
    pending = int(payload.get("pending", 0))
    eligible = int(payload.get("eligible", 0))
    pending_report = payload.get("pending_report")
    if pending:
        report("warn", f"{pending} inactive dirty/unmerged worktree(s) need attention; report: {pending_report}")
    else:
        report("ok", "no forgotten dirty/unmerged managed worktrees detected")
    if eligible:
        report("warn", f"{eligible} old merged worktree(s) are safe cleanup candidates; use scripts/worktree_cleanup.py cleanup")


def run_friction_review_status(integration: Path) -> None:
    result = subprocess.run(
        ["python3", str(integration / "scripts" / "agent_friction.py"), "pending", "--min-events", "5", "--format", "json"],
        cwd=integration,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        report("warn", "friction review status could not be read: " + (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"))
        return
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        report("warn", "friction review status returned unreadable output")
        return
    pending = int(payload.get("pending_count", 0))
    if payload.get("ready"):
        report(
            "warn",
            f"agent friction review is ready ({pending} pending; reason={payload.get('reason')}); review with `python3 scripts/agent_friction.py pending --format markdown`",
        )
    elif pending:
        report("ok", f"agent friction review not ready yet ({pending}/5 pending events)")
    else:
        report("ok", "no unreviewed agent friction events")


def query_github_branch_protection(root: Path, env: dict[str, str], branch: str) -> bool | None:
    name = publication_state.github_repo_name(root, env)
    if name is None:
        return None
    result = subprocess.run(
        ["gh", "api", f"repos/{name}/branches/{branch}", "--jq", ".protected"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def report_publication_status(root: Path, integration: Path, config: dict, gh_env: dict[str, str] | None) -> int:
    """Report unfinished automatic PR delivery as actionable publication state.

    Never mutates: this only observes current Git/GitHub state, exactly like
    `finish_task.py --status`. It intentionally does not fail doctor's overall
    exit code by itself -- unfinished delivery is expected mid-task state, not
    a hygiene defect -- except when GitHub state cannot be read at all while
    automatic delivery is configured, which is reported as a warning too since
    the operator still has a safe, resumable `finish`/`finish --status` path.
    """
    main_branch = str(config.get("main_branch", "main"))
    branch = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
    if not branch or branch == main_branch:
        return 0
    obs = publication_state.observe_publication(root, integration, gh_env, branch, main_branch)
    durability = publication_state.merge_durability_capability(config, gh_env, root)
    pr_ref = f" ({obs.pr.get('url')})" if obs.pr else ""
    if obs.bucket == publication_state.GITHUB_UNAVAILABLE:
        report("warn", f"publication status for {branch} could not be read from GitHub; resume with `finish_task.py --status`")
    elif obs.bucket == publication_state.NOT_PUBLISHED:
        report("ok", f"{branch} has no exact-head PR yet")
    elif obs.bucket == publication_state.BLOCKED:
        report("warn", f"{branch} publication is blocked: required checks failed{pr_ref}; delivery is unfinished, not complete")
    elif obs.bucket in (publication_state.OPEN_CHECKS_PENDING, publication_state.REMOTE_ARMED):
        armed = "auto-merge/queue is armed remotely" if obs.bucket == publication_state.REMOTE_ARMED else "checks are pending"
        report("warn", f"{branch} publication is unfinished ({armed}){pr_ref}; run finish_task.py (or --status) to continue, do not report the task as delivered")
    elif obs.bucket == publication_state.REMOTE_MERGED_LOCAL_PENDING:
        report("warn", f"{branch} was merged on GitHub{pr_ref}, but local main/board/worktree reconciliation is still pending; run finish_task.py to reconcile")
    elif obs.bucket == publication_state.COMPLETE:
        report("ok", f"{branch} is merged and reconciled{pr_ref}")
    if pr_merge_mode(config) == "auto" and gh_env is not None:
        if durability == "remote_armed_capable":
            report("ok", "native GitHub auto-merge/queue capability is available for durable remote delivery")
        elif durability == "foreground_fallback":
            report(
                "warn",
                "native GitHub auto-merge/queue is unavailable; publication uses the safe bounded foreground fallback "
                "(degraded remote durability). An administrator can enable it explicitly with "
                "`gh repo edit --enable-auto-merge` (or the repository Settings > General > 'Allow auto-merge' toggle) "
                "if durable remote delivery is desired; this is never changed automatically by the platform.",
            )
    return 0


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
    expected_protected = protected_main(config)
    merge_mode = pr_merge_mode(config)
    failures = 0
    report(
        "ok",
        f"workflow_profile={prof}; harness_mode={harness}; protected_main={str(expected_protected).lower()}; publish_mode={mode}; pr_merge_mode={merge_mode}",
    )
    if merge_mode not in {"auto", "manual"}:
        report("fail", f"invalid pr_merge_mode={merge_mode!r}; expected auto or manual")
        failures += 1
    if expected_protected and mode == "direct":
        report("fail", "protected_main=true is incompatible with publish_mode=direct; use PR publication so required checks can gate merge")
        failures += 1
    if mode == "pr" and prof == "light" and harness == "platform":
        report("fail", "platform-owned PR publication requires a feature-capable standard/multi-agent profile")
        failures += 1
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

    gh_env = github_cli_env(root)
    if mode == "pr" and harness == "platform":
        if gh_env is not None:
            report("ok", "GitHub PR API authentication available")
        else:
            report("fail", "GitHub PR API auth unavailable; run gh auth login, provide GH_TOKEN/GITHUB_TOKEN, or configure reusable GitHub HTTPS credentials")
            failures += 1
    elif gh_env is not None:
        report("ok", "GitHub API authentication available")

    if mode == "pr" and harness == "platform":
        report_publication_status(root, integration, config, gh_env)

    if gh_env is not None:
        actual_protected = query_github_branch_protection(root, gh_env, branch)
        if actual_protected is None:
            report("warn", f"could not verify GitHub protection state for {branch}")
        else:
            report("ok", f"GitHub reports {branch} protected={str(actual_protected).lower()}")
            if actual_protected and mode == "direct":
                report("fail", f"GitHub {branch} is protected but publish_mode=direct would push it directly")
                failures += 1
            if actual_protected != expected_protected:
                report(
                    "warn",
                    f"configured protected_main={str(expected_protected).lower()} differs from GitHub protected={str(actual_protected).lower()}; reconcile project config through review",
                )

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
        run_multi_agent_hygiene(integration)
    if harness == "platform":
        run_friction_review_status(integration)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
