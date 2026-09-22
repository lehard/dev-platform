# Design: One combined durable report per Platform Health Review run

## Boundary

The report mechanism is presentation/aggregation only: it does not change what either review evaluates. It reuses the exact `create-issue` safe-output shape (title prefix, `close-older-issues: true`, `max: 1`) already accepted for the process-backlog report, extended to carry both reviews' sections in one issue body.

## Report shape

Following the existing accepted report contract:

- Records `reviewed_at`, the exact current `main` SHA, and the previous-review boundary.
- Contains one section per review (process, architecture) with each review's own existing bounded content rules (e.g. the process review's existing 500-word/5-item bounds stay in force for its own section).
- Uses one fixed title prefix (distinct from the existing `[process-backlog]` prefix, e.g. `[platform-health-review]`) and `close-older-issues` so a new run replaces the prior report rather than accumulating duplicates.

## Verification note

`tasks.md` originally listed a live double-dispatch smoke test in
`lehard/dev-platform` as a pre-archive verification item. As established by
prerequisite changes `add-architecture-health-cloud-review` and
`add-platform-health-review-orchestration`, GitHub Actions only recognizes a
`workflow_dispatch`-triggerable workflow, and accepts a dispatch request for
it, once that workflow's file exists on the repository's **default branch**
-- and this holds for every reusable workflow a caller `uses:`, not only the
top-level one. This change's `publish-report` job is a new job inside the
already-merged `platform-health-review.yml`, so the same structural
constraint applies. The live-dispatch confirmation is therefore an explicit
**post-merge** follow-up (see `tasks.md`), not a pre-archive gate: everything
verifiable pre-merge (unit tests for
`scripts/publish_platform_health_review_report.py` covering normal/partial/
repeat-run behavior with mocked `gh` calls, `openspec validate --strict`, and
the full platform test suite) was verified before archive.

## Compatibility and rollback

If either underlying review is temporarily unavailable, the report step still records whichever review's output is available and notes the gap; it does not fail the whole report because one section is missing. Reverting this change removes the combined report only; each review's own existing safe-outputs behavior (if any is retained independently) is unaffected.

## Risks and mitigations

- Risk: merging two reviews' output into one issue could exceed a reasonable size/readability bound. Mitigation: each review's own existing content bounds (e.g. up to-N-items sections) are kept per section rather than relaxed for the combined report.
- Risk: a partial run (one review fails) could look like a false "all clear." Mitigation: the report explicitly states per-section whether that review actually ran, rather than omitting a failed section silently.

## Implementation addendum (as built)

`add-platform-health-review-orchestration` (#166) did not merge Process Health
Review and Architecture Health Review into one agentic job; it kept them as
two independent gh-aw agentic workflows, each still with its own `create-issue`
safe output, each called from a single non-agentic orchestrator
(`.github/workflows/platform-health-review.yml`) with no `needs:` between the
two review jobs. Given that shape, the combined report in this change is
implemented as a third, deterministic (non-agentic) job in that same
orchestrator, `publish-report`:

- `needs: [process-health-review, architecture-health-review]` with
  `if: always()`, so it still runs when either review job failed.
- It reads each review's job `result` plus the `created_issue_number` /
  `created_issue_url` outputs that each review's compiled `workflow_call` lock
  file already exposes (`jobs.safe_outputs.outputs.created_issue_number` /
  `..._url`) -- no new instrumentation of either review was required.
- It composes and publishes one combined report Issue through a new
  repository-owned script, `scripts/publish_platform_health_review_report.py`,
  invoked as a plain Actions step (`python3 scripts/...`), consistent with the
  platform's "keep CI providers thin" invariant
  (`openspec/specs/ci-safety/spec.md`): portable logic lives in a versioned,
  unit-tested script, not inline YAML.
- Because this step is plain Actions rather than a gh-aw safe output, the
  script re-implements the same `close-older-issues` / fixed-title-prefix
  replace-not-accumulate semantics itself, using `gh api` (list open issues
  labeled `platform-health-review` whose title starts with
  `[platform-health-review] `, create the new report, then close every other
  matching open issue).

**Choice: each review's own individual report issue is kept, not retired.**
Both `weekly-process-backlog-review.md` and `architecture-health-review.md`
keep their own standalone `workflow_dispatch` trigger independent of the
combined orchestrator (a documented, unchanged property from #166). If either
review's own `create-issue` safe output were removed, a standalone dispatch of
that review would produce no durable report at all. Removing it would also
mean editing each review's own gh-aw source/safe-outputs, which is out of
scope for this change (the proposal's non-goals state this change "does not
change either review's own findings/reasoning, and does not alter the
existing source-issue mutation rules"). The combined report is therefore
strictly additive: an aggregation on top of the two existing, unchanged
per-review reports, not a replacement for them.
