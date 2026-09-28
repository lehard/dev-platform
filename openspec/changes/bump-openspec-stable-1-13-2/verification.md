# Verification receipt

OpenSpec-Verify: PASS
Verification-Method: documented semantic OpenSpec review plus exact-CLI regression runs against OpenSpec 1.13.0 and 1.13.2 and automated platform checks
Automated-Checks-Evidence: automated-checks.json

## Upstream confirmation

Re-confirmed on 2026-09-28 immediately before editing: npm
`@fission-ai/openspec` dist-tag `latest` is `1.13.2` (published
2026-09-23) and the `Fission-AI/OpenSpec` GitHub release `v1.13.2` is marked
"Latest". The only other dist-tags are `beta` = `1.6.0-beta.1` and `next` =
`0.3.0`, both older; no prerelease is adopted.

## Semantic review

- **Pin agreement.** Every recorded copy of the tested version moved from
  `1.13.0` to `1.13.2`: `template/.dev-platform.toml.jinja`
  (`min_version`/`tested_version`), `.github/workflows/ci.yml` (strict
  validate and regression command), `.github/workflows/adopt-project.yml`,
  `template/.github/workflows/dev-platform.yml.jinja`, `README.md`,
  `tests/test_template_contract.py` and
  `tests/project_harness_adoption_smoke.py`. `git grep 1.13.0` outside
  archived history and this change's own artifacts finds nothing. The
  machine-local, git-excluded `.dev-platform.toml` of this worktree was
  updated too so the contract test exercises it; it is not part of the
  committed contract.
- **Focused regressions for the motivating fixes.**
  `tests/openspec_1_13_regression.py` gained fixtures for: case-only duplicate
  `ADDED` refusal; unpaired `RENAMED` refusal at strict validation and
  archive; `[~]`/`+`/numbered task markers counted as open work with
  `taskTrackingConfigured`; exact `RENAMED` + `REMOVED` archive; and the
  generated verify workflow's advisory framing, `Not verified` category and
  inverted REMOVED / baseline RENAMED checks (skipped-verification and
  removed/renamed-requirement cases).
- **Regression proof.** Against exact local installs: the extended script
  passes on `1.13.2`. Run fixture-by-fixture in fresh projects on `1.13.0`,
  every new regression fixture fails (case-duplicate archived, unpaired
  rename accepted by strict validate and applied by archive, task progress
  `1/1 all_done` instead of `1/4`, verify workflow lacks the advisory and
  REMOVED/RENAMED guidance). The paired `RENAMED`+`REMOVED` archive fixture
  passes on both versions and is a positive control, not a regression proof.
  The pre-existing `1.13.0` fixtures still pass on `1.13.2`.
- **Not independently pinned.** Scenario-less requirement rejection (`1.13.1`)
  was probed in change deltas and main specs, strict and non-strict: both
  versions already reject it, so there is no behavior difference to pin.
  Schema-aware task progress in agent-driven archive (`1.13.2`) is generated
  archive-skill guidance; its CLI basis (`instructions apply` progress with
  `taskTrackingConfigured`) is covered by the task-marker fixture only.
- **Independent child pass.** The routed native Claude child
  (`ac049bb691a7123da`) re-ran the pin grep, both exact-CLI regressions,
  the template contract tests and ruff, and reviewed each fixture in
  isolation; it found one stale `1.13.0` docstring mention (fixed) and the
  positive-control/unpinned wording corrected above.
- **Repository compatibility.** `openspec@1.13.2 validate --all --strict
  --no-interactive` on this repository: 36 passed, 0 failed.
- **Platform guard decision.** No platform guard was removed or weakened. The
  `1.13.2` verify workflow states "Verification is advisory" and "Archive
  retains its own checks", so equivalence with the platform's PASS receipt,
  automated-checks evidence, routing gate and lifecycle archive is not
  proven; they are retained as the requirement demands. The platform's own
  `openspec_lifecycle.task_state` still recognises only `- [ ]`/`- [x]`
  markers — the gap upstream fixed in `1.13.1` — and is recorded as a
  separate follow-up rather than folded into this bump.
- **Representative managed path.** This change is itself a managed child
  (materialize -> start -> route -> implement -> archive -> publish); its
  archive runs with exact `openspec` `1.13.2` first on `PATH`, so the
  lifecycle helper's `validate`, `archive` and post-archive
  `validate --all --strict` exercise the new pin.
- **Rollback.** Reverting the pin is an ordinary platform release; earlier
  immutable release tags keep `1.13.0` for downstream projects that pin them.

## Checks run

- `python3 -m compileall -q template/scripts scripts`: pass.
- `python3 scripts/managed_projects.py validate`: OK.
- `python3 -m unittest tests.test_template_contract`: 44 tests OK.
- `python3 -m ruff check tests/openspec_1_13_regression.py`: pass.
- `DEV_PLATFORM_TEST_JOBS=3 python3 scripts/run_test_groups.py --all`: success, 14 groups, 1408 tests; archive re-runs selected checks into
  `automated-checks.json` produced by the lifecycle archive helper.

## Limitation

`tests/project_harness_adoption_smoke.py` could not complete locally: Copier's
internal temporary clone fails in dunamai with `fatal: revision walk setup
failed` against this shared multi-worktree object store, the same
pre-existing environment limitation recorded in the archived Copier 9.18.2
bump, unrelated to this change's content. Platform CI runs this smoke
(`ci.yml`), and its OpenSpec expectation is also asserted by
`test_template_contract`.
