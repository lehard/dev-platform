# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the proposal, design, completion-lifecycle and agent-workflow deltas and the implementation against the Requirement acceptance evidence; strict OpenSpec validation (1.13.2); targeted unit tests; the archive helper's automated platform checks; and the platform-launched independent review of the committed candidate that archive runs.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Semantic review

- Reviewer runtime readiness: `independent_review_runner.preflight` resolves provider, exact selected model and binary, then runs one bounded probe (default 120 s, `[independent_review] preflight_timeout_seconds`) through the same launcher and read-only adapter flags, under the same workspace mutation postcheck. A missing binary, unresolvable provider/model, non-zero exit (with the CLI's bounded error), error result, unreadable output, timeout or mutation yields a limitation naming provider, model and next step; no other model or provider is tried. `run_review` calls it before any perspective; a failed preflight records both perspectives as unavailable without launching them. `independent_review.py preflight [change]` exposes the check without writing evidence; missing-review guidance and `advance` implement-child guidance point at it.
- Reviewer context: the reviewer diff is built only from the changed paths that the review task-content identity binds (`task_content_identity.review_path_partition`, the same `review_exclusion`), as literal pathspecs; the request records `excluded_lifecycle_paths` (additive, schema version unchanged) and the prompt states that those lifecycle paths are not candidate content.
- Ready receipt supersession: `requirement_integration.write_receipt` replaces an existing receipt only when it is a valid receipt with identical Requirement, child Issue, change and source branch and its head is a strict ancestor of the new head in the child worktree; foreign identity, invalid/unreadable content, same head with different content, divergent/unresolvable head or missing repository still refuse. `execute_requirement.advance` reports `superseded_receipts` for audit.
- Guarantees kept: unavailable reviewer, task-owned content change and ambiguous provenance still fail closed; publication, verification, independent-review and terminal-reconciliation gates are unchanged.

## Observed checks

- `python3 -m unittest tests.test_independent_review` passed (45 tests), including the representative happy path: one probe and one launch per perspective, then evidence commits, archive move, spec materialization and refreshed automated checks pass `ensure_review_evidence`, `require_review_evidence` and the publication gate with no further launches; a later task-owned change is stale.
- Targeted receipt tests in `tests.test_requirement_integration` and `tests.test_requirement_execution` passed.
- `DEV_PLATFORM_TEST_JOBS=3 python3 scripts/run_test_groups.py --group fast-b --group fast-c --group fast-d` passed.
- `openspec validate stabilize-independent-review-cycles --strict` passed; `python3 template/scripts/openspec_lifecycle.py check` passed; private-reference guard passed.
- The final candidate's full automated checks and independent review are produced by the archive helper and recorded in the archived `automated-checks.json` and review evidence.
