## 1. advance and finish
- [x] 1.1 `execute_requirement.py`: coordinator mode never requires the Requirement checkpoint or closes the parent; `await-post-merge`; merged composition reports instead of failing.
- [x] 1.2 `finish_task.py`, `requirement_integration.py`, `requirement_merge_recovery.py`: no parent close in coordinator mode.

## 2. Composition pre-merge retrospective removal
- [x] 2.1 `requirement_composition.py`, `post_review_finalization.py`, `lifecycle_workers.py`, `candidate_lifecycle.py`, `pr_review_gate.py`: remove the job, attempts, dispatch, resume and the readiness gate; stored pre-merge job fails derivation naming the PR.

## 3. Docs and tests
- [x] 3.1 Docs: task-intake, agent-workflow, chat-coordinator, hosted-lifecycle-workers; platform manifest.
- [x] 3.2 Tests: advance await-post-merge (single, legacy multi, composition), portable mode unchanged, no pre-merge job after finalize, readiness without the gate, stored pre-merge job fails, finish leaves parent open.

## 4. Verification
- [x] 4.1 Full validation and semantic OpenSpec verification.
