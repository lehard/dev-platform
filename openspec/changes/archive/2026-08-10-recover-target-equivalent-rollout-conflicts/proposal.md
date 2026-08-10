# Proposal: Recover target-equivalent Copier rollout conflicts

## Why

The v1.4.13 rollout exposed a recovery gap in `harness_mode=platform`: Cuby had already received the exact upstream `scripts/project_publish.py` bytes while repairing the protected-main worktree bug, but Copier still replayed the historical downstream diff and produced `scripts/project_publish.py.rej`. Managed rollout correctly failed closed, yet it had no safe way to recognize that the conflicted platform-owned file was already identical to the requested immutable release.

This means a consumer can be functionally on the fixed platform file but remain unable to return to normal Copier-managed versioning without another hand reconciliation.

## Goal

Allow managed rollout to recover automatically when every conflict in a platform-owned harness is provably target-equivalent before the smart Copier update starts, while continuing to fail closed on any real downstream divergence.

## Scope

- Add a narrow target-equivalent recovery path for platform-owned rollout conflicts.
- Permit guarded recopy in `harness_mode=platform` only when every rejected target was already byte-identical to the exact requested template before the failed smart update.
- Keep project-owned harness recovery rules unchanged.
- Preserve project configuration invariants and run normal bootstrap/doctor/selected checks after recovery.
- Add regression coverage reproducing the Cuby v1.4.13 conflict pattern.

## Non-goals

- Ignore or auto-resolve arbitrary Copier conflicts.
- Treat modified platform-owned files as safe merely because they are known paths.
- Weaken downstream PR review or required CI gates.
