from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Callable, ContextManager

from _platform_common import (
    FINISH_COMMAND,
    ci_completion_seconds,
    current_worktree_root,
    fetch_main,
    github_cli_env,
    main_root,
    pr_merge_mode,
    protected_main,
    publish_mode,
    read_platform_config,
    relation,
    require_origin,
    run_git,
    run_github_with_retry,
    preflight,
)
from integration_state import guard_before_protected_merge
from publication_state import (
    ExactHeadPrLookup,
    PrRef,  # re-exported: the canonical definition lives in the always-platform-owned publication_state
    find_exact_head_pr,
    required_check_state_for_ref,
    stable_pr_ref,
)
from managed_project_status import ManagedProjectStatusError, reconcile as reconcile_managed_project
from requirement_integration import RequirementIntegrationError, require_independent_publication_exception
import requirement_integration
from managed_task import ManagedTaskError, require_delivery_provenance


DIRECT_PUBLISH_GUARD = "DEV_PLATFORM_VALIDATED_DIRECT_PUBLISH"
MERGE_POLL_INTERVAL_SECONDS = 20.0
MERGE_SNAPSHOT_FIELDS = "state,headRefOid,autoMergeRequest,mergeStateStatus"
PRE_MERGE_GUARD_TIMEOUT_SECONDS = 60.0


def _pr_ref(pr: dict, *, already_merged: bool = False) -> PrRef:
    # Validate the candidate before retaining it as a publication cursor.
    stable_pr_ref(pr)
    number = pr.get("number")
    return PrRef(number if isinstance(number, int) else None, str(pr.get("url", "")), already_merged)


def clean(root: Path) -> bool:
    return not run_git(["status", "--porcelain"], cwd=root).stdout.strip()


def branch(root: Path) -> str:
    return run_git(["branch", "--show-current"], cwd=root).stdout.strip()


def require_gh_environment(root: Path, *, branch_pushed: bool = False) -> dict[str, str]:
    env = github_cli_env(root)
    if env is not None:
        return env
    suffix = " The validated feature branch is already pushed." if branch_pushed else ""
    raise SystemExit(
        "GitHub PR API authentication is unavailable."
        + suffix
        + " Install gh if needed, provide a valid GH_TOKEN/GITHUB_TOKEN, or configure a persistent gh/Git HTTPS credential."
    )


def publish_direct(root: Path, remote: str, main_branch: str) -> int:
    if os.environ.get(DIRECT_PUBLISH_GUARD) != "1":
        raise SystemExit(
            "Direct publication must be invoked by the validated finish_task lifecycle. "
            f"For an explicit emergency/operator override, set {DIRECT_PUBLISH_GUARD}=1 yourself."
        )
    integration = main_root()
    preflight(integration)
    if root != integration:
        raise SystemExit("Direct publication must run from the integration copy after local integration.")
    if branch(integration) != main_branch:
        raise SystemExit(f"Direct publication requires {main_branch!r} checked out.")
    if not clean(integration):
        raise SystemExit("Integration copy is dirty. Commit or remove changes before publishing.")
    require_origin(integration, remote)
    fetch_main(integration, remote, main_branch)
    remote_branch = f"{remote}/{main_branch}"
    state = relation(integration, main_branch, remote_branch)
    if state == "equal":
        print(f"Nothing to publish: {main_branch} already equals {remote_branch}.")
        return 0
    if state != "ahead":
        raise SystemExit(f"Refusing direct push: local {main_branch} vs {remote_branch} is {state}. Fetch/reconcile explicitly.")
    run_git(["push", remote, f"{main_branch}:{main_branch}"], cwd=integration)
    print(f"Published {main_branch} -> {remote}/{main_branch}.")
    return 0


def _validate_feature_branch(root: Path, remote: str, main_branch: str) -> str:
    current = branch(root)
    if not current or current == main_branch:
        raise SystemExit("PR publication requires a feature branch, not the integration branch.")
    if not clean(root):
        raise SystemExit("Task worktree is dirty. Commit or remove changes before publishing.")
    require_origin(root, remote)
    return current


