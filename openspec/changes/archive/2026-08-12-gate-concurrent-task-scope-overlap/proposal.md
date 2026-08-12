# Proposal: Gate concurrent task scope overlap

Source backlog issue: lehard/development-backlog#25

## Why

The multi-agent lifecycle can detect overlapping work, but advisory diagnostics alone do not prevent two agents from beginning implementation against the same concrete repository path. A real execution observed this correctly at the agent level; the platform should make the same safety decision deterministic and race-safe.

This change depends on `lehard/development-backlog#23` (`harden-worktree-context-coordination`). It extends that single coordination mechanism after #23 is complete and merged to `main`; it does not introduce a parallel scope-normalization or board system.

## What Changes

- Add a platform-owned admission decision for `workflow_profile=multi-agent`: `RUN` when no hard overlap exists, `WAIT` when another active task owns the same concrete file scope.
- Reuse the normalized declared/factual scope information established by #23 and distinguish exact file conflicts from broad potential overlap.
- Make concrete-path claim acquisition atomic relative to the existing machine-local coordination state.
- Preserve a managed task's existing worktree and canonical OpenSpec when admission returns `WAIT`, reconcile its Project status to `Blocked`, and re-check admission on the next explicit resume.
- Keep `standard` and `light` profiles free from mandatory multi-agent admission semantics.

## Impact

- Affected specifications: `worktree-coordination`, `platform-lifecycle`.
- Affected platform surfaces: multi-agent start/resume admission, machine-local coordination state, managed Project status reconciliation, diagnostics and lifecycle tests.
- Existing managed-task package import/materialization and OpenSpec provenance remain canonical and resumable.
