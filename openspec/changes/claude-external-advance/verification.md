OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the full implementation diff at c7da00e against the model-routing delta, proposal, design (including the supervisor amendment to decision 4 made before implementation completed) and tasks; independent review (spec-fidelity, engineering-quality) on the same content; repository-owned selected checks on the committed head
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

Implementation: a delegated native Claude executor (standard profile) implemented the change; its execution was recorded with a clean containment postcheck (integration head unchanged during the delegation). No supervisor code edits.

Completeness: tasks 1.1, 2.1, 2.2, 3.1 and 3.2 are implemented. Scenarios map to `tests/test_integration_advance_receipts.py` (54 tests) and receipt assertions in `tests/test_git_lifecycle.py`: a sibling merge with an unbroken receipt chain is recorded as a verified concurrent advance with the raw head movement preserved; integration path change, non-fast-forward, head different from origin/main, missing receipt, broken or short chain, receipt older than the delegation window, receipt not landing on its recorded origin main, receipt from inside the delegated worktree and a malformed receipt log all stay violations; Codex outcomes unchanged; Claude historical recovery succeeds (including after several later un-receipted advances) and each refusal writes nothing.

Correctness: receipts are written by every integration-main fast-forward site (finish_task direct publish after the push succeeds, sync after remote PR merge including the normalize step, project_sync); sites that move task branches only are deliberately not instrumented. The classifier requires all common facts for both tiers and the receipt chain only for detection-only writers. Recovery stores its record on the open delegation without creating an execution.

Coherence: the stated trust boundary (design decision 5) is documented in docs/engineering/model-routing.md and its template copy.

Independent review (advisory findings, reported): (1) in direct publish a receipt-write failure after a successful push surfaces as an explicit error whose message does not say the push succeeded; (2) the Claude recovery window ends at recovery time rather than the friction event — this is the deliberate amendment to decision 4, justified because the friction event is written after the Agent call returned, and bounded by the path-unchanged and origin/main-equality requirements; (3) the receipt chain may begin at the first receipt whose before equals the start head, skipping earlier receipts for heads already accounted for; the covered movement remains bounded by the start head and current head.

Pre-existing fallback reported, not changed: verify_remote_fast_forward and verify_historical_external_advance default main_branch to "main"; the new receipt code raises when main_branch is absent.

Checks actually run: supervisor ran `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/claude-external-advance/automated-checks.json` on head c7da00e: compileall, ruff and `run_test_groups.py --all` (559 s) all success (see automated-checks.json).