def push_feature_branch(root: Path, remote: str, main_branch: str, *, require_fresh_base: bool) -> str:
    """Push the validated feature branch; the push itself is always safe/idempotent.

    `require_fresh_base` gates only the first-publication precondition that the
    branch already contains current `{remote}/{main_branch}`. Recovery of an
    already-existing exact-head PR passes `require_fresh_base=False`: that PR's
    `headRefOid` already proves this exact commit reached GitHub, so an
    already-published branch must not be blocked from resuming merely because
    the base advanced after that PR was opened -- pushing again is a harmless
    no-op fast-forward to the same commit.
    """
    preflight(root)
    current = _validate_feature_branch(root, remote, main_branch)
    main_sha = fetch_main(root, remote, main_branch)
    if require_fresh_base and run_git(["merge-base", "--is-ancestor", main_sha, current], cwd=root, check=False).returncode != 0:
        raise SystemExit(f"{current} does not contain current {remote}/{main_branch}. Rebase/update explicitly, rerun checks, then publish.")
    run_git(["push", "-u", remote, current], cwd=root)
    print(f"Published feature branch {current} -> {remote}/{current}.")
    return current


def _safe_presentation(root: Path, title: str, body: str, identity: str,
                       children: list[str] | None) -> tuple[str, str]:
    import managed_work_identity
    title, body = managed_work_identity.presentation(title, body, identity, children)
    guard = _private_reference_guard(root)
    if guard is not None:
        subprocess.run(["python3", str(guard), "--root", str(root), "--text", title, "--text", body], cwd=root, check=True, stdin=subprocess.DEVNULL)
    return title, body


def _private_reference_guard(root: Path) -> Path | None:
    """The private-reference guard where private lineage is enabled; ``None`` (reported) where it does not apply."""
    import private_lineage

    try:
        guard = private_lineage.guard_script(root)
    except private_lineage.PrivateLineageError as exc:
        raise SystemExit("private-reference publication guard blocked: " + str(exc)) from exc
    if guard is None:
        print(private_lineage.GUARD_NOT_APPLICABLE, flush=True)
    return guard


def _repair_pr_identity(root: Path, env: dict[str, str], pr: PrRef, expected_head: str,
                        identity: str | None, children: list[str] | None) -> PrRef:
    if identity is None:
        return pr
    from _platform_common import run_github_with_retry

    observed = run_github_with_retry(["gh", "pr", "view", pr.ref, "--json", "title,body,headRefOid"], cwd=root, env=env)
    if observed.returncode:
        raise subprocess.CalledProcessError(observed.returncode, observed.args, observed.stdout, observed.stderr)
    payload = json.loads(observed.stdout)
    if payload.get("headRefOid") != expected_head:
        raise SystemExit("PR head changed before BR identity repair; publication remains resumable.")
    title, body = _safe_presentation(root, payload["title"], payload.get("body") or "", identity, children)
    if (title, body) != (payload["title"], payload.get("body") or ""):
        subprocess.run(["gh", "pr", "edit", pr.ref, "--title", title, "--body", body],
                       cwd=root, env=env, text=True, capture_output=True, check=True, stdin=subprocess.DEVNULL)
    return pr


