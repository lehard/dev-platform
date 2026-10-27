OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review of the publication_queue.py, pr_review_gate.py, integration_contour.py, docs and test diff against the publication-queue delta, proposal, design and tasks; Python 3.11 compileall of template/scripts, scripts and tests plus a 3.11 unittest run of tests/test_pr_review_gate.py (68 OK) and the integration-repair classes of tests/test_autonomous_integration_contour.py (26 OK); repository-owned selected checks (full set) on the committed candidate head
Automated-Checks-Evidence: automated-checks.json

## Scope

A developer fix re-admits a candidate waiting in `integration-repair-pending`, and the integration-repair writer brief carries the failed required check's identity and log excerpt. Changed: `template/scripts/publication_queue.py`, `template/scripts/pr_review_gate.py`, `template/scripts/integration_contour.py`, `docs/engineering/agent-workflow.md`, the platform manifest and three test modules.

## Completeness

- Requirement "A developer fix re-admits a candidate waiting for integration repair":
  - Accepted fix (scenario 1): `integration-repair-pending` joins `READMISSION_STATES`; `_supersession` keeps its checks (record bound to the proven integrated head, same task, no live job claim, descendant head). Test `test_developer_fix_supersedes_the_unclaimed_integration_repair_job`: the new admission records `supersedes` with state `integration-repair-pending`, the candidate is `review-pending` at the new head and the offered job is the review, not the integration repair.
  - Live claim (scenario 2) and unrelated head (scenario 3): `test_developer_fix_of_integration_repair_refuses_a_live_claim_and_an_unrelated_head` asserts "integration-repair job is claimed by writer" and "does not descend from the admitted head", with no comment written.
  - Archived task re-opened: `local_status` returns `readmission` for an unpushed local head that strictly descends from the proven head when the latest record at that head is `integration-repair-pending` (`test_unpushed_fix_on_an_integration_repair_wait_is_observed_for_admission`, which also keeps the explicit refusal for a non-descendant head, another state, a record bound elsewhere and a missing record); `semantic_readmission` accepts that lineage; `pr_review_gate` re-opens the archived handoff (`test_integration_repair_wait_reopens_the_archived_handoff`). The archived re-handoff still requires a re-recorded semantic receipt.
- Requirement "An integration-repair writer receives the failed check's evidence":
  - The queue records each failed required check (name, workflow, state, link) as `red_gate.evidence.failed_checks` with the message under `detail` (`test_failing_integration_check_creates_a_repair_job_not_a_block`, only the failed row is kept).
  - Brief carries the log (scenario 1): `test_red_check_writer_brief_carries_the_failed_log_excerpt` runs a real integration repair; the writer prompt's brief names `validate`, its link and the last 80 log lines ending in the failing error, and the log was read for exactly run 1 / job 2.
  - Brief without evidence refused (scenario 2): `test_red_check_brief_without_evidence_is_refused_before_any_writer_starts` covers no failed-check identity, no Actions job link and an empty log; each raises `WorkerError` naming the cause before any non-git process, posts no result, pushes nothing and leaves the offered job (attempt) unchanged. `test_unreadable_failed_log_names_the_job_and_gh_output` covers a failing `gh run view --log-failed`.
- No fallback added: a missing or unreadable evidence source raises; existing string evidence of other red gates is unchanged.
- Known limit, recorded: a Requirement-integration base whose required check is App-bound is observed through check runs without an Actions job link, so its writer brief is refused with that reason; the developer fix re-admission is the supported path there.

All tasks in `tasks.md` are complete.

## Selected checks

`python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/integration-repair-readmission-evidence/automated-checks.json` on head 2551ebbc passed: affected precheck, compileall, ruff, `generate_platform_manifest.py --check`, `run_test_groups.py --all`.
