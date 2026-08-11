# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic review against proposal/design/delta specs, full local automated validation (compileall, managed-project registry validation, full unit suite including new `tests/test_rollout_preflight.py` and rollout-adjacent additions to `tests/test_publication_state.py`, OpenSpec lifecycle hygiene, strict `openspec validate`), a fresh-render + rendered-project import/doctor smoke via Copier, and a read-only live-data confirmation of the identity/eligibility/required-check logic against a genuine currently-open Dev Platform rollout PR (`lehard/cuby#50`).

## Automated validation

- `python3 -m compileall -q template/scripts scripts` -- clean.
- `python3 scripts/managed_projects.py validate` -- OK (3 managed, 7 candidate, 3 excluded).
- `python3 -m unittest discover -s tests -v` -- **348 tests, all passing**, including the pre-existing rollout/publication/managed-task suites (unmodified behavior preserved) and the new/extended coverage below.
- `python3 template/scripts/openspec_lifecycle.py check` -- OK.
- `openspec validate reconcile-pending-rollout-before-task --strict --json` -- valid, zero issues.

## New/extended regression coverage (task 4.1's required scenarios)

All in `tests/test_rollout_preflight.py` (18 tests) unless noted:

- no pending rollout -> `NONE` (`test_no_open_prs_is_none`, `test_no_matching_branch_pattern_is_none`);
- green pending rollout -> `SAFE_TO_ADOPT` then merged+synced -> `RECONCILED` (`test_green_pr_is_safe_to_adopt`, `test_safe_pr_is_merged_and_synced_to_reconciled`);
- checks pending -> `PENDING_CHECKS` (`test_pending_required_checks_are_pending_checks_state`);
- checks failed -> `BLOCKED` (`test_failed_required_checks_block`);
- conflict/changed head -> `BLOCKED` without partial progress (`test_conflicting_or_changed_head_blocks_without_partial_progress`, `test_merge_accepted_but_head_changed_raises_system_exit_is_translated_to_blocked`, plus `test_changed_head_is_unknown_not_a_silent_pass` in `test_publication_state.py`);
- unexpected/unconfirmed ownership -> `BLOCKED` (`test_similar_pr_from_wrong_author_is_not_treated_as_rollout`, `test_candidate_without_configured_bot_login_blocks_ambiguously`);
- superseded older PR is never selected -> only the newest eligible PR is authoritative (`test_only_newest_eligible_pr_is_considered_authoritative`, and unchanged in `tests/test_rollout_supersession.py`'s existing supersession suite, which now runs against the shared `rollout_identity.py` module);
- remote-merged retry / local-main reconciliation -> idempotent `NONE` on retry once the PR is gone (`test_retry_after_remote_merge_finds_no_open_pr_and_is_idempotently_none`) and a resumable `MERGED_NEEDS_LOCAL_SYNC` when the post-merge sync itself fails (`test_merged_but_local_sync_fails_is_resumable_merged_needs_local_sync`).

`start_task.py` wiring is covered directly in `tests/test_managed_task.py`: a `RECONCILED` outcome still creates the task branch (`test_reconciled_rollout_prints_detail_and_still_creates_the_task_branch`), and a `BLOCKED` outcome raises before any branch exists (`test_blocked_rollout_stops_task_start_before_any_branch_exists`). The pre-existing `test_standard_task_start_creates_feature_branch_before_import` (a bare local repo with no GitHub remote) continues to pass unmodified, which is itself a regression check that an unreachable/unresolvable GitHub context fails *open* (proceeds with a note) rather than blocking every task start -- see "Design correction" below.

## Template render / rendered-project smoke (task 4.2)

`copier copy --trust --defaults --data project_name=...` against this change's dirty working tree (copied to a plain non-git directory first, since Copier resolves a git-backed local source to its last commit, not the working tree) produced a `.dev-platform.toml` containing the new `[tools.rollout] bot_login = "dev-platform-bot-lehard[bot]"` section. `python3 -m compileall -q <rendered>/scripts` was clean, and `agent_doctor`, `start_task`, and `rollout_preflight` all imported successfully from the rendered project, with `rollout_bot_login(config)` correctly resolving to the rendered value. The existing Copier-update-shaped suites (`tests/test_rollout_recopy.py`, `tests/rollout_recopy_smoke.py`, `tests/test_template_contract.py::test_upgrade_smoke_is_part_of_ci`) ran unchanged as part of the full suite above and remain green, so the new `.dev-platform.toml.jinja` section does not disturb guarded-recopy/upgrade behavior.

## Live read-only data validation

`lehard/cuby#50` is a genuine, currently-open Dev Platform rollout PR (head `dev-platform/rollout-v1.4.24`, opened by the platform's real GitHub App). Read-only checks against it, with no mutation of that repository:

- `gh api repos/lehard/cuby/pulls?state=open&base=main` fed directly into this change's real `candidate_rollout_prs`/`eligible_rollout_prs`/`authoritative_pending_rollout` correctly identified PR #50 as the sole candidate and authoritative eligible rollout for `expected_bot="dev-platform-bot-lehard[bot]"`, and correctly returned `None` for a deliberately wrong bot login (negative control).
- `required_check_state_for_ref` against a temporary read-only shallow clone of `lehard/cuby` reported `kind="passed"` for PR #50's real required `platform-ci` check, matching what GitHub's UI shows for that PR.

Together these prove `observe_pending_rollout` would correctly report `SAFE_TO_ADOPT` for this real PR today. The merge/sync half (`reconcile_pending_rollout`'s `_merge_rollout_pr`/`_synchronize_local_main`) was deliberately **not** exercised live against `lehard/cuby` -- actually merging that PR is a real, consequential action on a project outside this task's authorized scope, so that half is verified through `request_protected_merge`/`sync_after_remote_pr_merge`'s own existing, separately-proven test coverage (unchanged and reused, not reimplemented) plus this change's mocked unit tests of the calling convention (exact branch name as the PR reference, fresh `current_pr_head` immediately before merging, `SystemExit` translated to a structured `BLOCKED`/`MERGED_NEEDS_LOCAL_SYNC` result).

## Design correction made during implementation

The original draft treated "GitHub CLI/API unavailable" and "repository cannot be resolved" as `BLOCKED`. That would have made every task start fail whenever `gh` had no resolvable repo context for the current checkout -- confirmed by the pre-existing `test_standard_task_start_creates_feature_branch_before_import` fixture (a bare local repo with no GitHub remote), which broke under that draft. Neither condition is evidence of an actual pending rollout, and neither appears in the proposal/tasks' explicit scenario list, so both now resolve to `NONE` with an informational `detail` (surfaced by `start_task.py`'s print and `agent_doctor.py`'s `warn`) instead of blocking. Genuine misconfiguration of a platform-owned repo (missing `origin`, no `gh` auth) is still caught by `agent_doctor.py`'s pre-existing `require_origin`/gh-auth checks, which already run before this reconciliation step and already fail task start on their own.

## Semantic review

**Completeness: PASS.** All proposal/design decisions and all `tasks.md` items are implemented: shared identity/eligibility contract (`template/scripts/rollout_identity.py`, reused by `scripts/rollout_supersession.py` and this change's `rollout_preflight.py`); the six named states; observation before task-branch/worktree creation in `start_task.py` (covering `start_managed_task.py` too, since it calls `start_task()` directly); ordinary exact-head, non-bypass GitHub merge reusing `project_publish.request_protected_merge`; local-main sync reusing `finish_task.sync_after_remote_pr_merge` under the existing `serialized_integration` lock; read-only visibility for `harness_mode=project` via `agent_doctor.py` without touching its task/worktree entrypoint; `rollout.yml`/`publish-version.yml` untouched; no Development Backlog issue is created anywhere in this change.

**Correctness: PASS.** Ownership is established solely from GitHub's structured PR JSON (reserved branch regex, base ref, repository, and `user.login` against the configured `tools.rollout.bot_login`) -- never title/body. The exact-head guard is layered three times before any merge is requested (the check-state read compares against the head observed during eligibility scanning; `_merge_rollout_pr` re-reads the head fresh immediately before merging; GitHub itself enforces `--match-head-commit`). Supersession/newest-wins selection is delegated to the same sorted-by-version `eligible_rollout_prs` list logic central rollout automation already uses, now in one shared module. No force-push, admin bypass, or partial-progress path exists: a merge rejection or a failed post-merge sync both return a structured, resumable result without a second mutation attempt.

**Coherence: PASS.** The new module composes with existing platform primitives (`_platform_common.github_cli_env`, `publication_state`, `project_publish`, `finish_task`) rather than duplicating them; the one genuinely new safety primitive (`publication_state.required_check_state_for_ref`) was added by extracting the pre-existing check-classification logic into a shared helper, so `required_check_state`'s own behavior and tests are unchanged. `docs/managed-rollout.md` documents the new downstream-adoption behavior and the `tools.rollout.bot_login` config field's provenance (rendered by the Copier template as the platform's real, non-secret GitHub App login, empirically confirmed above) for both new and Copier-updated existing projects.