def ensure_pr(
    root: Path,
    env: dict[str, str],
    current: str,
    main_branch: str,
    title: str | None,
    body: str | None,
    expected_head: str,
    lookup: ExactHeadPrLookup | None = None,
    *,
    draft: bool = False,
    identity: str | None = None,
    children: list[str] | None = None,
) -> PrRef:
    """Reuse an exact-head PR if one exists; otherwise create one.

    Ownership is decided by repository/base branch + task head branch + exact
    `headRefOid`, never by title/body text or a remembered PR number. A create
    race against a concurrent publisher is resolved by re-observing GitHub and
    reusing whatever exact PR won, instead of producing a duplicate.
    """
    if lookup is None:
        lookup = find_exact_head_pr(root, env, current, main_branch, expected_head)
    if not lookup.available:
        raise SystemExit("GitHub PR state is unavailable; publication remains resumable without local-main mutation.")
    if lookup.exact_open is not None:
        url = str(lookup.exact_open.get("url", ""))
        print(f"PR already exists for exact task head: {url}")
        return _repair_pr_identity(root, env, _pr_ref(lookup.exact_open), expected_head, identity, children)
    if lookup.exact_merged is not None:
        url = str(lookup.exact_merged.get("url", ""))
        print(f"PR already merged on GitHub for exact task head: {url}")
        return _repair_pr_identity(root, env, _pr_ref(lookup.exact_merged, already_merged=True), expected_head, identity, children)

    if not title:
        title = run_git(["log", "-1", "--pretty=%s"], cwd=root).stdout.strip() or current
    if body is None:
        body = "Published by dev-platform after local validation and a fresh origin/main check."
    if identity is not None:
        title, body = _safe_presentation(root, title, body, identity, children)
    created = subprocess.run(
        ["gh", "pr", "create", "--base", main_branch, "--head", current, "--title", title, "--body", body,
         *(["--draft"] if draft else [])],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    if created.returncode == 0:
        # The create command's URL is not yet proof that it names the current
        # head. Re-enumerate the full tuple and retain only the stable exact PR.
        created_lookup = find_exact_head_pr(root, env, current, main_branch, expected_head)
        if created_lookup.available and created_lookup.exact_open is not None:
            pr = _pr_ref(created_lookup.exact_open)
            print(pr.url)
            return _repair_pr_identity(root, env, pr, expected_head, identity, children)
        raise SystemExit("PR creation returned success, but GitHub did not expose one stable exact-head PR; refusing to continue.")

    # A concurrent publisher may have created the exact PR between our lookup
    # and this create attempt. Re-observe and reuse it instead of treating the
    # race as a reason to create competing delivery work.
    retry = find_exact_head_pr(root, env, current, main_branch, expected_head)
    if retry.available and retry.exact_open is not None:
        url = str(retry.exact_open.get("url", ""))
        print(f"PR creation lost a race with a concurrent publisher; reusing exact PR: {url}")
        return _repair_pr_identity(root, env, _pr_ref(retry.exact_open), expected_head, identity, children)
    detail = created.stderr.strip() or created.stdout.strip() or f"exit {created.returncode}"
    raise SystemExit(f"gh pr create failed: {detail}")


def _set_pr_draft(root: Path, env: dict[str, str], pr: PrRef, *, draft: bool) -> None:
    command = ["gh", "pr", "ready", pr.ref] + (["--undo"] if draft else [])
    result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise SystemExit(f"Could not set shared PR {'draft' if draft else 'ready'} state: {detail}")


def exact_merged_state(root: Path, env: dict[str, str], pr: PrRef, expected_head: str) -> bool:
    """Return true only for the previously selected PR at the validated head."""
    result = subprocess.run(
        ["gh", "pr", "view", pr.ref, "--json", "state,headRefOid"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return False
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return (
        isinstance(payload, dict)
        and str(payload.get("state", "")).upper() == "MERGED"
        and str(payload.get("headRefOid", "")).strip() == expected_head
    )


def _merge_snapshot(root: Path, env: dict[str, str], pr: PrRef, expected_head: str) -> dict:
    result = run_github_with_retry(["gh", "pr", "view", pr.ref, "--json", MERGE_SNAPSHOT_FIELDS], cwd=root, env=env)
    detail = (result.stderr or result.stdout).strip()[:200] or f"exit {result.returncode}"
    if result.returncode:
        raise SystemExit(f"PR {pr.ref} cannot be read while following auto-merge: {detail}. "
                         f"Local main was not changed; continue with: {FINISH_COMMAND}")
    try:
        snapshot = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"PR {pr.ref} state is not JSON: {detail}. Local main was not changed; "
                         f"continue with: {FINISH_COMMAND}") from exc
    if not isinstance(snapshot, dict):
        raise SystemExit(f"PR {pr.ref} state is not a JSON object: {detail}. Local main was not changed; "
                         f"continue with: {FINISH_COMMAND}")
    observed = str(snapshot.get("headRefOid", "")).strip()
    if observed != expected_head:
        raise SystemExit(f"PR {pr.ref} head is {observed or 'unknown'}, not the validated head {expected_head}; "
                         "this publication no longer applies. Local main was not changed.")
    return snapshot


def wait_for_merge_outcome(root: Path, env: dict[str, str], pr: PrRef, expected_head: str, *, timeout_seconds: float) -> None:
    """Follow armed auto-merge to MERGED; every other outcome is a refusal that names its cause.

    ``timeout_seconds`` is the configured time in which required CI has certainly finished, so reaching it
    means something is wrong, not that the PR is slow. GitHub keeps the request after any refusal here.
    """
    deadline = time.monotonic() + timeout_seconds
    reported = None
    while True:
        snapshot = _merge_snapshot(root, env, pr, expected_head)
        state = str(snapshot.get("state", "")).upper()
        if state == "MERGED":
            return
        if state != "OPEN":
            raise SystemExit(f"PR {pr.ref} is {state or 'unknown'}, not merged. Local main was not changed.")
        checks = required_check_state_for_ref(root, env, pr.ref, expected_head)
        if checks.kind == "failed":
            raise SystemExit(f"Required check failed for head {expected_head}: {checks.detail}. The PR stays open; "
                             "local main was not changed. Fix the cause, commit and rerun finish.")
        if checks.kind not in {"pending", "passed"}:
            raise SystemExit(f"GitHub required-check state is {checks.kind} ({checks.cause}): {checks.detail}. "
                             f"Local main was not changed; continue with: {FINISH_COMMAND}")
        merge_state = str(snapshot.get("mergeStateStatus", "")).upper()
        if merge_state in {"BEHIND", "DIRTY"}:
            raise SystemExit(f"PR {pr.ref} cannot merge: GitHub reports it {merge_state} against its base. Local main "
                             "was not changed. Reconcile with python3 scripts/finish_task.py --reconcile, rerun finish.")
        if snapshot.get("autoMergeRequest") is None:
            raise SystemExit(f"PR {pr.ref} no longer has auto-merge armed, so nothing will merge it. "
                             f"Local main was not changed; arm it again with: {FINISH_COMMAND}")
        if time.monotonic() >= deadline:
            raise SystemExit(f"PR {pr.ref} did not merge within ci_completion_minutes ({timeout_seconds / 60:g} min) "
                             f"although required CI must have finished by then; last required-check state: "
                             f"{checks.kind}, merge state: {merge_state or 'unknown'}. Inspect the PR; auto-merge stays "
                             f"armed and local main was not changed. Continue with: {FINISH_COMMAND}")
        if checks.kind != reported:
            print(f"Following PR {pr.ref}: required checks {checks.kind}, waiting for MERGED.", flush=True)
            reported = checks.kind
        time.sleep(MERGE_POLL_INTERVAL_SECONDS)


def follow_armed_merge(root: Path, env: dict[str, str], current: str, pr: PrRef, remote: str, expected_head: str,
                       *, timeout_seconds: float) -> None:
    """Wait out one armed exact-head PR and drop its remote branch; shared by first publication and a rerun."""
    wait_for_merge_outcome(root, env, pr, expected_head, timeout_seconds=timeout_seconds)
    delete_remote_branch(root, remote, current)
    print(f"Merged PR for {current} through GitHub.")


def delete_remote_branch(root: Path, remote: str, current: str) -> None:
    exists = run_git(["ls-remote", "--exit-code", "--heads", remote, current], cwd=root, check=False)
    if exists.returncode != 0:
        print(f"Remote feature branch {remote}/{current} is already absent.")
        return
    deleted = run_git(["push", remote, "--delete", current], cwd=root, check=False)
    if deleted.returncode != 0:
        # GitHub's own delete-on-merge can win the race after the first observation; exit 2 proves the ref is gone.
        if run_git(["ls-remote", "--exit-code", "--heads", remote, current], cwd=root, check=False).returncode == 2:
            print(f"Remote feature branch {remote}/{current} is already absent.")
            return
        detail = deleted.stderr.strip() or deleted.stdout.strip() or f"exit {deleted.returncode}"
        print(f"WARNING: PR is merged, but remote branch cleanup failed for {remote}/{current}: {detail}")
        return
    print(f"Deleted remote feature branch {remote}/{current} after confirmed merge.")


def require_mergeable_checks(root: Path, env: dict[str, str], pr: PrRef, expected_head: str) -> None:
    """Refuse a merge request that GitHub would not gate on required checks.

    Without a required check on the base, `gh pr merge --auto` merges the head at once, so
    "no required checks" is a refusal, never a pass. Only pending or passed checks go on.
    """
    state = required_check_state_for_ref(root, env, pr.ref, expected_head)
    if state.kind == "not_registered":
        raise SystemExit(
            f"Refusing to merge PR {pr.ref}: GitHub reports no required checks for head {expected_head} "
            f"({state.detail or 'no required check is attached'}), so nothing would gate the merge. Require a status "
            "check on the base branch, or set pr_merge_mode=manual. The PR stays open; local main was not changed."
        )
    if state.kind == "failed":
        raise SystemExit(f"Required PR checks failed for head {expected_head}: {state.detail}. "
                         "The PR stays open; local main was not changed.")
    if state.kind not in {"pending", "passed"}:
        raise SystemExit(f"GitHub required-check state is {state.kind} ({state.cause}): {state.detail}. "
                         "The PR stays open; local main was not changed.")


def request_protected_merge(
    root: Path,
    env: dict[str, str],
    current: str,
    pr: PrRef,
    remote: str,
    expected_head: str,
    *,
    timeout_seconds: float,
    merge_guard: Callable[[], ContextManager[None]] | None = None,
) -> None:
    """Arm GitHub auto-merge for the exact validated head, the one merge action, and follow it to its outcome.

    `--match-head-commit` makes GitHub itself refuse any other head. A rejected request stops the
    publication with GitHub's reason. An accepted request survives this process, so a stop while
    following it leaves a rerun of finish to pick the same PR up.
    """
    require_mergeable_checks(root, env, pr, expected_head)
    with merge_guard() if merge_guard is not None else nullcontext():
        result = subprocess.run(
            ["gh", "pr", "merge", pr.ref, "--auto", "--squash", "--match-head-commit", expected_head],
            cwd=root, env=env, text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL,
        )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise SystemExit(f"GitHub refused auto-merge for exact head {expected_head}: {detail}. Local main was not changed.")
    print(f"GitHub accepted auto-merge with squash for exact validated head {expected_head}.")
    follow_armed_merge(root, env, current, pr, remote, expected_head, timeout_seconds=timeout_seconds)


def validate_shared_manifest(root: Path, path: Path) -> dict:
    """Bind shared publication to one exact committed Requirement candidate."""
    if path.is_absolute() or ".." in path.parts or path.parent != Path("dev-platform/requirement-integrations") or path.suffix != ".json":
        raise RequirementIntegrationError("shared manifest must use its canonical repository-relative path")
    try:
        payload = json.loads((root / path).read_text(encoding="utf-8"))
        shown = run_git(["show", f"HEAD:{path.as_posix()}"], cwd=root, check=False)
        if shown.returncode:
            raise ValueError("missing committed manifest")
        committed = json.loads(shown.stdout)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RequirementIntegrationError("shared manifest is absent or not committed at exact HEAD") from exc
    if not isinstance(payload, dict) or payload != committed:
        raise RequirementIntegrationError("shared manifest differs from exact committed HEAD")
    unsigned = {key: value for key, value in payload.items() if key != "digest"}
    requirement = payload.get("requirement")
    children = payload.get("children")
    private_raw = os.environ.get("DEV_PLATFORM_PRIVATE_MANIFEST")
    private_manifest = None
    if private_raw:
        try:
            private_manifest = json.loads(private_raw)
        except json.JSONDecodeError as exc:
            raise RequirementIntegrationError("private integration evidence is malformed") from exc
    opaque = private_manifest is not None
    if (payload.get("digest") != requirement_integration._digest(unsigned)
            or not isinstance(requirement, str)
            or (not requirement_integration.ISSUE_RE.fullmatch(requirement) and not (opaque and re.fullmatch(r"pln_[0-9a-f]{32}", requirement)))
            or not isinstance(children, list) or len(children) < requirement_integration._min_children(payload)
            or any(not isinstance(child, dict) or not isinstance(child.get("source_issue"), str)
                   or not (re.fullmatch(r"pln_[0-9a-f]{32}", child["source_issue"])
                           if opaque else requirement_integration.ISSUE_RE.fullmatch(child["source_issue"])) for child in children)
            or len({child["source_issue"] for child in children}) != len(children)):
        raise RequirementIntegrationError("shared manifest identity or digest is invalid")
    expected_changes = payload.get("expected_changes")
    if expected_changes is not None and (
        not isinstance(expected_changes, list) or len(expected_changes) < 2 or len(set(expected_changes)) != len(expected_changes)
        or [child.get("change") for child in children] != expected_changes[:len(children)]
    ):
        raise RequirementIntegrationError("shared manifest expected changes are invalid")
    if opaque:
        if not isinstance(private_manifest, dict) or requirement_integration._public_manifest(main_root(), private_manifest) != payload:
            raise RequirementIntegrationError("public manifest does not match exact private lineage")
    generation = payload.get("generation")
    expected = requirement_integration._candidate_slug(requirement, generation)
    if payload.get("mode") == "exact-parent-merge":
        expected += "-merge"
    elif payload.get("mode") is not None:
        raise RequirementIntegrationError("shared manifest mode is unsupported")
    canonical_path = requirement_integration._candidate_manifest_path(requirement)
    if payload.get("mode") == "exact-parent-merge":
        import requirement_merge_recovery
        canonical_path = requirement_merge_recovery._manifest_path(payload)
    if path != canonical_path or branch(root) != "agent/" + expected:
        raise RequirementIntegrationError("shared manifest does not identify the candidate branch")
    exact = private_manifest if opaque else payload
    requirement_integration._verify_parent_links(main_root(), exact)
    requirement_integration.publication_identities(main_root(), exact)
    return payload


def publish_pr(
    root: Path,
    remote: str,
    main_branch: str,
    title: str | None,
    body: str | None,
    merge_mode: str,
    *,
    config: dict | None = None,
    shared_manifest: Path | None = None,
) -> int:
    if config is None:
        config = read_platform_config(root)
    try:
        delivery = require_delivery_provenance(root)
        if delivery is not None:
            require_independent_publication_exception(root, delivery)
    except (ManagedTaskError, RequirementIntegrationError) as exc:
        raise SystemExit("Managed task publication blocked: " + str(exc)) from exc
    incomplete = False
    shared_candidate: dict = {}
    if shared_manifest is not None:
        try:
            shared_candidate = validate_shared_manifest(root, shared_manifest)
            incomplete = not requirement_integration.manifest_complete(shared_candidate)
        except RequirementIntegrationError as exc:
            raise SystemExit("Shared Requirement publication blocked: " + str(exc)) from exc
    identity = None
    child_identities = None
    if shared_manifest is not None or delivery is not None:
        import managed_work_identity
        try:
            if shared_manifest is not None:
                exact = json.loads(os.environ["DEV_PLATFORM_PRIVATE_MANIFEST"]) if os.environ.get("DEV_PLATFORM_PRIVATE_MANIFEST") else shared_candidate
                identity, child_identities = requirement_integration.publication_identities(main_root(), exact)
            elif delivery is not None:
                import managed_task
                identity = managed_work_identity.canonical_child_identity(root, delivery.source_issue,
                    provenance=managed_task.read_provenance(delivery.path))
        except (managed_work_identity.IdentityError, RequirementIntegrationError, ManagedTaskError) as exc:
            raise SystemExit("BR publication identity blocked: " + str(exc)) from exc
    privacy_guard = _private_reference_guard(root)
    if privacy_guard is not None:
        proposed_title = title or run_git(["log", "-1", "--pretty=%s"], cwd=root).stdout.strip()
        proposed_body = body or "Published by dev-platform after local validation and a fresh origin/main check."
        subprocess.run(
            ["python3", str(privacy_guard), "--root", str(root), "--text", proposed_title, "--text", proposed_body],
            cwd=root, check=True,
         stdin=subprocess.DEVNULL)
    current = _validate_feature_branch(root, remote, main_branch)
    env = require_gh_environment(root)
    expected_head = run_git(["rev-parse", current], cwd=root).stdout.strip()

    # An already-open (or already-merged) exact-head PR is a resumable remote
    # object: recovery does not require re-applying the first-publication
    # freshness precondition, even if the base has advanced since that PR was
    # opened -- GitHub protection and auto-merge remain authoritative for
    # whether it can still integrate. The push itself still happens whenever
    # the PR isn't already merged: it is a harmless idempotent no-op when the
    # exact head is already on GitHub, and it is the actual first-publication
    # push otherwise.
    lookup = find_exact_head_pr(root, env, current, main_branch, expected_head)
    if not lookup.available:
        raise SystemExit("GitHub PR state is unavailable; publication remains resumable without local-main mutation.")
    # An early shared candidate grows by fast-forward pushes to the one existing PR; that PR
    # (open with an older head) already proves first publication, so no fresh-base rule applies.
    grows_existing = shared_manifest is not None and lookup.stale_open is not None
    if lookup.exact_merged is None:
        push_feature_branch(root, remote, main_branch, require_fresh_base=lookup.exact_open is None and not grows_existing)
        if grows_existing:
            lookup = find_exact_head_pr(root, env, current, main_branch, expected_head)
            if not lookup.available or lookup.exact_open is None:
                raise SystemExit("Shared candidate push did not leave one exact-head PR; refusing to create a competing PR.")

    pr = ensure_pr(root, env, current, main_branch, title, body, expected_head, lookup=lookup, draft=incomplete, **({"identity": identity, "children": child_identities} if identity else {}))
    if pr.already_merged:
        if not exact_merged_state(root, env, pr, expected_head):
            raise SystemExit("Previously discovered merged PR no longer proves MERGED at the exact validated head; refusing cleanup.")
        delete_remote_branch(root, remote, current)
        print(f"PR for {current} was already merged on GitHub for the exact validated head; nothing further to merge.")
        return 0
    if shared_manifest is not None:
        is_draft = bool(lookup.exact_open.get("isDraft")) if lookup.exact_open is not None else incomplete
        if incomplete and not is_draft:
            _set_pr_draft(root, env, pr, draft=True)
        if incomplete:
            print("Shared Requirement candidate is incomplete (missing: "
                  + ", ".join(requirement_integration.missing_changes(shared_candidate))
                  + "): draft PR only; ready and merge are not attempted.")
            return 0
        if is_draft:
            _set_pr_draft(root, env, pr, draft=False)
    try:
        project = None if shared_manifest is not None else reconcile_managed_project(root, "In review")
    except ManagedProjectStatusError as exc:
        raise SystemExit(
            "Reviewable PR exists, but managed Project reconciliation is pending: " + str(exc)
        ) from exc
    if project is not None:
        print(
            f"Managed Project status {'updated' if project.changed else 'already current'}: "
            f"{project.source_issue} -> In review"
        )
    if merge_mode == "manual":
        print("PR published for manual review; pr_merge_mode=manual, so no merge was attempted.")
        return 0
    if merge_mode != "auto":
        raise SystemExit(f"Unknown pr_merge_mode: {merge_mode!r}; expected 'auto' or 'manual'.")

    integration = main_root()

    def merge_guard() -> ContextManager[None]:
        return guard_before_protected_merge(
            integration, config, remote, main_branch, PRE_MERGE_GUARD_TIMEOUT_SECONDS
        )

    request_protected_merge(root, env, current, pr, remote, expected_head,
                            timeout_seconds=ci_completion_seconds(config, SystemExit), merge_guard=merge_guard)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish completed work to GitHub using the project's configured safety mode.")
    parser.add_argument("--mode", choices=["direct", "pr"])
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--title")
    parser.add_argument("--body")
    parser.add_argument("--shared-manifest", type=Path, help="committed shared Requirement manifest; skip single-child Project attribution")
    args = parser.parse_args()
    root = current_worktree_root()
    config = read_platform_config(root)
    mode = args.mode or publish_mode(config)
    main_branch = config["main_branch"]
    if mode == "direct":
        if protected_main(config):
            raise SystemExit("protected_main=true is incompatible with direct publication. Use PR publication so required checks can gate the merge.")
        return publish_direct(root, args.remote, main_branch)
    return publish_pr(root, args.remote, main_branch, args.title, args.body, pr_merge_mode(config), config=config,
                      shared_manifest=args.shared_manifest)


if __name__ == "__main__":
    raise SystemExit(main())
