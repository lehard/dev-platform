# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic review against proposal/design/delta spec, local automated validation (compileall, managed-project registry validation, full unit suite including the new `tests/test_rollout_control_plane_regressions.py`, OpenSpec lifecycle hygiene, strict OpenSpec validation with the CI-pinned openspec 1.6.0), plus real live-rollout acceptance evidence from the actual `v1.4.22` managed rollout run (31469600804) against all three current `managed` projects.

## Automated validation

- `python3 -m compileall -q template/scripts scripts` -- passed.
- `python3 scripts/managed_projects.py validate` -- OK (3 managed, 7 candidate, 3 excluded).
- `python3 -m unittest discover -s tests` -- 251 tests passed.
- `python3 template/scripts/openspec_lifecycle.py check` -- OK.
- `npx --yes @fission-ai/openspec@1.6.0 validate --all --strict --no-interactive` (pinned, matching this repository's CI pin) -- 12/12 passed.
- This change touches no `template/` files, so no Copier render/upgrade-smoke was required per its own design.md; the standard three-profile `tests/upgrade_smoke.py` plus `tests/project_harness_adoption_smoke.py`/`tests/rollout_recopy_smoke.py` were already re-verified as part of the surrounding `wire-runtime-delegation-containment` publication and were not invalidated by this change.

## Live rollout acceptance (task 9)

Release `v1.4.22` (tag SHA `d18a1e0a111dc5e16d6fae5e1daecee0718b27a3`) was published through the normal `release: vX.Y.Z` PR flow (#94). The release workflow's automatic `rollout.yml` dispatch (run `31469600804`) completed successfully end to end:

- `lehard/planner-agent-lab -> v1.4.22`: succeeded (job `93709828173`).
- `lehard/Jara_Fin -> v1.4.22`: succeeded (job `93709828206`).
- `lehard/cuby -> v1.4.22`: succeeded (job `93709828214`) -- `Detect already-pending rollout PR` correctly used the new structured `find-pending` subcommand with no `gh` flag error; `Prepare exact-version Copier update` (owned by `allow-safe-reclaimed-rollout-recopy`) succeeded automatically; `Supersede older validated rollout PRs` correctly resolved `platform/scripts/rollout_supersession.py reconcile`; a reviewable PR was opened at `lehard/cuby#46`, which passed downstream `platform-ci` and was merged through the normal protected workflow.

No run showed `unknown flag: --arg`, no missing-helper-path failure, and no failure-streak label crash. This is the exact acceptance evidence task 9 requires; it was not available from unit tests alone, only from a real dispatched rollout against real managed repositories.

## Semantic review

Completeness: PASS. All three defects named in the proposal (broken pending-PR detection, wrong `platform/` path for two call sites, non-idempotent failure-streak label bootstrap) have corresponding code fixes and passing regression tests, and the live rollout run demonstrates none of the three recur.

Correctness: PASS. `find_exact_pending_rollout_pr` reuses the same `list_open_prs`/`eligible_rollout_prs` trust boundary already relied upon by supersession (verified by `FindExactPendingRolloutPrTests` covering found/absent/wrong-bot/wrong-base/wrong-branch cases). `ensure_label` uses `gh label create --force`, verified idempotent by `test_ensure_label_is_safe_to_call_repeatedly`, and a simulated bootstrap failure (`test_missing_label_failure_does_not_crash_tracking_or_change_outcome`) still returns `0` without raising, matching the pre-existing best-effort tracking-layer contract.

Coherence: PASS. Code, design, and delta spec agree: the delta's "Rollout fails closed on project ambiguity or conflicts" and "Repeated managed rollout failures..." MODIFIED requirements, plus the new "Platform-owned rollout helpers are invoked from their actual checkout path" requirement, are all satisfied by the corresponding implementation and exercised by `tests/test_rollout_control_plane_regressions.py`.

## Scope note

This change intentionally did not reopen or edit the already-archived `supersede-stale-managed-rollouts` change, which originally introduced these regressions; it repairs the shipped code and workflow files directly under its own new OpenSpec change, per explicit operator instruction.
