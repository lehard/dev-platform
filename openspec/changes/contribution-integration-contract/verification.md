# Verification: contribution-integration-contract

OpenSpec-Verify: PASS
Verification-Method: documented equivalent semantic review of proposal, design, tasks and delta specs against the implementation, scenario by scenario, with canonical regression tests. No opsx tool invocation is claimed.
Automated-Checks-Evidence: automated-checks.json

## Semantic assessment

- Conflict before checks: `merge_reviewed_contribution` evaluates content gates, then the conflict with the target head, then required checks immediately before the merge. A conflict moves the candidate to integration repair within its budget; a spent budget returns the block. A conflict-free head without checks raises `RequiredChecksWait` naming the head; the worker posts it as a wait, spends no claim release, and the queue integrates the head once checks pass.
- absorb-main: merges main in a disposable checkout and pushes by fast-forward from the observed head. Refuses a queue-owned composition, a missing branch, a moved head and a conflict, naming the next action. The manifest does not change.
- Base transitions: an integration repair rebinds the identity to the merged target head, in the validated-push receipt too. Equivalent content or a proven target-only merge keeps content gates without required checks and publishes the integration job; other changes return to review on the new base. `reusable` accepts a moved base only through `equivalent_proofs`. Re-admission accepts a base that descends from the recorded one inside the target and otherwise refuses naming both bases and reconcile, before any write.
- Checks: contribution checks use `--base` and `--contribution-base` set to the contribution base, and finalization refuses a base its target does not contain. Main-target candidates keep `--base origin/main` and the proven-base rule.
- Freshness: `task_freshness_branch` resolves the recorded target or main for status, finish, reconcile, handoff, preflight and selected checks. Reconcile merges that branch and moves the contribution base. The merge hook admits the intent's ref, limited to main or a requirement branch.
- Composition keeps verifying the recorded base, identity, head and integrated head; a moved base recomputes and a changed identity refuses naming the child.

## Changes beyond the task list

- `advance_after_repair` publishes the contribution-integration job with its target head. Without it `build_job` offered a job with no target head, which `work-next` could not run.
- The queue keeps its label on `integration-repair-pending`, so the repaired head stays reachable.
- A recovered validated-push of a contribution derives `contribution-integration-pending`, not `ready`, which the contribution path never leaves.
- `push_feature_branch` now applies the first-publication freshness rule to contribution handoffs, against their target.

## Evidence

- Selected checks passed on committed head 6298179de9e1bddaa10ab81d8f66a08178591832; record in `automated-checks.json`.
- `openspec validate --all --strict`: 52 passed, 0 failed. `openspec_lifecycle.py check`: OK. Ruff and manifest check passed.
- New tests cover the BR-978 T1 sequence, spent budget, the required-checks wait, every absorb-main refusal, moved-base composition, gate reuse across a move, repair rebinding, recovery state, base-move refusals, base outside the target, target freshness, reconcile moving the base, and the main-target rule.

## Not verified

- No direct test covers the one-line `select_checks.py` target selection, the `RequiredChecksWait` catch in `work-next`, or the `finish_task.py` target ref; they rest on the tested helpers.
- The installed `pre-merge-commit` hook of an existing checkout updates through `agent_doctor.py`. An older hook refuses a contribution reconcile explicitly; a main reconcile is unaffected.
- The live GitHub path is exercised only by this delivery itself.
