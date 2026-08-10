# Verification: harden rollout diagnostics

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review (no `/opsx:verify` tool integration in this environment) plus full local platform test/validation run

## Completeness

- All tasks in `tasks.md` are complete except release/rollout, which are explicitly deferred pending operator go-ahead.
- The delta adds only the machine-readable diagnostic envelope layer; it does not touch `allow-safe-reclaimed-rollout-recopy`'s recopy/recovery contract, and this change's files are the only ones under `openspec/changes/harden-rollout-diagnostics/`.
- Checked for overlap with the two other currently active changes: `harden-ci-safety-model` (already archived; its scope was CI safety invariants, not rollout diagnostics) and `durable-publication-recovery` (in-progress locally; its scope is task-publication/PR-merge lifecycle, unrelated to rollout diagnostics). Neither duplicates this change's requirement; nothing was left unmerged as a result.

## Correctness

- `scripts/rollout_diagnostic.py` builds the envelope purely from already-known structured rollout state (the existing `Managed rollout: BLOCKED:` and `DEV_PLATFORM_CHECK_COMMAND:` markers), never from arbitrary log scraping, matching the spec's `Selected downstream check fails` scenario (verified by `test_selected_check_failure_uses_reserved_marker_only`, which proves adjacent compiler noise never leaks into `reason`/`command`).
- `retry_same_inputs` defaults to `pointless` for safety-guard/copier-conflict/runtime-environment categories and `unknown` for downstream-check/unclassified categories, matching the spec's requirement that a same-input retry is never labeled `safe` when nothing about the input can change.
- Secrets/raw log text are excluded by construction: the envelope only carries the parsed `reason`/`command`/`conflict_paths` fields, never the raw log (verified by `test_envelope_excludes_raw_log_text_and_secrets`).
- The CLI never raises a non-zero exit even on a missing/unreadable log file (`test_cli_never_fails_even_with_unreadable_log`), and the workflow invokes it with `|| true` before `exit "$rc"`, so diagnostic generation/upload can never mask, soften, or replace the original rollout failure or its exit code.
- The artifact-upload step is `if: ... && failure()` with `continue-on-error: true` and `if-no-files-found: ignore`, so a missing/failed upload cannot itself change job status, push a branch, or open a PR.

## Coherence

- No safety guard, branch-protection rule, or recopy/recovery eligibility rule was modified.
- No auto-retry, auto-merge, or auto-push was introduced; `retry_same_inputs` is documented and implemented as advisory-only.
- `openspec/changes/allow-safe-reclaimed-rollout-recopy/` was restored to its pre-existing `main` content (the stray diagnostics-contract edits that had been added to that path in draft PR #75 were moved into this new change instead); that change's own remaining tasks (bookkeeping, release, Cuby rollout) are untouched and not implemented by this change.

## Acceptance evidence

Run locally on branch `agent/rollout-diagnostics-contract`:

- `python3 -m compileall -q template/scripts scripts` — OK
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded)
- `python3 -m unittest discover -s tests -v` — 148 tests, OK (includes 7 new envelope-construction tests, 2 new CLI tests, 3 new workflow-integration tests, plus the existing `test_rollout_diagnostics.py` suite adjusted only to scope its `continue-on-error` prohibition to the `Prepare exact-version Copier update` step, which still forbids it there)
- `python3 template/scripts/openspec_lifecycle.py check` — OK
- `openspec validate harden-rollout-diagnostics --strict` — valid
- `openspec validate allow-safe-reclaimed-rollout-recopy --strict` — valid (unaffected)

No release was cut and no rollout was executed against Cuby or any other managed project; both remain deferred per explicit instruction pending review of this implementation.
