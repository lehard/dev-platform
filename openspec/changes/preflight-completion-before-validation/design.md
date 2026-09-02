# Design: Reorder existing gates

## Decisions

1. Pre-validation inspection reuses current cleanliness, OpenSpec, provenance, terminal state, freshness, scope, checkpoint and integration checks.
2. Independent read-only failures are collected into one bounded report; unsafe dependent checks may still stop.
3. Full validation begins only after the current preflight is clear.
4. The synchronous command prints stage transitions and existing test-group results; it does not create a job service.
5. A state change after validation remains protected by the current immediately-before-publication rechecks.
6. The consolidated preflight sits after the `task_pr_is_already_merged` recovery early-return, so the pure local-reconciliation path for an already-merged exact PR no longer runs OpenSpec hygiene or the friction checkpoint. That path starts no expensive validation and blocking it would strand a delivery GitHub has already merged (see the existing "Remote PR merged but local reconciliation remains" requirement); the best-effort friction route-pending retry still runs there.
