OpenSpec-Verify: PASS
Verification-Method: equivalent semantic OpenSpec review of completeness, correctness and coherence against the accepted publication-queue, completion-lifecycle and lifecycle-workers specs plus this active delta
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

Implementation was delegated to a Claude Sonnet subagent (Codex subscription exhausted at start) in this worktree and reviewed by the supervisor; the supervisor made the final two fixes directly.

Integration contour. Path overlap no longer blocks: `_prepare` runs a deterministic merge pre-check; a clean merge updates the branch and runs checks on the merged head; a real conflict or a failing merged check becomes a bounded integration-repair job (two attempts) executed through the worker harness. A repair that leaves task content unchanged reuses review and finalization evidence and reruns required checks; changed content returns to review and finalization. Blocked, foreign-owned or repair-pending candidates no longer stop the queue.

Inherited obligations. Coordinator lifecycle events are recorded as friction attributed to the candidate task and its Requirement; Requirement retrospectives accept child-attributed events. Retrospective, terminal-reconciliation and local-cleanup jobs are derived from result receipts of coordinator-merged PRs (rerun-safe, bounded retries); cleanup refuses dirty, active, foreign-path or unmerged worktrees.

Independent review: round 1 ready with advisories; the supervisor restored best-effort board release for ordinary finish (required only for developer handoff). Round 2 found that post-LLM harness git ran in the writer-controlled checkout with operator credentials (material); fixed so writer/reviewer content is imported file-by-file into a harness-owned clone and every post-LLM git runs there with a credential-free environment, with sentinel tests proving planted `filter.clean`/`textconv` never execute. Round 3 found the import could write through directory symlinks (material); fixed by recreating symlinks without following them on either side, with a regression test. Round 4: ready.

Known limitations (advisory, accepted): real GitHub/Project/worktree adapters are exercised through fakes; post-merge obligations scan one bounded page of recently closed PRs; a failed Requirement lineage lookup leaves events unattributed; cleanup completes on a worker without the developer's worktree; `execute_review` has no dedicated sentinel test (the generic review job does).

Checks: compileall, ruff, `tests/test_autonomous_integration_contour.py` with affected queue, worker, gate and finalization tests, import-isolation, module-identity and shared-writer guards, `openspec_lifecycle.py check`, and the selected full validation (automated-checks.json). Completeness: tasks 1.1-3.2. Correctness and coherence: behavior matches the delta scenarios.
