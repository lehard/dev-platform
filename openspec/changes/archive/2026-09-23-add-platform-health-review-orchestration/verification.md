# Verification: add-platform-health-review-orchestration

OpenSpec-Verify: PASS

Verification-Method: local deterministic validation (gh-aw compile, structural/unit tests, full platform test-group suite, OpenSpec structural + hygiene validation) both before and after reconciling with the merged `main`; live gh-aw cloud dispatch of the combined trigger is an explicit documented post-merge follow-up, not performed pre-archive

Automated-Checks-Evidence: automated-checks.json

The prerequisite sibling change `add-architecture-health-cloud-review` (#165)
has since merged to `main` (PR #31, merge commit `9b5a449`), establishing the
same "live workflow_dispatch requires the workflow's file to already exist on
the default branch" structural GitHub constraint (see `design.md`'s
"Verification note"). Per the user's explicit decision applied consistently
across the whole #165→#166→#167→#169 chain, the `tasks.md` live-dispatch item
is reworded as an explicit **post-merge** follow-up rather than a pre-archive
gate — it is checked because it now correctly describes deferred post-merge
work, not because a live dispatch already happened. Every other item, and
everything that *is* verifiable pre-merge, was actually run and passed (see
below), so this change is archive-ready on that basis.

## Sibling merge (step 0, then reconcile with merged main)

`git merge agent/add-architecture-health-cloud-review` into
`agent/add-platform-health-review-orchestration` originally fast-forwarded
cleanly (`fb912d2..5bde96d`, "Fast-forward", no conflicts), since neither
branch had touched the same files at that point. After #165 actually merged
to `main` (squash commit `9b5a449`), `python3 scripts/dogfood_task.py
reconcile` was run to replace that provisional local merge with real history;
it stopped at merge conflicts in `.github/workflows/architecture-health-review.{md,lock.yml}`
and `tests/test_agentic_workflows.py` (expected: this change's own commit
`2f1f786` already rewired those same files' trigger from `schedule:` to
`workflow_call:`, while `main`'s incoming version was #165's original,
pre-rewire `schedule:` state). Resolved by keeping this branch's already-correct
evolved content (`git checkout --ours` for the two workflow files, confirmed
byte-identical to pre-conflict via `validate_agentic_workflows.py` reporting
zero drift after resolution; manually merged the two conflicting assertion
blocks in `tests/test_agentic_workflows.py` to keep the post-rewire
expectations — no `schedule: weekly` substring, `workflow_call:` present —
for both reviews) and committing the merge (`155095b`). Confirmed afterward:
`dogfood_task.py status` reports `task freshness: ahead relative to
origin/main` (no longer diverged), and the full validation suite (below) was
re-run against this reconciled state and passed.

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

## Automated checks actually run (all passed, re-run after reconciling with merged main)

- `python3 -m compileall -q template/scripts scripts` — exit 0
- `python3 scripts/managed_projects.py validate` — `Managed project registry: OK (3 managed, 0 candidate, 0 excluded)`
- `python3 template/scripts/openspec_lifecycle.py check` — `OpenSpec lifecycle hygiene: OK`
- `openspec validate add-platform-health-review-orchestration --strict --no-interactive` — `Change 'add-platform-health-review-orchestration' is valid`
- `python3 scripts/validate_agentic_workflows.py` — `Agentic workflow sources and locks match gh-aw v0.85.4.` (recompiles all three workflows and asserts zero generated-file drift against the working tree post-reconcile)
- `python3 scripts/run_test_groups.py --all` — 13/13 groups succeeded, 1165/1165 declared tests discovered and run (`DEV_PLATFORM_TEST_AGGREGATE: {"failed_groups": [], "group_count": 13, ... "outcome": "success", ...}`) — this run includes #165's own merged test additions plus several unrelated sibling changes that landed on `main` in the interim (requirement-preauthoring tooling, PRs #25-#28), confirming no regression from any of that concurrent work either
- `python3 -m unittest tests.test_agentic_workflows -v` — 11/11 tests passed post-reconcile, including the four combined-trigger tests
- `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/platform-health-review.yml'))"` (ad hoc, not a committed test) — parses without error; confirmed the plain `on:` key matches the same unquoted style already used by every other plain workflow in this repository, so GitHub Actions' own parser is unaffected

## Post-merge follow-up (not a pre-archive gap)

- **Live dispatch of `platform-health-review.yml` in `lehard/dev-platform`.** Documented in `tasks.md` and `design.md` as an explicit post-merge follow-up: the workflow must exist on `main` before `workflow_dispatch` recognizes it at all. To be performed once this change merges.
- **`python3 scripts/dogfood_task.py route-claude`** — attempted, refused by the tool itself ("found multiple materialized changes" in this worktree — this change plus the still-present, now-actually-merged-upstream `add-architecture-health-cloud-review` directory pulled in by the sibling merge). Not part of the validation list this task was asked to run; not forced past the refusal. `#165` itself hit and resolved the same routing-refusal pattern before its own successful merge.

## Semantic OpenSpec review (performed manually; no `/opsx:verify` integration available in this environment)

- Outcome vs. success evidence (`proposal.md`): "Each review's own existing advisory/read-only/safe-outputs behavior is provably unchanged" is met — verified directly via the compiled-lock diff (guardrails and safe-outputs byte-identical). "A single manual dispatch, and separately the configured schedule, starts both reviews for the same run" is met by construction (one `workflow_dispatch`/`schedule` on the orchestrator, two `workflow_call` jobs with no `needs:`) but not yet observed live — that is the one open, deliberately-deferred item. "`openspec validate --strict` passes" is met.
- Completeness vs. `design.md`: the design explicitly left the choice between "extend one workflow to invoke the other job" and "keep both as separate workflows sharing one identical schedule/dispatch definition, started together" to implementation time. This change implements a variant of the second shape — trigger consolidation onto one new, shared, non-agentic orchestrator using gh-aw's native `workflow_call` reusable-workflow support — rather than literally duplicating an identical cron on both individual sources, because that would either (a) leave three separate weekly schedules firing (two individual plus one combined) if the per-review schedules were kept, tripling scheduled AI-credit spend and contradicting the design's own stated mitigation against "doubled AI-credit spend per combined run", or (b) still require a separate mechanism to make "a single manual dispatch...starts both" literally true, since two independently-scheduled `workflow_dispatch` triggers cannot be fired as one GitHub Actions action. The chosen shape satisfies both the schedule and dispatch halves of the observable behavior the design requires with one mechanism, keeps each review's engine/tools/safe-outputs declaration textually unchanged, and required no new capability beyond gh-aw's already-built-in `workflow_call` trigger support (confirmed present and correctly wired by the compiler's own generated output, not authored by hand).
- Correctness: the two modified `.md` sources' compiled-lock diffs contain no new `uses:` actions, no new declared secrets beyond what gh-aw's `workflow_call` plumbing itself requires (already-present secrets, now also exposed as optional workflow_call secrets), and no permission escalation (`permissions: {}` unchanged at the top level of both lock files).
- Coherence: `specs/platform-health-review/spec.md`'s four scenarios (scheduled combined run, manually dispatched combined run, one-review-fails-independently, central-pilot-precedes-downstream-rollout) are all addressed by the implemented shape; the fourth (central-pilot) required no code change since `platform-health-review.yml` is authored only in this repository and this task did not touch any managed-rollout/downstream-deployment path.
