from __future__ import annotations

import argparse
import json
import os
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
    run_git,
    preflight,
)
from integration_state import (
    dirty_paths,
    fcntl,
    integration_clean,
    local_state_matches_remote_target,
    normalize_equivalent_remote_state,
    serialized_integration,
)
import publication_state
from managed_project_status import (
    ManagedProjectStatusError,
    reconcile as reconcile_managed_project,
)
try:
    from agent_board import warn_current_worktree_scope_overlap
except (ImportError, ModuleNotFoundError):  # Compatibility while older rendered projects are upgraded.
    def warn_current_worktree_scope_overlap(root: Path, worktree: Path, branch: str) -> None:
        return None
try:
    from managed_task import (
        ManagedTaskError,
        assert_integration_identity_cross_check,
        delivery_identity,
        require_delivery_provenance,
    )
except ModuleNotFoundError:  # Compatibility while a pre-managed-intake render is being upgraded.
    class ManagedTaskError(RuntimeError):
        pass

    def require_delivery_provenance(root: Path):
        return None

    def delivery_identity(root: Path):
        return None

    def assert_integration_identity_cross_check(integration: Path, identity) -> None:
        return None


ALLOW_NO_CHECKS_ENV = "DEV_PLATFORM_ALLOW_NO_CHECKS"
DIRECT_PUBLISH_GUARD = "DEV_PLATFORM_VALIDATED_DIRECT_PUBLISH"


def clean(root: Path) -> bool:
    return not run_git(["status", "--porcelain"], cwd=root).stdout.strip()


def current_branch(root: Path) -> str:
    return run_git(["branch", "--show-current"], cwd=root).stdout.strip()


def find_board_id(main: Path, worktree: Path, config: dict) -> str | None:
    rel = config.get("paths", {}).get("agent_board", ".claude/agents-board.json")
    path = main / rel
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    for item in data.get("items", []):
        try:
            if Path(item.get("worktree", "")).resolve() == worktree.resolve():
                return item.get("id")
        except OSError:
            continue
    return None


def finish_board(main: Path, worktree: Path, config: dict) -> None:
    board_id = find_board_id(main, worktree, config)
    if board_id:
        subprocess.run(["python3", str(main / "scripts" / "agent_board.py"), "finish", "--id", board_id, "--quiet"], cwd=main, check=False)


def run_checks(root: Path, base: str, no_checks: bool) -> None:
    if no_checks:
        return
    result = subprocess.run(["python3", str(root / "scripts" / "select_checks.py"), "--base", base, "--execute"], cwd=root)
    if result.returncode != 0:
        record_lifecycle_friction(root, "lifecycle-validation-failure", "required platform validation failed", "select_checks returned a non-zero exit status")
        raise SystemExit(result.returncode)


def run_openspec_hygiene(root: Path) -> None:
    script = root / "scripts" / "openspec_lifecycle.py"
    result = subprocess.run(["python3", str(script), "check"], cwd=root)
    if result.returncode != 0:
        record_lifecycle_friction(root, "lifecycle-openspec-hygiene-failure", "OpenSpec lifecycle hygiene failed", "openspec_lifecycle check returned a non-zero exit status")
        raise SystemExit(result.returncode)


def record_lifecycle_friction(root: Path, category: str, observation: str, evidence: str) -> None:
    """Capture narrow deterministic failures without changing delivery outcome."""
    helper = root / "scripts" / "agent_friction.py"
    if not helper.is_file():
        return
    subprocess.run(
        [
            "python3", str(helper), "record",
            "--category", category, "--trigger", "repeated-error", "--severity", "high",
            "--observation", observation, "--evidence", evidence,
            "--hypothesis", "a deterministic lifecycle guard needs operator review",
            "--scope", "platform", "--proposal", "review the lifecycle failure and its guard",
            "--task", current_branch(root),
        ],
        cwd=root, text=True, capture_output=True, check=False,
    )


