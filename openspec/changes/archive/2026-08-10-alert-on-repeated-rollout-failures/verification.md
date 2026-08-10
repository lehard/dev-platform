# Verification: alert on repeated managed rollout failures

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review (no `/opsx:verify` tool integration in this environment) plus full local platform test/validation run

## Completeness

- All tasks in `tasks.md` are complete except release/rollout, which is out of scope for this change (it only adds detection/alerting, not a new release).
- Checked for overlap with the only other currently active change, `allow-safe-reclaimed-rollout-recopy`: that change owns guarded-recopy conflict recovery/eligibility (why a rollout attempt blocks); this change only observes the already-existing terminal outcome across runs and never touches recopy/recovery logic, `.rej` handling, or baseline-equivalence rules. No files under `openspec/changes/allow-safe-reclaimed-rollout-recopy/` were touched. No duplicate backlog was created for its remaining tasks (release, verify Cuby, archive) — those stay with that change.
- Checked for overlap with the already-archived `harden-rollout-diagnostics`: that change owns the per-attempt `rollout-diagnostic.json` envelope and its `stage`/`category`/`reason` classification. This change only *reads* the already-produced `category`/`reason` fields from that envelope to feed the cross-run streak; it does not change the envelope schema, its classification rules, or its per-attempt artifact/summary/annotation behavior.

## Correctness

- `scripts/rollout_failure_streak.py`'s `next_state_on_failure` increments `consecutive_failures` only when the parsed prior state's `repository` field exactly matches the current project, preventing cross-project state leakage even if GitHub's own issue search were to fuzzy-match a similarly named repository (`test_different_repository_marker_does_not_leak_into_state`).
- The alert threshold (3) is crossed exactly at the third consecutive failure and not before (`test_third_consecutive_failure_crosses_default_threshold` asserts no alert at failures 1–2 and an alert at failure 3).
- An unreadable prior state (body present but the embedded `<!-- rollout-failure-streak-state ... -->` block missing, malformed, or an unrecognized `schema_version`) escalates the streak to at least the threshold rather than resetting it to 1, so a corrupted or tampered record cannot hide an ongoing streak (`test_unreadable_prior_state_escalates_instead_of_resetting`, `test_parse_state_returns_none_for_malformed_json`, `test_parse_state_rejects_unknown_schema_version`).
- `render_body`/`parse_state` round-trip exactly (`test_parse_state_round_trips_through_render_body`), so the state block is not lossy across issue edits.
- A resolved project's streak starts over at `consecutive_failures = 1` on its next failure because the tracking issue is closed (not left open with stale state) on success, matching the spec's "fresh record starting at 1" scenario; `cmd_record_success` is a no-op when no open tracking issue exists, matching the "no prior open record" scenario.
- Both CLI entry points (`cmd_record_failure`, `cmd_record_success`) wrap all logic in `except Exception` and always return `0`, so a `gh` CLI failure, network error, or unexpected API shape can never propagate a non-zero exit into the workflow step (verified structurally by `test_script_entry_points_never_raise_on_generic_failure`; the same posture as the already-shipped `rollout_diagnostic.py`).

## Coherence

- `.github/workflows/rollout.yml`: the two new steps (`Record rollout failure streak`, `Record rollout recovery`) are both `continue-on-error: true`, both scoped under the existing `steps.pending.outputs.found != 'true'` guard used by every other per-attempt step, and neither appears inside the `git -C target push` / `gh pr create` steps' own condition (`test_failure_streak_steps_cannot_influence_push_or_pr_conditions`). Their own conditions (`&& failure()` and `&& steps.prepare.outcome == 'success'`) are read-only signals derived from the already-fixed `prepare` step outcome — they cannot themselves cause `prepare` to fail or succeed.
- Both new steps use `${{ github.token }}` (the workflow's own same-repository token) rather than the cross-repository `source-token`/`target-token` App tokens, matching `AGENTS.md`'s reservation of the dedicated App for cross-repository (target-project) writes only; `issues: write` was added to top-level `permissions:` for exactly this same-repository use (`test_failure_streak_uses_default_token_not_cross_repo_app`, `test_workflow_grants_issues_write_for_same_repo_tracking`).
- No safety guard, recovery/recopy eligibility, credential scope, retry behavior, or auto-merge behavior was introduced or modified. The tracker only reads already-terminal rollout state and writes to its own tracking issue.
- `docs/managed-rollout.md` documents the mechanism, threshold, and token model consistently with the implementation.

## Acceptance evidence

Run locally on branch `claude/modest-brattain-04f7ca`:

- `python3 -m compileall -q template/scripts scripts` — OK
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded)
- `python3 -m unittest discover -s tests -v` — 168 tests, OK (includes 9 new streak-state tests, 5 new script-content/workflow-wiring tests, plus all pre-existing rollout/diagnostic/template suites unchanged)
- `python3 template/scripts/openspec_lifecycle.py check` — OK
- `openspec validate alert-on-repeated-rollout-failures --strict` — valid
- `openspec validate allow-safe-reclaimed-rollout-recopy --strict` — valid (unaffected)

No release was cut and no rollout was executed against any managed project; this change adds a detection/alerting layer only and does not by itself require a rollout to take effect on `dev-platform`'s own automation, though it will reach downstream projects only through the normal reviewed Copier rollout PR path once released.
