# Verification: add-platform-health-review-orchestration

## Status: NOT YET ARCHIVE-READY

This change is implemented and passes every deterministic/automated check run
so far. It is intentionally **not** marked `OpenSpec-Verify: PASS` and has
**not** been archived, because one authored `tasks.md` item under "3. Verify
and document" is deliberately left open:

- [ ] Manually dispatch the combined trigger in `lehard/dev-platform` and
  confirm both reviews run for the same trigger event.

This is a deliberate, explicit deferral, not an oversight: this change is one
link in a stacked chain of four dependent changes
(`add-architecture-health-cloud-review` #165 → `add-platform-health-review-orchestration`
#166 → `add-platform-health-review-report` #167 → #169), and the user
supervising the chain has explicitly instructed that every real cloud-workflow
dispatch (which spends AI-credit budget and would publish real GitHub Issues)
is deferred to one later coordinated round across all four changes, run only
after all four are implemented. `template/scripts/openspec_lifecycle.py
archive` refuses to archive while any `tasks.md` checkbox is unchecked, so
this receipt records real, truthful evidence of everything that could be
verified deterministically without a live dispatch, and explicitly flags the
one item that is intentionally still open.

Separately, `python3 scripts/dogfood_task.py route-claude` was attempted and
refused: "model routing requires exactly one materialized managed OpenSpec
change in this task checkout; found 2". This worktree currently contains both
this change's own `openspec/changes/add-platform-health-review-orchestration/`
and the still-unarchived, still-unmerged-to-main
`openspec/changes/add-architecture-health-cloud-review/` pulled in by the
required sibling-branch merge (step 0 of this task). That sibling change is
also deliberately left unarchived pending the same deferred live-dispatch
round, so this is an expected, structural consequence of the stacked-branch
approach the user chose, not a defect in this change. Routing was not part of
the validation list this task was explicitly asked to run, so it was not
forced past this refusal.

## Verification-Method: local deterministic validation (gh-aw compile, structural/unit tests, full platform test-group suite, OpenSpec structural + hygiene validation); no live gh-aw cloud dispatch performed

## Sibling merge (step 0)

`git merge agent/add-architecture-health-cloud-review` into
`agent/add-platform-health-review-orchestration` fast-forwarded cleanly
(`fb912d2..5bde96d`, "Fast-forward", no conflicts), since neither branch had
touched the same files. Confirmed present afterward:
`.github/workflows/architecture-health-review.md` and
`.github/workflows/architecture-health-review.lock.yml`.

## What was implemented

- `.github/workflows/weekly-process-backlog-review.md` and
  `.github/workflows/architecture-health-review.md`: each review's own
  `on:` trigger dropped its independent `schedule:` and kept
  `workflow_dispatch:` (so each remains independently, manually runnable
  exactly as before), and gained a new `workflow_call:` trigger. No other
  frontmatter or prompt-body content changed.
- Both `.lock.yml` files recompiled with `gh aw compile <id> --strict`
  (`weekly-process-backlog-review`, `architecture-health-review`; v0.85.4,
  matching `.github/aw/gh-aw-version.txt`). The diff is exactly the expected
  shape: the `schedule:`/`cron:` block is replaced by gh-aw's automatic
  `workflow_call` support (host-repo resolution step, `aw_context` input,
  `created_issue_number`/`created_issue_url` outputs, per-artifact name
  prefixing, and a compiler-injected `pre_activation` team-membership gate
  job). `engine: codex`, `tools:`, `safe-outputs:`, and every
  `max-ai-credits`/`max-daily-ai-credits`/`timeout-minutes`/`max-turns`
  guardrail are byte-identical to their pre-change values in both lock
  files — confirmed by inspecting the compiled diff directly, not merely
  asserted.
- New `.github/workflows/platform-health-review.yml`: a plain, non-agentic
  GitHub Actions workflow (no gh-aw source, no AI engine, no new AI-credit
  spend) that owns the one combined `schedule` (weekly, one explicit cron)
  + `workflow_dispatch` trigger. It has two jobs, each calling one of the
  two compiled `.lock.yml` files as a reusable workflow (`uses: ./.github/
  workflows/<file>.lock.yml`, `secrets: inherit`), with matching
  `permissions:` per job. Neither job declares `needs:` on the other, so a
  failure in one review's job cannot block or cancel the other's job or its
  own safe output — satisfying the "One review fails independently"
  scenario in `specs/platform-health-review/spec.md` by construction (two
  independent GitHub Actions jobs, not a shared job or `needs:` chain).
- `tests/test_agentic_workflows.py`: removed the now-stale
  `"schedule: weekly"` required-substring assertions for both reviews (they
  no longer declare an independent schedule), added `"workflow_call:"` to
  each review's required set, and added four new tests: both reviews no
  longer declare `schedule:` and do declare `workflow_call:` +
  `workflow_dispatch:`; both compiled locks expose the `workflow_call:`
  trigger and no longer contain a `cron:` line; the orchestrator declares a
  `schedule`/`cron` + `workflow_dispatch` and calls both lock files with
  `secrets: inherit`; and the orchestrator's `jobs:` block contains no
  `needs:` (independent-failure guarantee).

## Automated checks actually run (all passed)

- `python3 -m compileall -q template/scripts scripts` — exit 0
- `python3 scripts/managed_projects.py validate` — `Managed project registry: OK (3 managed, 0 candidate, 0 excluded)`
- `python3 scripts/run_test_groups.py --all` — 13/13 groups succeeded, 1148/1148 declared tests discovered and run (`DEV_PLATFORM_TEST_AGGREGATE: {"failed_groups": [], "group_count": 13, ... "outcome": "success", ...}`)
- `python3 template/scripts/openspec_lifecycle.py check` — `OpenSpec lifecycle hygiene: OK`
- `openspec validate add-platform-health-review-orchestration --strict --no-interactive` — `Change 'add-platform-health-review-orchestration' is valid`
- `python3 scripts/validate_agentic_workflows.py` — `Agentic workflow sources and locks match gh-aw v0.85.4.` (recompiles `process-issue-triage`, `weekly-process-backlog-review`, `architecture-health-review` and asserts zero generated-file drift against the working tree; `process-issue-triage.lock.yml` and `.github/aw` were confirmed unchanged by this task)
- `python3 -m unittest tests.test_agentic_workflows -v` — 11/11 tests passed, including the four new combined-trigger tests
- `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/platform-health-review.yml'))"` (ad hoc, not a committed test) — parses without error; confirmed the plain `on:` key (which PyYAML's default loader reads as boolean `True`, a well-known YAML 1.1 quirk) matches the same unquoted style already used by every other plain workflow in this repository (`ci.yml`, `project-ci.yml`, `reconcile-stale-rollouts.yml`, etc.), so GitHub Actions' own parser is unaffected

## Not run / explicit gap

- **Live dispatch of `platform-health-review.yml` (or either underlying review) in `lehard/dev-platform`.** This requires the workflow to exist on a pushed ref; a live run would spend real AI-credit budget on both Codex-driven reviews and could publish two real GitHub Issues via their declared `create-issue` safe outputs. Per explicit instruction, this is deferred to one later coordinated round across the full #165→#166→#167→#169 chain, after all four changes are implemented — not attempted here.
- **`python3 scripts/dogfood_task.py route-claude`** — attempted, refused by the tool itself ("found 2" materialized changes in this worktree, see above). Not part of the validation list this task was asked to run; not forced past the refusal.

## Semantic OpenSpec review (performed manually; no `/opsx:verify` integration available in this environment)

- Outcome vs. success evidence (`proposal.md`): "Each review's own existing advisory/read-only/safe-outputs behavior is provably unchanged" is met — verified directly via the compiled-lock diff (guardrails and safe-outputs byte-identical). "A single manual dispatch, and separately the configured schedule, starts both reviews for the same run" is met by construction (one `workflow_dispatch`/`schedule` on the orchestrator, two `workflow_call` jobs with no `needs:`) but not yet observed live — that is the one open, deliberately-deferred item. "`openspec validate --strict` passes" is met.
- Completeness vs. `design.md`: the design explicitly left the choice between "extend one workflow to invoke the other job" and "keep both as separate workflows sharing one identical schedule/dispatch definition, started together" to implementation time. This change implements a variant of the second shape — trigger consolidation onto one new, shared, non-agentic orchestrator using gh-aw's native `workflow_call` reusable-workflow support — rather than literally duplicating an identical cron on both individual sources, because that would either (a) leave three separate weekly schedules firing (two individual plus one combined) if the per-review schedules were kept, tripling scheduled AI-credit spend and contradicting the design's own stated mitigation against "doubled AI-credit spend per combined run", or (b) still require a separate mechanism to make "a single manual dispatch...starts both" literally true, since two independently-scheduled `workflow_dispatch` triggers cannot be fired as one GitHub Actions action. The chosen shape satisfies both the schedule and dispatch halves of the observable behavior the design requires with one mechanism, keeps each review's engine/tools/safe-outputs declaration textually unchanged, and required no new capability beyond gh-aw's already-built-in `workflow_call` trigger support (confirmed present and correctly wired by the compiler's own generated output, not authored by hand).
- Correctness: the two modified `.md` sources' compiled-lock diffs contain no new `uses:` actions, no new declared secrets beyond what gh-aw's `workflow_call` plumbing itself requires (already-present secrets, now also exposed as optional workflow_call secrets), and no permission escalation (`permissions: {}` unchanged at the top level of both lock files).
- Coherence: `specs/platform-health-review/spec.md`'s four scenarios (scheduled combined run, manually dispatched combined run, one-review-fails-independently, central-pilot-precedes-downstream-rollout) are all addressed by the implemented shape; the fourth (central-pilot) required no code change since `platform-health-review.yml` is authored only in this repository and this task did not touch any managed-rollout/downstream-deployment path.
