# Tasks

## 1. Define the bounded stage graph and receipt
- [x] Define the fixed pre-authoring stages and their content-bound preconditions/outputs.
- [x] Add a minimal machine-local ignored run receipt with requirement/snapshot/ADD/intent/handoff identities.
- [x] Implement dependency-aware stale/invalidation calculation without a general workflow engine.

## 2. Compose existing stage owners
- [x] Call/reuse #127 snapshot preflight/build surfaces.
- [x] Call/reuse #128 ADD approval, intent decomposition/gates and OpenSpec handoff surfaces.
- [x] Keep normal managed OpenSpec lifecycle outside the pre-authoring receipt.

## 3. Add stage routing and human mediation
- [x] Use deterministic operations first and routine/read-only workers for snapshot extraction.
- [x] Use R2/standard ADD and decomposition by default and existing R3 escalation triggers.
- [x] Add structured worker decision requests and main-agent human mediation.
- [x] Prevent worker self-approval of consequential choices.

## 4. Implement resume/failure behavior
- [x] Resume from fresh completed stages after process/session restart.
- [x] Invalidate only dependent downstream stages after upstream mutation.
- [x] Preserve fresh artifacts on stage failure and bound retries/escalation.
- [x] Fail closed on ambiguous/missing stage identity.

## 5. Verify
- [x] Add e2e clean-run test/eval.
- [x] Add human pause/resume and process-restart cases.
- [x] Add partial invalidation and stage-failure retry cases.
- [x] Add routing escalation and no-second-lifecycle negatives.
- [x] Verify source/template parity and semantic OpenSpec completion.
