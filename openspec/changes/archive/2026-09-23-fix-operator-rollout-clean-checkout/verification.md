# Verification: clean-checkout operator rollout

OpenSpec-Verify: PASS
Verification-Method: Contract review of the active delta against the accepted `platform-rollout` specification, focused regression tests, full platform test groups, strict structural OpenSpec validation, and a real isolated Copier render.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

The defect was reproduced from the v1.5.7 rollout: writing
`.copier-answers.yml` before `copier update` makes Copier reject the target as
dirty. The candidate instead passes `--data operator_integration=true` to both
`copier update` and guarded `copier recopy`; it does not pre-mutate the
checkout. Target-template fingerprints receive the same selected render data.

Executed before archive:

- `python3 -m unittest -v tests.test_rollout_recopy tests.test_rollout_control_plane_regressions tests.test_managed_rollout` — 79 passed, 5 expected historical-baseline skips.
- `python3 scripts/run_test_groups.py --all` — 1,220 discovered/declared tests across 13 groups, all passed.
- `python3 -m compileall -q template/scripts scripts` — passed.
- `python3 scripts/managed_projects.py validate` — passed (3 managed projects).
- `openspec validate fix-operator-rollout-clean-checkout --strict --no-interactive` — passed.
- `python3 template/scripts/openspec_lifecycle.py check` and `git diff --check` — passed.
- An isolated Copier render from a Git archive with `--data operator_integration=true` wrote `operator_integration: true` in `.copier-answers.yml` and rendered only the generic `[operator]` table with `config_env = "DEV_PLATFORM_OPERATOR_CONFIG"`.

Fresh read-only independent review bound to base `2e142ac` and candidate
`e80c4ae` recomputed the request diff SHA and reported no findings for either
spec fidelity or engineering quality. It independently checked the accepted
specification, full candidate diff, Copier 9.17.1 data handling, and the
clean-checkout/fallback regression coverage. Its machine-readable evidence is
in `independent-review-request.json` and `independent-reviews/`.

The archive helper will now generate `automated-checks.json` for the exact
committed candidate before it archives the accepted delta.
