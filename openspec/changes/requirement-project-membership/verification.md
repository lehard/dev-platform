OpenSpec-Verify: PASS
Verification-Method: equivalent semantic review of proposal, delta, design, implementation and regression evidence
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Semantic review

Completeness: both added managed-task-intake requirements are implemented. `managed_project_status.ensure_item` adds a missing Project item idempotently, initializes only an unset Status to `Backlog`, and accepts the result only after an exactly-one read-back. `requirement_intake.create` confirms membership before reporting success, reuses an identical open Requirement on rerun and fails closed naming the durable Issue; `reconcile-board` repairs one or all open Requirements; `requirement_board.claim_started` ensures membership before claiming the card. The connected rule is documented in task-intake and the ChatGPT protocol and pinned by the `connected_fixation_outcome` reference model.

Correctness: fake-GraphQL tests cover auto-add already done (unset Status), auto-add absent, item lagging in the Project list, existing item and Status preserved, repeated reconciliation without a duplicate, duplicate items refused without mutation, unavailable Project API at read and at add, missing authentication, repository-local create success, fail-closed create and rerun reuse, and the connected outcome.

Coherence: proposal, design, delta, runtime and docs agree. No new service or Project migration; GitHub built-in auto-add stays a fast path.

## Evidence and limits

- Live read-back on 2026-10-07 before the change: lehard/development-backlog #415, #416, #433 and #436 each already had exactly one Project item created 2-3 seconds after the Issue. The reported missing auto-add was not reproducible, so the root cause of the original observation is unconfirmed; the delivered defect fix is that membership was never confirmed or repaired by the platform.
- Live `reconcile-board --all` after the change: all 30 open Requirements, including #416, #433 and #436, have exactly one item; nothing needed adding. #416 shows Status Done while open (a side effect of the earlier close/reopen retrigger); it was not changed because the platform does not rewrite lifecycle statuses.
- The connected ChatGPT adapter cannot be executed from this repository; its behavior is a documented contract plus a reference-model test, and the unattended completion depends on the operator invoking `reconcile-board`, which is not scheduled by this change.
- Selected checks: compileall, ruff and the complete canonical suite (17 groups) passed; see automated-checks.json.
