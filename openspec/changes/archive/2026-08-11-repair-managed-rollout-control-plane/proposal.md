# Change: Repair managed rollout control-plane regressions

## Why

The real `v1.4.21` managed rollout (dispatched automatically after `wire-runtime-delegation-containment` merged) failed identically for every `managed` project -- `cuby`, `Jara_Fin`, and `planner-agent-lab` -- before any repository-specific Copier logic ran. Reading the actual failing CI run and the current `.github/workflows/rollout.yml`/`scripts/*.py` state (not the passing unit-test suite) surfaced three distinct, previously untested regressions in the rollout control plane itself:

1. **Broken pending-PR detection.** The "Detect already-pending rollout PR" step runs `gh pr list ... --jq --arg branch "$branch" --arg base "$BASE_BRANCH" --arg bot "..." '...'`. `--arg` is a `jq` flag, not a `gh pr list` flag; `gh`'s own argument parser rejects it with `unknown flag: --arg` before the `--jq` expression ever runs. This is a hard failure on every single managed repository, every time.
2. **Wrong tool path for the actual job layout.** The `rollout` job checks out platform tooling into `platform/` and the downstream project into `target/` -- there is no plain root checkout in that job. Three call sites correctly invoke `platform/scripts/rollout_project.py`, `platform/scripts/rollout_diagnostic.py`, and `platform/scripts/rollout_failure_streak.py`. Two call sites (`Supersede older validated rollout PRs`, `Reconcile rollout PRs already adopted by downstream base`) instead invoke the bare `scripts/rollout_supersession.py`, which does not exist at that path in this job and would fail with "no such file" the moment step 1's failure is fixed.
3. **Non-idempotent failure-streak label bootstrap.** `rollout_failure_streak.py` assumes the `rollout-failure-streak` and `rollout-alert` GitHub labels already exist on the tracker repository. On the real run this was false (`could not add label: 'rollout-failure-streak' not found`), so even the best-effort failure-tracking layer degraded to a warning instead of recording anything.
4. **The test gap that let all three ship.** The existing unit-test suite exercises the Python *semantics* of `rollout_supersession.py`, `rollout_failure_streak.py`, and friends thoroughly, but nothing exercised the actual *shell/CLI orchestration* -- the exact `gh` arguments passed, or the actual multi-checkout path layout of the `rollout` job. Green unit tests and a green `Platform CI` run coexisted with a rollout job that could never have succeeded end-to-end.

None of these three defects are owned by `allow-safe-reclaimed-rollout-recopy` (which owns the downstream Copier-recopy recovery step, several steps later in the same job and never reached) or by `wire-runtime-delegation-containment` (unrelated subsystem). They were introduced by `supersede-stale-managed-rollouts`, which is already archived. This change repairs the regressions without reopening that archived change.

## What changes

- Replace the fragile inline `gh pr list --jq --arg ...` shell with a call to a new, testable, platform-owned helper (`find_exact_pending_rollout_pr` in `scripts/rollout_supersession.py`, exposed as a `find-pending` CLI subcommand) that reuses the already-existing, already-tested structured trust-boundary logic (`list_open_prs`, `eligible_rollout_prs`) instead of parsing human-readable `gh` output or matching on PR title text.
- Restructure `scripts/rollout_supersession.py`'s CLI into explicit subcommands (`reconcile`, `find-pending`) sharing the same structured helpers, and fix every call site across `.github/workflows/rollout.yml` (both inside the multi-checkout `rollout` job, using the correct `platform/scripts/...` path) and `.github/workflows/reconcile-stale-rollouts.yml` (single-checkout maintenance workflow, correct bare `scripts/...` path) to use the new subcommand form.
- Add an idempotent `ensure_label` bootstrap to `scripts/rollout_failure_streak.py` that guarantees the `rollout-failure-streak` and `rollout-alert` labels exist on the tracker repository before they are referenced, using the least-privilege `issues: write` permission the rollout job already has. Bootstrap failure still degrades to a warning and never changes rollout's own pass/fail outcome, matching the existing best-effort contract for this tracking layer.
- Add regression coverage that would have caught all three defects before release: unit tests for the new structured pending-PR lookup (found, absent, wrong bot/base/branch not recognized as trusted), a static regression test asserting the fragile `gh ... --jq --arg` pattern is gone and every platform-owned script invocation inside the multi-checkout `rollout` job actually resolves under `platform/`, and label-bootstrap idempotency/missing-label tests for the tracking layer.
- No workflow-engine rewrite: the fix stays inside the existing job/step structure, moving control logic that was previously inline shell into already-established, testable Python helpers where that reduces the chance of this class of bug recurring.

## Scope

This affects only the central rollout control plane: `.github/workflows/rollout.yml`, `.github/workflows/reconcile-stale-rollouts.yml`, `scripts/rollout_supersession.py`, and `scripts/rollout_failure_streak.py`. It does not touch downstream project code, `openspec/changes/archive/2026-08-11-supersede-stale-managed-rollouts` (already archived; not reopened), `durable-publication-recovery` (separate parallel initiative; not touched), or any candidate/excluded repository. No downstream repository is manually reconciled as part of this change.

## Compatibility risks

- Changing `rollout_supersession.py`'s CLI from flat flags to subcommands is a breaking change for any caller of that exact CLI shape; the two workflow files that call it are updated in the same change so no caller is left broken.
- The new pending-PR helper must apply the exact same trust-boundary rules (`eligible_rollout_prs`) already relied upon by supersession, so a PR is never treated as "pending" merely by branch-name/title resemblance.
- Label bootstrap must remain genuinely best-effort: if `ensure_label` itself fails (permissions, API outage), tracking must still degrade to a warning rather than failing the rollout attempt, exactly as the existing tracking-layer contract already requires.

## Success criteria

A subsequent real managed rollout for the next published immutable release reaches a normal per-project rollout result (opened PR, reused pending PR, or already-up-to-date) for every `managed` repository, with no `unsupported gh flag` failure, no `missing platform helper path` failure, and no failure-streak tracking crash from missing labels. This change is not archived on unit tests alone; it requires that live rollout evidence.