def run_friction_retry_and_checkpoint(root: Path, branch: str) -> None:
    """Telemetry is best effort; the explicit semantic checkpoint is not."""
    helper = root / "scripts" / "agent_friction.py"
    # Compatibility for minimal pre-friction renders used by older project
    # harnesses. Current platform renders always include this helper.
    if not helper.is_file():
        return
    result = subprocess.run(
        ["python3", str(helper), "route-pending"], cwd=root, text=True, capture_output=True, check=False,
    )
    if result.returncode == 0:
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            print("WARNING: friction routing retry returned unreadable output; safe publication may continue.")
        else:
            if payload.get("failures"):
                print(f"WARNING: {payload['failures']} friction event(s) remain pending GitHub routing; safe publication may continue.")
    else:
        print("WARNING: friction routing retry could not run; safe publication may continue.")
    checkpoint = subprocess.run(
        ["python3", str(helper), "assert-checkpoint", "--branch", branch], cwd=root, text=True, capture_output=True, check=False,
    )
    if checkpoint.returncode:
        raise SystemExit(checkpoint.stderr.strip() or checkpoint.stdout.strip() or "Completion friction checkpoint is required.")


def validate_publication_config(root: Path, config: dict, prof: str, mode: str) -> None:
    merge_mode = pr_merge_mode(config)
    if merge_mode not in {"auto", "manual"}:
        raise SystemExit(f"Invalid pr_merge_mode={merge_mode!r}; expected 'auto' or 'manual'.")
    if protected_main(config) and mode == "direct":
        raise SystemExit("protected_main=true is incompatible with publish_mode=direct. Use publish_mode=pr so GitHub required checks can gate the merge.")
    if mode == "pr" and prof == "light":
        raise SystemExit("publish_mode=pr requires a feature-capable profile. Use standard/multi-agent or a reviewed project-owned harness.")
    if mode == "pr" and github_cli_env(root) is None:
        raise SystemExit(
            "publish_mode=pr requires authenticated GitHub CLI/API access. Provide a valid GH_TOKEN/GITHUB_TOKEN, a persistent gh login, or reusable GitHub HTTPS credentials before finishing the task."
        )


