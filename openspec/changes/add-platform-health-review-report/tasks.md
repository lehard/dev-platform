# Tasks

## 1. Specify the combined report

- [x] Add the combined-report ADDED Requirement to the `platform-health-review` OpenSpec delta, with scenarios for a normal combined run, a repeat run replacing the prior report, and a partial run where one review's section is missing.

## 2. Implement the report step

- [x] Add or extend a `create-issue` safe output (fixed title prefix, `close-older-issues: true`, `max: 1`) that composes both reviews' sections into one dated report body recording `reviewed_at`, exact `main` SHA, and previous-review boundary.
  - Implemented as a third, deterministic (non-agentic) `publish-report` job in `.github/workflows/platform-health-review.yml`, since #166's architecture keeps each review as its own independent agentic job with its own gh-aw `create-issue` safe output rather than merging them into one agent job. `publish-report` `needs: [process-health-review, architecture-health-review]` with `if: always()`, reads each job's `result` and its `created_issue_number`/`created_issue_url` workflow_call outputs, and calls the new repository-owned `scripts/publish_platform_health_review_report.py` as a plain Actions step. That script re-implements the `close-older-issues`/title-prefix replace-not-accumulate semantics itself (via `gh api`), since this step is plain Actions rather than a gh-aw safe output. See the design note below and `verification.md` for why this shape was chosen.
- [x] Ensure a missing/failed review section is stated explicitly rather than silently omitted.
  - `render_section()` in `scripts/publish_platform_health_review_report.py` states explicitly whether each review ran, produced no report issue, failed, was cancelled, or was skipped; `if: always()` on `publish-report` guarantees this runs even when a review job failed.

## 3. Verify and document

- [ ] Manually dispatch the combined trigger twice in `lehard/dev-platform` and confirm the second run replaces the first report rather than creating a duplicate.
  - Deliberately deferred: this requires a live GitHub Actions dispatch, which is out of scope for this task per the coordinated deferred live-dispatch round across #165 -> #166 -> #167 -> #169. Not attempted.
- [x] Run `openspec validate --strict` for the change, full platform test groups, and semantic OpenSpec verification; record truthful evidence in `verification.md`.

## Logical commits

- [x] Commit the OpenSpec delta and the report-generation wiring together, since they jointly define one observable capability: a single combined durable report per run.
