# Proposal: Add safe managed-task reconciliation

## Why

The existing freshness gate correctly stops stale task branches before authoritative expensive validation. In a fast-moving multi-agent repository, however, the recovery loop is still manual and can repeat several times. Rebasing an already-published branch also conflicts with the platform's no-force-push contract.

## What Changes

- Add a lifecycle-owned read/diagnose/reconcile path for task branches that fall behind authoritative main.
- Surface stale/behind status before another expensive validation run.
- Preserve published PR history with non-rewriting reconciliation so the same PR branch can be fast-forward pushed.
- Fail closed on dirty state, conflicts, changed remote head or provenance ambiguity.
- Reuse existing freshness, publication and exact-head state rather than inventing another synchronization model.

## Impact

- Modified specifications: `platform-lifecycle`, `publication-recovery`, and `central-dogfood-lifecycle`.
- Expected surfaces: `finish_task.py`/`dogfood_task.py` status and reconcile entrypoints, Git helpers, publication-state integration, regression tests and focused docs.
