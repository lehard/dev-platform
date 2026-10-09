"""Safe, explicit reconciliation of a quick or managed task with authoritative main."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from _platform_common import (
    current_worktree_root,
    fetch_main,
    github_cli_env,
    harness_mode,
    observe_task_base_freshness,
    observe_task_base_freshness_readonly,
    publish_mode,
    read_platform_config,
    relation,
    run_git,
)
try:
    from managed_task import ManagedTaskError, resolve_canonical_provenance
except ModuleNotFoundError:  # Compatibility while older renders are upgraded.
    class ManagedTaskError(RuntimeError):
        pass

    def resolve_canonical_provenance(root: Path):
        return None
import publication_state


RECONCILE_COMMAND = "python3 scripts/finish_task.py --reconcile"
TASK_KIND_MANAGED = "managed"
TASK_KIND_QUICK = "quick"
MANAGED_PROVENANCE_FILE = ".managed-task.json"


@dataclass(frozen=True)
class Freshness:
    state: str
    authoritative_sha: str

    @property
    def reconcile_required(self) -> bool:
        return self.state in {"behind", "diverged"}


def clean(root: Path) -> bool:
    return not run_git(["status", "--porcelain"], cwd=root).stdout.strip()


def current_branch(root: Path) -> str:
    return run_git(["branch", "--show-current"], cwd=root).stdout.strip()


def observe(root: Path, *, read_only: bool = False) -> Freshness:
    """Fetch authoritative main and classify the exact checked-out task head."""
    config = read_platform_config(root)
    main_branch = str(config.get("main_branch", "main"))
    helper = observe_task_base_freshness_readonly if read_only else observe_task_base_freshness
    state, authoritative_sha = helper(root, "origin", main_branch)
    return Freshness(state=state, authoritative_sha=authoritative_sha)


def status_payload(root: Path) -> dict[str, object]:
    """Return bounded freshness evidence for status/preflight callers."""
    freshness = observe(root, read_only=True)
    payload: dict[str, object] = {
        "task_freshness": freshness.state,
        "authoritative_main": freshness.authoritative_sha,
        "reconcile_required": freshness.reconcile_required,
        "reconcile_command": RECONCILE_COMMAND if freshness.reconcile_required else None,
    }
    try:
        provenance = resolve_canonical_provenance(root)
    except ManagedTaskError as exc:
        payload["managed_provenance"] = "ambiguous"
        payload["provenance_detail"] = str(exc)[:300]
    else:
        if provenance is None:
            payload["managed_provenance"] = "absent"
        else:
            payload["managed_provenance"] = "canonical"
            payload["managed_change"] = provenance.change
            payload["managed_lifecycle"] = provenance.lifecycle
    return payload


def task_kind(root: Path, main_branch: str) -> str:
    """Classify the task from the lifecycle state the platform records.

    A managed start records ``.managed-task-state.json`` and a canonical
    managed OpenSpec lineage; ``resolve_canonical_provenance`` resolves it (or
    raises when it is broken/ambiguous).  A quick task is classified only
    when every recorded managed signal is positively absent: no task state
    record, no canonical lineage, no active OpenSpec change without
    provenance, and no managed provenance added by this branch's own commits.
    Anything else stops instead of being guessed.
    """
    try:
        import managed_task
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Task reconciliation cannot determine the task kind: the managed_task lifecycle module is unavailable; "
            "update the rendered platform lifecycle before using --reconcile."
        ) from exc
    try:
        state = managed_task.read_task_state(root)
        provenance = managed_task.resolve_canonical_provenance(root)
        managed_task.require_no_orphan_active_openspec(root)
    except managed_task.ManagedTaskError as exc:
        raise SystemExit("Task reconciliation cannot determine the task kind: " + str(exc)) from exc
    if provenance is not None:
        return TASK_KIND_MANAGED
    if state is not None:
        raise SystemExit(
            "Task reconciliation cannot determine the task kind: a managed task state record exists without a canonical managed lineage."
        )
    base = run_git(["merge-base", "HEAD", f"origin/{main_branch}"], cwd=root, check=False)
    if base.returncode != 0 or not base.stdout.strip():
        detail = base.stderr.strip() or f"exit {base.returncode}"
        raise SystemExit(f"Task reconciliation cannot determine the task kind: no merge base with origin/{main_branch}: {detail}")
    added = run_git(
        ["diff", "--name-only", "--diff-filter=A", base.stdout.strip(), "HEAD", "--", "openspec/changes"], cwd=root
    ).stdout.splitlines()
    branch_provenance = sorted(path for path in added if Path(path).name == MANAGED_PROVENANCE_FILE)
    if branch_provenance:
        raise SystemExit(
            "Task reconciliation cannot determine the task kind: this branch adds managed OpenSpec provenance "
            "without a managed task state record: " + ", ".join(branch_provenance[:5])
        )
    return TASK_KIND_QUICK


def _remote_branch_head(root: Path, branch: str) -> str | None:
    result = run_git(["ls-remote", "--heads", "origin", branch], cwd=root, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split()[0].strip()


def _require_exact_open_pr(root: Path, branch: str, main_branch: str, proof_head: str) -> None:
    """Prove a published branch still belongs to its exact open task PR.

    ``proof_head`` is the SHA the exact open PR head must currently equal. It is
    the local task head for an unchanged branch, or the unchanged remote branch
    head when a proven local descendant is about to continue the same PR.
    """
    env = github_cli_env(root)
    if env is None:
        raise SystemExit("Task reconciliation cannot verify the existing remote task branch without GitHub authentication.")
    lookup = publication_state.find_exact_head_pr(root, env, branch, main_branch, proof_head)
    if not lookup.available:
        raise SystemExit("Task reconciliation cannot read exact PR state; retry after GitHub access is restored.")
    if lookup.stale_open is not None:
        raise SystemExit("Task reconciliation blocked: the remote PR head changed from this local task head.")
    if lookup.exact_merged is not None:
        raise SystemExit("Task reconciliation found an already merged exact PR; rerun finish_task.py to perform terminal local reconciliation.")
    pr = lookup.exact_open
    if pr is None:
        raise SystemExit("Task reconciliation blocked: a remote task branch exists without an exact open task PR.")
    if pr.get("baseRefName") != main_branch:
        raise SystemExit("Task reconciliation blocked: the exact PR base is unreadable or no longer targets authoritative main.")
    expected_owner = publication_state.github_repo_name(root, env)
    expected_owner = expected_owner.split("/", 1)[0] if expected_owner else None
    owner_payload = pr.get("headRepositoryOwner")
    actual_owner = owner_payload.get("login") if isinstance(owner_payload, dict) else None
    if isinstance(owner_payload, str) and owner_payload.strip():
        actual_owner = owner_payload.strip()
    actual_owner = actual_owner or publication_state.pr_head_repository_owner(
        root, env, publication_state.stable_pr_ref(pr)
    )
    if not expected_owner or actual_owner != expected_owner:
        raise SystemExit("Task reconciliation blocked: the exact PR head owner is unreadable or differs from the authoritative repository owner.")


def _require_exact_merged_is_terminal(root: Path, branch: str, main_branch: str) -> None:
    """Route an already merged exact PR to terminal finish, never to a new head.

    This runs before any authoritative-main merge so a squash-merged delivery
    whose remote branch is already deleted is not reconciled into a fresh task
    head that a later finish would republish.
    """
    env = github_cli_env(root)
    if env is None:
        return
    lookup = publication_state.find_exact_local_branch_pr(root, env, branch, main_branch)
    if lookup.available and lookup.exact_merged is not None:
        raise SystemExit(
            "Task reconciliation found the exact task PR already merged; run "
            "python3 scripts/finish_task.py to perform terminal local-main reconciliation without republishing."
        )


def _continue_exact_pr_from_local_descendant(
    root: Path, branch: str, main_branch: str, remote_branch_head: str, local_head: str
) -> None:
    """Fast-forward the exact open PR branch to a proven local CI-fix descendant.

    Only a strict fast-forward is attempted: the exact open PR is proven at the
    unchanged remote head first, the descendant is pushed without force, and PR
    identity is re-proven at the new head. Any non-fast-forward or changed
    remote/PR identity keeps the strict refusal.
    """
    if relation(root, remote_branch_head, local_head) != "behind":
        raise SystemExit("Task reconciliation blocked: remote task branch head differs from the local exact task head.")
    _require_exact_open_pr(root, branch, main_branch, remote_branch_head)
    pushed = run_git(["push", "origin", f"{local_head}:refs/heads/{branch}"], cwd=root, check=False)
    if pushed.returncode != 0:
        detail = pushed.stderr.strip() or pushed.stdout.strip() or f"exit {pushed.returncode}"
        raise SystemExit(
            "Task reconciliation could not fast-forward the exact PR branch to the local descendant: " + detail
        )
    if _remote_branch_head(root, branch) != local_head:
        raise SystemExit("Remote task branch head changed while continuing the exact PR; refusing to proceed without re-observation.")
    _require_exact_open_pr(root, branch, main_branch, local_head)
    print(
        f"Fast-forwarded exact PR branch {branch} to the local descendant {local_head}; "
        "the same pull request continues."
    )


def _conflict_paths(root: Path) -> list[str]:
    result = run_git(["diff", "--name-only", "--diff-filter=U"], cwd=root, check=False)
    return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})


def reconcile(root: Path | None = None) -> Freshness:
    """Incorporate current main by normal merge only; never reset, stash, or rebase."""
    root = (root or current_worktree_root()).resolve()
    config = read_platform_config(root)
    if harness_mode(config) != "platform" or publish_mode(config) != "pr":
        raise SystemExit("Task reconciliation is supported only for harness_mode=platform, publish_mode=pr tasks.")
    main_branch = str(config.get("main_branch", "main"))
    kind = task_kind(root, main_branch)
    print(f"Task reconciliation: {kind} task.")
    branch = current_branch(root)
    if not branch or branch == main_branch:
        raise SystemExit("Task reconciliation requires a checked-out feature branch.")
    if run_git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=root, check=False).returncode == 0:
        conflicts = _conflict_paths(root)
        suffix = (" Conflicting paths: " + ", ".join(conflicts) + ".") if conflicts else ""
        raise SystemExit("Task reconciliation has an unfinished merge; resolve it or explicitly abort it before rerunning reconcile." + suffix)
    if not clean(root):
        raise SystemExit("Task reconciliation blocked: the task worktree is dirty. Commit or resolve it explicitly; automatic stash/reset is forbidden.")

    _require_exact_merged_is_terminal(root, branch, main_branch)

    before = observe(root)
    local_head = run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    remote_branch_head = _remote_branch_head(root, branch)
    published = remote_branch_head is not None
    if published:
        if remote_branch_head != local_head:
            _continue_exact_pr_from_local_descendant(
                root, branch, main_branch, remote_branch_head, local_head
            )
            remote_branch_head = local_head
        else:
            _require_exact_open_pr(root, branch, main_branch, local_head)

    if not before.reconcile_required:
        print(f"Task branch is already current relative to origin/{main_branch} ({before.state}); reconcile is a no-op.")
        return before

    result = run_git(["merge", "--no-edit", f"origin/{main_branch}"], cwd=root, check=False)
    if result.returncode != 0:
        conflicts = _conflict_paths(root)
        if conflicts:
            raise SystemExit(
                "Task reconciliation stopped at merge conflicts. Resolve explicitly, then commit the merge; conflicting paths: "
                + ", ".join(conflicts)
            )
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise SystemExit("Task reconciliation failed without rewriting task history: " + detail)

    # Re-observe both authority and published identity.  A moving base/head is
    # not silently accepted as a successful reconciliation.
    after = observe(root)
    if after.authoritative_sha != before.authoritative_sha:
        raise SystemExit("Authoritative main changed during reconciliation; rerun reconcile against the newly observed head before validation.")
    if after.reconcile_required:
        raise SystemExit("Task is still behind authoritative main after reconciliation; rerun reconcile before validation.")
    if published:
        if _remote_branch_head(root, branch) != local_head:
            raise SystemExit("Remote task branch head changed during reconciliation; refusing to publish the new descendant automatically.")
        _require_exact_open_pr(root, branch, main_branch, local_head)
        pushed = run_git(["push", "origin", branch], cwd=root, check=False)
        if pushed.returncode != 0:
            detail = pushed.stderr.strip() or pushed.stdout.strip() or f"exit {pushed.returncode}"
            raise SystemExit(
                "Reconciled task head was retained locally but not pushed because the remote branch may have changed: " + detail
            )
    print(
        f"Reconciled {branch} with origin/{main_branch} at {after.authoritative_sha} using normal Git history. "
        "The resulting head is new execution state: rerun validation and then resume the existing exact-head publication flow."
    )
    return after


def main() -> int:
    reconcile()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
