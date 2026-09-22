# Verification: add-platform-health-review-report

## Scope of this receipt

This records what was actually run for the `add-platform-health-review-report`
change (managed Issue lehard/development-backlog#167), on branch
`agent/add-platform-health-review-report`, after merging in the sibling branch
`agent/add-platform-health-review-orchestration` (which itself already
contains `add-architecture-health-cloud-review`, #165, merged into it).

This change is deliberately **not** archived and this receipt is **not** a
completion claim for the whole four-change stack (#165 -> #166 -> #167 ->
#169). One task item is deliberately left unattempted (see below) pending a
later coordinated live-dispatch round across all four related changes. Do not
read this file as `OpenSpec-Verify: PASS`.

## Step 0: sibling merge

`git merge agent/add-platform-health-review-orchestration` from inside this
worktree fast-forwarded cleanly (no conflicts, no manual resolution needed).
Confirmed present afterward:
- `.github/workflows/platform-health-review.yml` (the combined orchestrator)
- `.github/workflows/architecture-health-review.md` / `.lock.yml`
- `.github/workflows/weekly-process-backlog-review.md` / `.lock.yml` (updated
  for the combined `workflow_call` trigger)
- `openspec/changes/add-architecture-health-cloud-review/` and
  `openspec/changes/add-platform-health-review-orchestration/` (left
  untouched, not archived, per instructions -- they are not this task's
  concern)

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
     `test_platform_health_review_publishes_one_combined_report`, and the
     updated `test_platform_health_review_jobs_do_not_depend_on_each_other`)
     and by the new `tests/test_publish_platform_health_review_report.py`.

7. `python3 -m unittest tests.test_agentic_workflows -v`
   - 12 tests, all passed (`OK`), including the two new/updated tests
     covering the `publish-report` job's shape and the review jobs' continued
     independence from each other.

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

9. `python3 scripts/dogfood_task.py route-claude --profile standard --rationale "..." --evidence "..."`
   - Refused: `Model routing blocked: model routing requires exactly one
     materialized managed OpenSpec change in this task checkout; found 3`.
   - Expected consequence of the stacked-branch approach (three
     `openspec/changes/` packages are materialized simultaneously:
     `add-architecture-health-cloud-review`,
     `add-platform-health-review-orchestration`, and
     `add-platform-health-review-report`), matching what the prior sibling
     task (`add-platform-health-review-orchestration`) also recorded. Not
     forced; recorded here as-is per instructions.

## Explicitly deferred / not attempted

- `tasks.md` item "Manually dispatch the combined trigger twice in
  `lehard/dev-platform` and confirm the second run replaces the first report
  rather than creating a duplicate" -- **deliberately not attempted**. It
  requires a live GitHub Actions dispatch against the real repository, which
  is out of scope for this task per the explicit instruction to defer all
  live-dispatch verification to a later, separate coordinated round across
  the four related changes (#165 -> #166 -> #167 -> #169). This checkbox is
  left unchecked in `tasks.md`.
- `openspec_lifecycle.py archive`, `dogfood_task.py finish`, `git push`, and
  opening a PR were not run, per instructions -- this branch is left ready for
  the next sibling task (#169, `add-platform-health-review-notifications`) to
  merge on top of it the same way this task merged #166's branch.

## Explicit statement

This is **not** a pass/complete verification receipt for the OpenSpec
lifecycle. Do not treat this file as `OpenSpec-Verify: PASS`. One required
task item (live manual-dispatch confirmation) is deliberately deferred, as
described above.
