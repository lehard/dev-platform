## 1. Integration
- [x] 1.1 `requirement_contributions.py`: content gates, conflict, then required checks; explicit next action in refusals.
- [x] 1.2 `execute_requirement.py absorb-main` with queue-owned and conflict refusals.

## 2. Provenance
- [x] 2.1 Contribution base transitions in `integration_contour.py`, `pr_review_gate.py`, `publication_queue.py`, `requirement_child_context.py`.
- [x] 2.2 `post_review_finalization.py` and `select_checks.py`: contribution checks scoped to the contribution base.

## 3. Freshness
- [x] 3.1 `task_reconciliation.py`, `project_publish.py`, `select_checks.py`, `dogfood_task.py`: freshness and reconcile against the contribution target.

## 4. Tests and docs
- [x] 4.1 Tests: BR-978 T1 sequence; absorb-main refusals; review, finalization and composition identity after main is absorbed; base transition refusals; main-target rule unchanged.
- [x] 4.2 agent-workflow, openspec-workflow and chat-coordinator docs; manifest.

## 5. Verification
- [x] 5.1 Full validation, strict `openspec validate` and semantic OpenSpec verification.
