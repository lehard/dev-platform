# Tasks

- [x] 1. Add `find_exact_pending_rollout_pr` to `scripts/rollout_supersession.py`, reusing `list_open_prs`/`eligible_rollout_prs`; add a `find-pending` CLI subcommand producing structured JSON (`found`/`url`/`number`/`branch`).
- [x] 2. Restructure `rollout_supersession.py`'s CLI into `reconcile`/`find-pending` subcommands, preserving `reconcile`'s existing flags/behavior exactly.
- [x] 3. Fix `.github/workflows/rollout.yml`: replace the broken `gh pr list --jq --arg ...` step with a call to `platform/scripts/rollout_supersession.py find-pending`; fix the two existing supersession call sites to `platform/scripts/rollout_supersession.py reconcile ...`.
- [x] 4. Fix `.github/workflows/reconcile-stale-rollouts.yml`'s call site to `scripts/rollout_supersession.py reconcile ...` (bare path stays correct for its single-checkout layout).
- [x] 5. Add `ensure_label` to `scripts/rollout_failure_streak.py`, called for both `TRACKING_LABEL` and `ALERT_LABEL` before either is first referenced in `cmd_record_failure`; keep the whole bootstrap inside the existing best-effort `try/except`.
- [x] 6. Add regression tests: `find_exact_pending_rollout_pr` (found/absent/wrong bot/base/branch), workflow-text checks (no `--jq`+`--arg` gh pattern anywhere; every `rollout:` job script reference is `platform/`-prefixed; `plan:` job's bare reference stays valid), label-bootstrap idempotency and missing-label-does-not-crash-tracking tests.
- [x] 7. Run the full local validation contract (compileall, managed_projects validate, unit tests, openspec lifecycle check, strict OpenSpec validate); this change touches no `template/` files so no render/upgrade-smoke is required.
- [ ] 8. Publish implementation through a normal protected-main PR.
- [ ] 9. After merge, cut the next normal cumulative immutable patch release (do not retag/reuse v1.4.21) and confirm the resulting automatic managed rollout reaches a normal per-project result (opened/reused/up-to-date PR) for every `managed` repository, with no unsupported-`gh`-flag failure, no missing-helper-path failure, and no failure-streak label crash. If a new, unrelated platform-owned blocker appears, stop and diagnose before deciding whether it belongs to this change.
- [ ] 10. Record `OpenSpec-Verify: PASS` with the real method in `verification.md`, archive via `python3 template/scripts/openspec_lifecycle.py archive repair-managed-rollout-control-plane`, then publish the archive/spec result through protected main.

## Logical commit boundaries

1. Structured pending-PR helper + CLI reshape + workflow path fixes + label bootstrap + tests (one implementation commit; these changes are interdependent and small enough not to warrant separate commits).
2. Verification/archive commit, after live rollout evidence exists.
