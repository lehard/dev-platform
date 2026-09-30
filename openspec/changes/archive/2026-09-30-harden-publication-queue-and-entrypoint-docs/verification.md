# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the proposal, design, publication-queue and agent-instructions deltas and the implementation against the Requirement acceptance evidence; strict OpenSpec validation (1.13.2); targeted unit tests; the archive helper's automated platform checks; and the platform-launched independent review of the committed candidate that archive runs.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Semantic review

- Trust boundary: the queue workflow's label trigger is `pull_request_target`, so workflow and worker code come from the default branch; no step checks out a PR head or merge ref, and the job filter on `publication:queued` is re-keyed to the new event name. Schedule and dispatch triggers are unchanged.
- Token scope: the App token step sets `owner`, a repository name derived from `GITHUB_REPOSITORY` (not `github.event.repository`, which a schedule payload may lack) and exactly `permission-contents: write` and `permission-pull-requests: write`. Checks, statuses and workflows permissions are not requested because the documented App grants only contents, pull requests and workflows, and the coordinator does not author workflow content. Whether the GitHub App accepts this reduced set for update-branch with workflow-file diffs could not be exercised locally; it is recorded as a residual risk in design.md.
- Queue semantics (admission, ordering, exact-head merge guard, required checks, no bypass or force) are untouched: `publication_queue.py` is unchanged.
- Entrypoint docs: `orchestrate_pre_authoring.py --id requirement-N status` now appears in AGENTS.md, template/AGENTS.md.jinja, agent-workflow.md, task-intake.md and their template counterparts. The parser was factored into `build_parser()` with identical behavior so a test parses every documented command line. CLI runtime hints that omit `--id` are a separate, unchanged observation.

## Observed checks

- `python3 -m unittest tests.test_publication_queue tests.test_orchestrate_pre_authoring` passed (38 tests); the new workflow tests fail against the previous workflow file, and the documented-command test rejects the subcommand-first form.
- Related modules (CI guardrails, template contract, agent-instruction architecture, requirement intake/execution/flow) passed (142 tests).
- `openspec validate harden-publication-queue-and-entrypoint-docs --strict`, `python3 -m compileall -q template/scripts scripts` and the private-reference guard passed.
- The final candidate's full automated checks and independent review are produced by the archive helper and recorded in the archived evidence.
