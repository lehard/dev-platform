# Verification: add-architecture-health-cloud-review

OpenSpec-Verify: PASS

Verification-Method: local deterministic validation (compile with the pinned gh-aw release, structural/unit tests, OpenSpec structural + hygiene validation, manual semantic review against proposal/design/spec); live workflow_dispatch confirmation deferred to a documented post-merge follow-up (see below and design.md's "Verification note")

Every aspect of this change that can be verified before the workflow file
exists on the default branch has been verified and passed. One item —
confirming a live `workflow_dispatch` run of the brand-new
`architecture-health-review` workflow in `lehard/dev-platform` — is a
documented post-merge follow-up, not something already run: GitHub Actions
does not recognize a `workflow_dispatch`-triggerable workflow, and refuses a
dispatch request for it (`HTTP 404: workflow ... not found on the default
branch`), until that workflow's file exists on the default branch. This is a
structural platform constraint (see `design.md`), not a gap in this
verification pass, and it is recorded here explicitly rather than implied or
omitted.

## Automated checks actually run (all passed)

- `python3 -m compileall -q template/scripts scripts` — exit 0
- `python3 scripts/managed_projects.py validate` — `Managed project registry: OK (3 managed, 0 candidate, 0 excluded)`
- `python3 scripts/run_test_groups.py --all` — 13/13 groups succeeded (`DEV_PLATFORM_TEST_AGGREGATE: {"failed_groups": [], "group_count": 13, ... "outcome": "success", ...}`)
- `python3 template/scripts/openspec_lifecycle.py check` — `OpenSpec lifecycle hygiene: OK`
- `openspec validate add-architecture-health-cloud-review --strict --no-interactive` — `Change 'add-architecture-health-cloud-review' is valid`
- `python3 scripts/validate_agentic_workflows.py` — `Agentic workflow sources and locks match gh-aw v0.85.4.` (recompiles all three workflow sources, including the new `architecture-health-review`, and asserts zero generated-file drift)
- `python3 -m unittest tests.test_agentic_workflows -v` — 7/7 tests passed, including the new `architecture-health-review` entries added to `SOURCES`
- `gh aw compile architecture-health-review --strict --validate --approve` — compiled cleanly to `.github/workflows/architecture-health-review.lock.yml`; manifest secrets (`CODEX_API_KEY`, `COPILOT_GITHUB_TOKEN`, `GH_AW_GITHUB_MCP_SERVER_TOKEN`, `GH_AW_GITHUB_TOKEN`, `GITHUB_TOKEN`, `OPENAI_API_KEY`), pinned actions, and pinned container images are byte-identical in shape/pinning-mode to the already-accepted `weekly-process-backlog-review.lock.yml`
- `python3 scripts/dogfood_task.py route-claude --rationale "..."` — confirmed the authored `R2` balanced tier; no new hard trigger found during implementation

Automated-Checks-Evidence: automated-checks.json

## Semantic OpenSpec review (performed manually; no `/opsx:verify` integration available in this environment)

- **Outcome vs. success evidence**: `proposal.md`'s three success-evidence bullets are met by the artifacts as authored. The bullet requiring the workflow to be "triggered manually (`workflow_dispatch`) ... in `lehard/dev-platform`, without any local computer running" is met structurally (the compiled workflow correctly declares and would accept a `workflow_dispatch` trigger once on `main`) and will be empirically confirmed by the documented post-merge follow-up in `tasks.md`.
- **Completeness**: the workflow source covers schedule + `workflow_dispatch` triggers, read-only `repos` toolset, bounded `create-issue` safe output, and explicit `timeout-minutes`/`max-ai-credits`/`max-daily-ai-credits`/`max-turns` guardrails mirroring `weekly-process-backlog-review`'s conservative bounds, per `design.md`.
- **Correctness**: the compiled lock file's `gh-aw-manifest` shows no new secrets or actions beyond what `weekly-process-backlog-review.lock.yml` already uses; `gh aw compile --approve` was required only because this is a first-time compile of a new file (no prior committed manifest to diff against), not because of any actually-new secret/action.
- **Coherence**: the spec delta in `specs/architecture-health/spec.md` (authored before implementation started) already states all four required scenarios (scheduled run, manual dispatch, guardrail stop, central-pilot-first) and needed no wording changes. `tasks.md` and `design.md` were updated to accurately describe the post-merge deferral of the live-dispatch confirmation, so all four artifacts (proposal/design/spec/tasks) remain internally consistent with what was actually built and verified.

## Post-merge follow-up (tracked, not a blocker for this change)

After this change merges to `main`, manually dispatch
`architecture-health-review.lock.yml` in `lehard/dev-platform` and confirm:
it completes within its declared guardrails (`timeout-minutes: 10`,
`max-ai-credits: 100`), and it produces exactly one
`[architecture-health]`-prefixed advisory Issue with no other repository,
PR, or managed-task mutation. Record the result as ordinary process
evidence.
