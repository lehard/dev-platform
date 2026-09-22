# Verification: add-platform-health-review-report

OpenSpec-Verify: PASS

Verification-Method: local deterministic validation (unit tests for the new report-aggregation script against a fake gh client, full platform test-group suite, OpenSpec structural + hygiene validation, gh-aw compile drift check) both before and after reconciling with the merged `main`; live gh-aw cloud dispatch of the combined trigger (including the double-dispatch replace check) is an explicit documented post-merge follow-up, not performed pre-archive

Automated-Checks-Evidence: automated-checks.json

## Scope of this receipt

This records what was actually run for the `add-platform-health-review-report`
change (managed Issue lehard/development-backlog#167). Prerequisite siblings
`add-architecture-health-cloud-review` (#165) and
`add-platform-health-review-orchestration` (#166) have both since merged to
`main`, establishing the same "live workflow_dispatch requires the workflow's
file (and every reusable workflow it calls) to already exist on the default
branch" structural GitHub constraint (see `design.md`'s "Verification note").
Per the user's decision applied consistently across the whole
#165->#166->#167->#169 chain, the one `tasks.md` live-dispatch item is
reworded as an explicit **post-merge** follow-up rather than a pre-archive
gate. Every other item, and everything verifiable pre-merge, was actually run
and passed, so this change is archive-ready on that basis.

## Step 0: sibling merge, then reconcile with merged main

`git merge agent/add-platform-health-review-orchestration` from inside this
worktree originally fast-forwarded cleanly. After #165 and #166 actually
merged to `main`, `python3 scripts/dogfood_task.py reconcile` was run to
replace that provisional local merge with real history; it stopped at merge
conflicts in `.github/workflows/platform-health-review.yml` and
`tests/test_agentic_workflows.py` (expected: main had since gained #166's
merge plus a separate quick-fix, `fix-platform-health-review-permissions`,
that corrected insufficient job-level `permissions:` on the two review-calling
jobs -- discovered by #166's own post-merge live-dispatch follow-up -- while
this branch's commit already added the `publish-report` job on top of the
pre-fix content). Resolved by combining both sides by hand: kept the
corrected `permissions:` blocks (and their explanatory comments) from `main`
on the `process-health-review`/`architecture-health-review` jobs, and kept
this task's own `publish-report` job addition unchanged; in the test file,
kept both this task's new/updated tests
(`test_platform_health_review_publishes_one_combined_report`, the
updated `test_platform_health_review_jobs_do_not_depend_on_each_other`) and
main's new `test_caller_job_permissions_cover_every_nested_job_in_the_called_workflow`
regression test. Also removed two now-stale duplicate pre-archive OpenSpec
change directories (`add-architecture-health-cloud-review`,
`add-platform-health-review-orchestration`) that were leftover artifacts of
the original local stacked-branch merges -- confirmed via
`git show origin/main:<path>` that `main` never contained them at their active
(non-archived) location, only under `openspec/changes/archive/...`.
Confirmed afterward: `dogfood_task.py status` reports `task freshness: ahead
relative to origin/main` (no longer diverged), and the full validation suite
(below) was re-run against this reconciled state and passed.

## What was implemented

See `design.md`'s "Implementation addendum (as built)" section for the full
rationale. Summary: a third, deterministic (non-agentic) job,
`publish-report`, was added to `.github/workflows/platform-health-review.yml`.
It `needs: [process-health-review, architecture-health-review]` with
`if: always()`, reads each review job's `result` and its
`created_issue_number` / `created_issue_url` `workflow_call` outputs (already
exposed by each review's compiled lock file -- no change to either review's
gh-aw source, tools, engine, safe-outputs, or content rules was required), and
calls the new `scripts/publish_platform_health_review_report.py` as a plain
Actions step to compose and publish exactly one combined report Issue,
title-prefixed `[platform-health-review] `, replacing any prior open issue
under that same prefix (the script re-implements gh-aw's
`close-older-issues` / title-prefix semantics itself via `gh api`, since this
step is plain Actions rather than a gh-aw safe output).

Each review's own individual report issue (`[process-backlog] ...`,
`[architecture-health] ...`) is kept, not retired -- see the design addendum
for why.

## Commands run and results

All from `/Users/Shared/Workspace/dev-platform/.claude/worktrees/add-platform-health-review-report`.

1. `python3 -m compileall -q template/scripts scripts`
   - Exit 0, no output (no syntax errors).

2. `python3 scripts/managed_projects.py validate`
   - `Managed project registry: OK (3 managed, 0 candidate, 0 excluded)` -- exit 0.

3. `python3 scripts/run_test_groups.py --all`
   - Ran in the background (exceeded the 2-minute foreground limit); completed
     with exit code 0.
   - `DEV_PLATFORM_TEST_COVERAGE`: `declared_test_count: 1173`,
     `discovered_test_count: 1173`, `declared_but_not_discovered: []`,
     `duplicated_tests: []`, `missing_from_groups: []` -- the new
     `tests/test_publish_platform_health_review_report.py` module (24 tests)
     was registered in `dev-platform/checks.toml`'s `fast-a` group so the
     mandatory-suite-equivalence check passed.
   - `DEV_PLATFORM_TEST_AGGREGATE`: `group_count: 13`, `failed_groups: []`,
     `outcome: "success"`, `group_seconds_total: 745.732`.
   - All 13 groups (`delegated_write_guard`, `fast-a`, `fast-b`, `fast-c`,
     `fast-d`, `git_lifecycle`, `managed_task_exact_state`,
     `merge_lifecycle_resilience`, `model_routing`,
     `protected_main_zero_handoff`, `publication_recovery_cli`,
     `publication_state`, `worktree_hygiene`) reported `exit_code: 0`,
     `outcome: "success"`.

4. `python3 template/scripts/openspec_lifecycle.py check`
   - `OpenSpec lifecycle hygiene: OK` -- exit 0.

5. `openspec validate add-platform-health-review-report --strict --no-interactive`
   - `Change 'add-platform-health-review-report' is valid` -- exit 0.

6. `python3 scripts/validate_agentic_workflows.py`
   - Compiled `process-issue-triage`, `weekly-process-backlog-review`,
     `architecture-health-review` with `gh aw compile ... --strict --validate`
     (gh-aw v0.85.4, matching `.github/aw/gh-aw-version.txt`).
   - `✓ Compiled 3 workflows: 3 succeeded, 0 warnings`.
   - `git diff --exit-code` against `.github/aw` and the three `.lock.yml`
     files reported no drift.
   - `Agentic workflow sources and locks match gh-aw v0.85.4.` -- exit 0.
   - Note: `platform-health-review.yml` and
     `scripts/publish_platform_health_review_report.py` are plain,
     non-gh-aw Actions/Python and are intentionally outside this compiler
     check's scope; they are covered instead by
     `tests/test_agentic_workflows.py` (new
     `test_platform_health_review_publishes_one_combined_report`, the
     updated `test_platform_health_review_jobs_do_not_depend_on_each_other`,
     and main's `test_caller_job_permissions_cover_every_nested_job_in_the_called_workflow`
     picked up by the reconcile) and by the new
     `tests/test_publish_platform_health_review_report.py`.

7. `python3 -m unittest tests.test_agentic_workflows -v` (re-run post-reconcile)
   - 13 tests, all passed (`OK`): this task's two new/updated tests covering
     the `publish-report` job's shape and the review jobs' continued
     independence from each other, plus the permissions-ceiling regression
     test picked up from `main` via the reconcile.

8. `python3 -m unittest tests.test_publish_platform_health_review_report -v`
   - 24 focused unit tests, all passed (`OK`). These exercise, against a
     `FakeGh` (no real `gh` binary or live GitHub call): per-outcome section
     rendering for success-with-issue, success-without-issue, skipped,
     failure, cancelled, and an unrecognized result string; `reviewed_at`
     extraction from a report body; previous-review-boundary selection across
     zero/one/multiple prior reports; report title formatting; full report
     body composition; the end-to-end `publish()` flow for a normal run, a
     repeat run that closes the prior report and carries its boundary
     forward, a defensive case ensuring the newly created issue number is
     never self-closed, and a partial run (one review failed) that still
     publishes with the gap stated explicitly; plus `gh api --paginate`
     JSON-array-splitting edge cases and outcome-argument parsing/stripping.

9. `python3 scripts/dogfood_task.py route-claude --profile routine --rationale "..." --evidence "..."`
   - Recorded cleanly (`R2`, routine profile) after the reconcile removed the
     two stale duplicate OpenSpec directories, leaving exactly one
     materialized change (`add-platform-health-review-report`) in this
     worktree. `report-claude-execution` recorded a clean containment
     postcheck.

## Post-merge follow-up (not a pre-archive gap)

- **Live double-dispatch of `platform-health-review.yml` in
  `lehard/dev-platform`.** Documented in `tasks.md` and `design.md` as an
  explicit post-merge follow-up: the workflow (and every reusable workflow it
  calls) must exist on `main` before `workflow_dispatch` recognizes it at
  all. To be performed once this change merges, alongside #165's and #166's
  own already-completed post-merge dispatch confirmations.