def _local_head(root: Path, branch: str) -> str | None:
    result = run_git(["rev-parse", branch], cwd=root, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def task_pr_is_already_merged(root: Path, branch: str, main_branch: str) -> bool:
    """Return true only when GitHub merged the exact-head PR for this local branch."""
    env = github_cli_env(root)
    if env is None:
        return False
    local_head = _local_head(root, branch)
    if local_head is None:
        return False
    lookup = publication_state.find_exact_head_pr(root, env, branch, main_branch, local_head)
    return lookup.available and lookup.exact_merged is not None


def find_existing_exact_open_pr(root: Path, branch: str, main_branch: str) -> dict | None:
    """Detect an already-open exact-head PR so recovery can resume it.

    This is deliberately checked before the first-publication stale-base
    precondition: an existing exact-head PR remains resumable through GitHub
    required checks/protection/auto-merge/queue even after the base branch has
    advanced, and the platform must not force a rebase merely to satisfy a
    local check that GitHub itself does not require for recovery.
    """
    env = github_cli_env(root)
    if env is None:
        return None
    local_head = _local_head(root, branch)
    if local_head is None:
        return None
    lookup = publication_state.find_exact_head_pr(root, env, branch, main_branch, local_head)
    return lookup.exact_open if lookup.available else None


def run_status(work: Path, integration: Path, config: dict, *, as_json: bool) -> int:
    """Strictly read-only publication status: no push/PR/merge/board/cleanup/main mutation."""
    main_branch = str(config.get("main_branch", "main"))
    mode = publish_mode(config)
    branch = current_branch(work)
    if harness_mode(config) != "platform" or mode != "pr":
        message = (
            f"status: not_applicable (harness_mode={harness_mode(config)!r}, publish_mode={mode!r}); "
            "this status view covers harness_mode=platform, publish_mode=pr tasks only."
        )
        print(json.dumps({"status": "not_applicable"}) if as_json else message)
        return 0
    if not branch or branch == main_branch:
        message = "status: not_published (no feature branch is checked out)"
        print(json.dumps({"status": "not_published", "detail": "no feature branch is checked out"}) if as_json else message)
        return 0
    env = github_cli_env(work)
    obs = publication_state.observe_publication(work, integration, env, branch, main_branch)
    durability = publication_state.merge_durability_capability(config, env, work)
    if as_json:
        print(json.dumps(publication_state.status_payload(obs, durability), indent=2))
    else:
        print(publication_state.status_text(obs, durability))
    return 0


def integrate_and_publish_direct(work: Path, integration: Path, config: dict, branch: str, main_branch: str) -> None:
    fetch_main(integration, "origin", main_branch)
    remote_main = f"origin/{main_branch}"
    if branch != main_branch:
        if not clean(integration):
            raise SystemExit("Integration copy is dirty. Resolve it before direct integration.")
        if work == integration:
            run_git(["switch", main_branch], cwd=integration)
        elif current_branch(integration) != main_branch:
            raise SystemExit(f"Integration copy must have {main_branch!r} checked out.")
        if run_git(["merge-base", "--is-ancestor", remote_main, main_branch], cwd=integration, check=False).returncode != 0:
            raise SystemExit(f"Local {main_branch} is not safely based on current {remote_main}.")
        if run_git(["merge-base", "--is-ancestor", main_branch, branch], cwd=integration, check=False).returncode != 0:
            raise SystemExit(f"{branch} is stale relative to current local {main_branch}. Rebase/update explicitly and rerun checks.")
        run_git(["merge", "--ff-only", branch], cwd=integration)
        print(f"Integrated {branch} -> {main_branch} locally.")
    env = os.environ.copy()
    env[DIRECT_PUBLISH_GUARD] = "1"
    subprocess.run(["python3", str(integration / "scripts" / "project_publish.py"), "--mode", "direct"], cwd=integration, check=True, env=env)


def sync_after_remote_pr_merge(work: Path, integration: Path, config: dict, main_branch: str) -> None:
    # This function is called only while serialized_integration is held. Fetch
    # after lock acquisition: a previous reconciler may have advanced main while
    # this task was waiting for the shared checkout.
    fetch_main(integration, "origin", main_branch)
    if not integration_clean(integration, config):
        remote_main = f"origin/{main_branch}"
        paths = dirty_paths(integration, config)
        if not local_state_matches_remote_target(integration, config, remote_main):
            raise SystemExit(
                "Remote PR is merged (authoritative), but local reconciliation is blocked by divergent integration content. "
                "Leave it untouched and synchronize main manually after resolving local state. Affected paths: "
                + ", ".join(paths)
            )
        normalize_equivalent_remote_state(integration, remote_main)
        print(f"Normalized integration index to the already-merged {remote_main}; local content was proven equivalent.")
    remote_main = f"origin/{main_branch}"
    if work == integration:
        run_git(["switch", main_branch], cwd=integration)
    elif current_branch(integration) != main_branch:
        raise SystemExit(f"Remote PR merged, but integration copy must have {main_branch!r} checked out before synchronization.")
    state = relation(integration, main_branch, remote_main)
    if state == "behind":
        run_git(["merge", "--ff-only", remote_main], cwd=integration)
        print(f"Fast-forwarded local {main_branch} to merged {remote_main}.")
    elif state == "equal":
        print(f"Local {main_branch} already equals merged {remote_main}.")
    else:
        raise SystemExit(f"Remote PR merged, but local {main_branch} vs {remote_main} is {state}. Refusing automatic reconciliation.")


def cleanup_completed_task(work: Path, integration: Path, branch: str, *, squash_merged: bool) -> None:
    if work == integration:
        return

    # The running process must leave the task worktree before asking Git to
    # remove it. All post-merge housekeeping is driven from the integration
    # checkout where main is already synchronized.
    os.chdir(integration)
    removed = run_git(["worktree", "remove", str(work)], cwd=integration, check=False)
    if removed.returncode != 0:
        detail = removed.stderr.strip() or removed.stdout.strip() or f"exit {removed.returncode}"
        print(f"WARNING: task is integrated, but local worktree cleanup failed for {work}: {detail}")
        return

    # A squash-merged branch is not an ancestor of main even though its PR is
    # merged. At this point remote merge has been confirmed and main synced, so
    # explicit local branch deletion is safe for the exact completed task.
    delete_flag = "-D" if squash_merged else "-d"
    deleted = run_git(["branch", delete_flag, branch], cwd=integration, check=False)
    if deleted.returncode != 0:
        detail = deleted.stderr.strip() or deleted.stdout.strip() or f"exit {deleted.returncode}"
        print(f"WARNING: task is integrated, but local branch cleanup failed for {branch}: {detail}")
        return
    print(f"Removed completed worktree and local branch {branch}.")


def reconcile_confirmed_remote_pr_merge(
    work: Path,
    integration: Path,
    config: dict,
    branch: str,
    main_branch: str,
    prof: str,
    *,
    cleanup: bool,
    timeout_seconds: float,
) -> None:
    """Serialize only local post-MERGED reconciliation, never remote waits."""
    try:
        identity = delivery_identity(work)
    except ManagedTaskError as exc:
        raise SystemExit("Managed task provenance is invalid before terminal reconciliation: " + str(exc)) from exc
    with serialized_integration(integration, config, timeout_seconds):
        sync_after_remote_pr_merge(work, integration, config, main_branch)
        try:
            assert_integration_identity_cross_check(integration, identity)
            project = reconcile_managed_project(
                work,
                "Done",
                source_issue=identity.source_issue if identity else None,
            )
        except (ManagedProjectStatusError, ManagedTaskError) as exc:
            raise SystemExit(
                "GitHub confirms the task PR is merged and local main is synchronized, "
                "but managed Project reconciliation is pending: " + str(exc)
            ) from exc
        if project is not None:
            print(
                f"Managed Project status {'updated' if project.changed else 'already current'}: "
                f"{project.source_issue} -> Done"
            )
        if prof == "multi-agent":
            finish_board(integration, work, config)
        if cleanup:
            cleanup_completed_task(work, integration, branch, squash_merged=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate, integrate when needed, and publish a completed task without a human git hand-off.")
    parser.add_argument("--no-checks", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--title")
    parser.add_argument("--body")
    parser.add_argument("--merge-timeout", type=float, default=60.0)
    parser.add_argument("--status", action="store_true", help="Read-only publication status; makes no mutations.")
    parser.add_argument("--json", action="store_true", help="Emit --status output as JSON.")
    args = parser.parse_args()
    if args.json and not args.status:
        parser.error("--json requires --status")
    if args.merge_timeout < 0:
        parser.error("--merge-timeout must be non-negative")
    if args.no_checks and os.environ.get(ALLOW_NO_CHECKS_ENV) != "1":
        raise SystemExit(
            "--no-checks is an emergency/operator override and is blocked by default. "
            f"Set {ALLOW_NO_CHECKS_ENV}=1 only after an explicit decision to bypass validation."
        )
    work = current_worktree_root()
    integration = main_root()
    config = read_platform_config(work)
    if args.status:
        return run_status(work, integration, config, as_json=args.json)
    if harness_mode(config) != "platform":
        raise SystemExit("harness_mode=project: use the repository-owned Git/worktree publication workflow instead of scripts/finish_task.py.")
    prof = profile(config)
    preflight(integration)
    if work != integration:
        preflight(work)
    mode = publish_mode(config)
    main_branch = str(config.get("main_branch", "main"))
    branch = current_branch(work)
    if not branch:
        raise SystemExit("Detached HEAD is not publishable through the platform lifecycle.")
    validate_publication_config(work, config, prof, mode)
    try:
        require_delivery_provenance(work)
    except ManagedTaskError as exc:
        raise SystemExit("Managed task publication blocked: " + str(exc)) from exc
    run_openspec_hygiene(work)
    run_friction_retry_and_checkpoint(work, branch)
    if not clean(work):
        raise SystemExit("Current worktree is dirty. Commit or remove changes first.")
    fetch_main(integration, "origin", main_branch)
    remote_main = f"origin/{main_branch}"

    # Recovery is intentionally checked before local validation against the new
    # remote base. A squash-merged task branch is no longer an ancestor of main,
    # but if GitHub already merged this exact head there is nothing to rebase or
    # republish; only local reconciliation remains.
    if mode == "pr" and branch != main_branch and task_pr_is_already_merged(work, branch, main_branch):
        reconcile_confirmed_remote_pr_merge(
            work, integration, config, branch, main_branch, prof, cleanup=args.cleanup, timeout_seconds=args.merge_timeout
        )
        print("Task PR was already merged through GitHub; local main and task state were reconciled without republishing.")
        return 0

    # An already-open exact-head PR is a resumable remote object: detect it
    # before the first-publication fresh-base precondition below, so recovery
    # of an existing PR is not blocked merely because origin/main advanced
    # after that PR was opened. GitHub required checks/protection/auto-merge/
    # merge queue remain authoritative for whether it can actually integrate.
    exact_open_pr = None
    if mode == "pr" and branch != main_branch:
        exact_open_pr = find_existing_exact_open_pr(work, branch, main_branch)

    warn_current_worktree_scope_overlap(integration, work, branch)
    run_checks(work, remote_main, args.no_checks)
    if mode == "pr":
        if branch == main_branch:
            raise SystemExit("publish_mode=pr requires a feature branch. Use standard/multi-agent profile or switch publish_mode deliberately.")
        if exact_open_pr is None and run_git(["merge-base", "--is-ancestor", remote_main, branch], cwd=work, check=False).returncode != 0:
            raise SystemExit(f"{branch} is stale relative to {remote_main}. Rebase/update explicitly, rerun checks, then finish.")
        if exact_open_pr is not None:
            print(f"Resuming existing exact-head PR: {exact_open_pr.get('url')}")
        command = ["python3", str(work / "scripts" / "project_publish.py"), "--mode", "pr"]
        if args.title:
            command += ["--title", args.title]
        if args.body:
            command += ["--body", args.body]
        subprocess.run(command, cwd=work, check=True)
        if pr_merge_mode(config) == "auto":
            reconcile_confirmed_remote_pr_merge(
                work, integration, config, branch, main_branch, prof, cleanup=args.cleanup, timeout_seconds=args.merge_timeout
            )
            print("Task PR passed required checks, merged through GitHub, and local main was synchronized.")
        else:
            if prof == "standard" and work == integration:
                run_git(["switch", main_branch], cwd=integration)
                print(f"Returned integration copy to {main_branch} after manual-review PR publication.")
            if prof == "multi-agent":
                finish_board(integration, work, config)
            print("Task published as PR for manual review. OpenSpec lifecycle hygiene passed.")
        return 0
    if mode != "direct":
        raise SystemExit(f"Unknown publish_mode: {mode}")
    try:
        identity = delivery_identity(work)
    except ManagedTaskError as exc:
        raise SystemExit("Managed task provenance is invalid before direct publication: " + str(exc)) from exc
    with serialized_integration(integration, config, args.merge_timeout):
        integrate_and_publish_direct(work, integration, config, branch, main_branch)
        try:
            assert_integration_identity_cross_check(integration, identity)
            project = reconcile_managed_project(
                work,
                "Done",
                source_issue=identity.source_issue if identity else None,
            )
        except (ManagedProjectStatusError, ManagedTaskError) as exc:
            raise SystemExit(
                "Direct publication succeeded, but managed Project reconciliation is pending: " + str(exc)
            ) from exc
        if project is not None:
            print(
                f"Managed Project status {'updated' if project.changed else 'already current'}: "
                f"{project.source_issue} -> Done"
            )
        if prof == "multi-agent" and work != integration:
            finish_board(integration, work, config)
    if args.cleanup:
        cleanup_completed_task(work, integration, branch, squash_merged=False)
    print("Task published directly. OpenSpec lifecycle hygiene passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
