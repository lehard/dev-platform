OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the implementation diff against the hosted-review-transition-continuity deltas (lifecycle-workers added, publication-queue modified), proposal, design and tasks; incident evidence from lehard/dev-platform#619 records and hosted run logs; repository-owned selected checks on the candidate head
Automated-Checks-Evidence: automated-checks.json

Implementation: the supervisor implemented the change directly. The routing plan named a delegated child; the owner approved the supervisor-written diff in chat on 2026-10-20 (`model_routing.py approve-supervisor-diff`).

Design change before implementation: the approved ADD proposed recording lineage on the candidate. Implementation found that `private_lineage` is enabled for this repository, so a private Backlog reference must not reach the public PR either. Attribution was therefore changed to the public work identity encoded in the managed branch. The proposal, design, tasks and spec deltas were updated first.

Completeness, per spec scenario (all in `tests/test_hosted_review_continuity.py` unless noted):
- Hosted review with material findings, hosted contract without `[development_backlog]` (`authoring_config` patched to fail): one run records `repair-pending` on the pushed head, one trusted evidence record with `work_identity=BR-7`, `child_identity=BR-7/T1` and no `requirement` field, exactly one worker `update` marker, and the next job is `repair`. The Requirement retrospective lists the record.
- Malformed managed branch: the sink raises before any comment or local event (`tests/test_coordinator_evidence.py`); `run_claimed` fails before the reviewer runs and writes no record.
- Evidence write failure: no `repair-pending` record is published.
- Pull request head lag after the own push: the job publishes its transition. Foreign head or changed claim: discarded with nothing published. A head that never converges: explicit `WorkerError` (finalize path test updated accordingly in `tests/test_post_review_finalization.py`).
- Review without material findings: `finalize-pending` carries `developer-friction`, `selected-checks`, `semantic-verification` and `review`; `reestablish_gates` neither reruns checks nor requires fresh semantic verification.
- Interrupted review push recovered from its `validated-push` receipt keeps the admission gates through the next claim and review. Changed task content and head-only legacy gates are not carried.
- `restore-gates`: restores the proven admission gates without changing state, refuses a second run, a head without a trusted harness push, a push that changed task content, and an unexpected head, writing nothing on refusal.
- Legacy evidence records that stored a `requirement` reference still match the Requirement.

Correctness: no fallback added. Attribution has a single source (the branch). The bounded wait re-reads the same observation and then fails explicitly; it does not substitute another strategy. `resolve_lineage` stays only for local post-merge obligations.

Coherence: design decisions 1-6 are implemented as written. Docs updated: `hosted-lifecycle-workers.md`, `chat-coordinator.md`, `agent-workflow.md` (the `finalize-pending` lost-gates path, closing the gap of lehard/dev-platform#624 for unchanged content).

Known limits:
- Local friction mirrors of coordinator events now carry `work_identity` instead of the private Requirement reference. They are matched to the Requirement by that identity.
- The recovery of lehard/dev-platform#619 itself is an operational step after this change merges (`restore-gates --pr 619`), not part of this candidate.
- The cause of the 2026-10-19 discards (PR API lag after the push) is inferred from run timing; the change does not depend on it for safety.

Checks run before the selected-checks run:
- `python3 scripts/check_private_backlog_refs.py --root .` passed.
- `compileall` and `ruff check scripts template/scripts tests` passed.
- `openspec validate hosted-review-transition-continuity --strict` and `openspec_lifecycle.py check` passed.
- `run_test_groups.py --verify-coverage` passed (3069 tests, no gaps).
- Targeted suites passed: `test_hosted_review_continuity` (14), `test_coordinator_evidence`, `test_pr_review_gate`, `test_candidate_lifecycle`, `test_autonomous_integration_contour`, `test_post_review_finalization`, `test_lifecycle_workers`, `test_hosted_workers`.
- An earlier `run_test_groups.py --all` stopped at the routing early gate (supervisor diff not yet approved). It is not counted as a pass.

Selected checks: `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/hosted-review-transition-continuity/automated-checks.json`. The outcome is recorded in `automated-checks.json`.
