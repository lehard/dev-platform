OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the full implementation diff against the model-routing delta, proposal, design and tasks; independent review (spec-fidelity, engineering-quality) on the final content; repository-owned selected checks on the reconciled head
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

Implementation: a delegated native Claude executor (standard profile) implemented the change; its execution was recorded with a clean containment postcheck. After independent review the supervisor made one bounded repair (archive gate equality check for the approval, design decision 3 wording, one test).

Completeness: tasks 1.1, 1.2, 2.1 and 2.2 are implemented. Scenarios map to tests/test_model_routing.py: the owner-approved diff becomes a supervisor-retained plan with policy owner-approved and the recorded approval, the early gate passes, record-retained-execution carries the approval and the archive gate passes; refusals for empty approval, empty reason, already retained plan, real delegation, existing execution and unchanged content each leave the record unchanged; a plan claiming the policy without a complete approval, an approval on another policy, and a retained execution whose approval is missing or differs from the plan all fail; routing reports expose owner_approved; the CLI prints the approved route.

Correctness: the command never writes a delegation, launch claim or escalation and leaves the profile unchanged; it calls the existing recovery-safety postcheck before writing. Policy resolution reads only the validated plan. The modified requirement keeps every existing scenario and names the owner-approved retention as the only exception.

Coherence: docs/engineering/model-routing.md and its template copy describe the command, its preconditions, that it requires an explicit owner decision given in chat, and what it records.

Independent review: the first round reported (1) the archive gate did not require the approval in the retained execution — fixed and covered by a test; (2) the approval statement cannot be verified mechanically, so any agent can record one — accepted residual risk stated in design Risks and the owner's request; the record is explicit and visible in reports. The final round on the repaired content reported no findings.

Checks actually run: supervisor ran `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/owner-approved-supervisor-diff/automated-checks.json` on the final head 8adaa1b (task content reconciled with origin/main e5b3f9d): compileall, ruff and `run_test_groups.py --all` (584 s) all success; affected precheck success (169 s). An earlier run on f23bfae also passed (633 s).
