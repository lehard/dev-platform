# Verification: add-ci-guardrails

OpenSpec-Verify: PASS
Verification-Method: manual semantic review of proposal, design, delta scenarios and implementation diff; Ruff 0.11.13 baseline and injected undefined-name check; focused workflow regression tests; full platform test groups; strict OpenSpec CLI validation; rendered Jinja workflow YAML inspection
Automated-Checks-Evidence: automated-checks.json

## Semantic review

The implemented gate uses `python3 -m ruff check scripts template/scripts tests` with pinned Ruff 0.11.13 in central CI and a repository `ruff.toml` selecting E9, F811, F821, F822 and F823. It caught two pre-existing binding defects in `agent_friction.py` and `requirement_intake.py`; both were corrected before enabling the gate. The focused test runs Ruff against a deliberately undefined name and checks the F821 file/line diagnostic. There is no style rewrite or mypy migration.

All authored central workflows have explicit token permissions and bounded job timeouts; existing release and rollout write scopes remain where their GitHub token operations need them. `reconcile-stale-rollouts` now uses read-only GITHUB_TOKEN rights in its reconcile job because downstream writes use a separate GitHub App token. Copier-managed project CI and process-label templates also have explicit rights and deadlines; Jinja render plus YAML parse confirmed the resulting values. Existing projects receive template changes through reviewed Copier updates. The three gh-aw source workflows already declared token permissions and time limits; their generated lock files were not hand-edited.

## Checks actually run

- `python3 -m ruff check scripts template/scripts tests` using Ruff 0.11.13: passed.
- `python3 -m unittest tests.test_ci_guardrails tests.test_template_contract tests.test_ci_trigger_compatibility -q`: 50 passed.
- `python3 -m compileall -q template/scripts scripts`: passed.
- `python3 scripts/managed_projects.py validate`: passed (3 managed projects).
- `python3 scripts/run_test_groups.py --all`: final run passed, 1225 tests in 13 groups, no failed groups. An earlier run failed due to an error in the newly added guardrail test; that test was corrected, its group and the full suite were rerun successfully.
- `python3 template/scripts/openspec_lifecycle.py check`: passed before archive.
- `npx --yes @fission-ai/openspec@1.13.0 validate add-ci-guardrails --strict --no-interactive`: passed.
- Jinja render of both changed downstream workflow templates followed by PyYAML parse and assertions of permissions/timeouts: passed.
- `git diff --check`: passed.

No live GitHub Actions run has yet executed this branch. PR checks remain the clean-environment merge gate after publication.
