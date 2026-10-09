OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the full implementation diff against the model-routing delta, proposal, design and tasks; independent review (spec-fidelity, engineering-quality) on the final content; repository-owned selected checks on the reconciled head
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

Implementation: a delegated native Claude executor (standard profile) implemented the change; its execution was recorded with a clean containment postcheck. After independent review the supervisor made one bounded repair (archive gate equality check for the approval, design decision 3 wording, one test).

Completeness: tasks 1.1, 1.2, 2.1 and 2.2 are implemented. Scenarios map to tests/test_model_routing.py: the owner-approved diff becomes a supervisor-retained plan with policy owner-approved and the recorded approval, the early gate passes, record-retained-execution carries the approval and the archive gate passes; refusals for empty approval, empty reason, already retained plan, real delegation, existing execution and unchanged content each leave the record unchanged; a plan claiming the policy without a complete approval, an approval on another policy, and a retained execution whose approval is missing or differs from the plan all fail; routing reports expose owner_approved; the CLI prints the approved route.

Correctness: the command never writes a delegation, launch claim or escalation and leaves the profile unchanged; it calls the existing recovery-safety postcheck before writing. Policy resolution reads only the validated plan. The modified requirement keeps every existing scenario and names the owner-approved retention as the only exception.

Coherence: docs/engineering/model-routing.md and its template copy describe the command, its preconditions, that it requires an explicit owner decision given in chat, and what it records.

Independent review: the first round reported (1) the archive gate did not require the approval in the retained execution — fixed and covered by a test; (2) the approval statement cannot be verified mechanically, so any agent can record one — accepted residual risk stated in design Risks and the owner's request; the record is explicit and visible in reports. The final round on the repaired content reported no findings.

Coordinator review (Codex, spec-fidelity and engineering-quality) on the handed-off head reported one material finding: escalating an owner-approved plan rewrote its policy to complex-parent while keeping owner_approval, which wrote an invalid record. Repaired by the developer: escalate now refuses an owner-approved plan and writes nothing; a regression test covers it.

Advisory accepted after the repair round: the approval binds the diverged paths and time, not a content digest, so supervisor edits after approval stay under supervisor retention. This is intended: the owner approves supervisor retention for the rest of the task (verification and archive still follow), exactly as an up-front supervisor-retained plan permits later supervisor edits; containment postcheck still applies at finalization.

Second coordinator review round (Codex): material — an unlaunched Codex attempt left execution evidence and blocked owner approval; repaired by the developer (approval and retained finalization accept a closed not-launched attempt, prove integration containment and keep it as prior execution; regression test). Advisory — the template routing guide still said a delegated plan is never converted; aligned with the owner-approved exception.

Checks actually run: supervisor ran `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/owner-approved-supervisor-diff/automated-checks.json` on head 3cfe941 (up to date with origin/main): compileall, ruff and `run_test_groups.py --all` (281 s) all success; affected precheck success (75 s). Earlier heads also passed (331 s, 584 s, 633 s).
