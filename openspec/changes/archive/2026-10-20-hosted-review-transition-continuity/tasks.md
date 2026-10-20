## 1. Attribution by public work identity
- [x] 1.1 Add `managed_work_identity.branch_attribution(branch)` (managed child, composition, unmanaged, malformed).
- [x] 1.2 Make `default_friction_sink` and the durable evidence record use only that attribution (`work_identity`, `child_identity`); no Backlog or authoring-config access.
- [x] 1.3 Match durable records in `requirement_evidence` by work identity, keeping legacy `requirement` matches.

## 2. Review job ordering and own-push convergence
- [x] 2.1 Preflight friction attribution in `run_claimed` before the reviewing/repairing transition and before the reviewer starts.
- [x] 2.2 Add bounded own-push convergence and use it in review, repair and finalize result paths; foreign head or claim change still discards.

## 3. Content-bound gate continuity and recovery
- [x] 3.1 Keep content-bound gates in validated-push recovery and in the claim transition after a trusted harness push with unchanged digest.
- [x] 3.2 Add `publication_queue.py restore-gates --pr N` proving the trusted push chain; refuse with the failing hop otherwise.
- [x] 3.3 Document attribution, preflight and `restore-gates` (hosted-lifecycle-workers.md, chat-coordinator.md, agent-workflow.md finalize-pending path).

## 4. Verification
- [x] 4.1 Regression tests reproducing 2026-10-19: hosted contract without `[development_backlog]`, review with material findings (one run, `repair-pending` + trusted evidence record, no extra rounds or commits) and without findings (`finalize-pending` with admission gates; finalize does not stop at semantic verification).
- [x] 4.2 Tests: unattributable candidate fails before push; API lag does not discard; foreign head/claim still discards; restore-gates success and refusal; no private Backlog identity in the public tree.
- [x] 4.3 Run full validation and semantic OpenSpec verification.
