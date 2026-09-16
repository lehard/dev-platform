# Verification: OpenSpec 1.13.0 compatibility baseline

OpenSpec-Verify: PASS
Verification-Method: equivalent semantic review of the proposal, design, delta requirement, version-contract diff, and exact-version archive/delta regression fixture.
Automated-Checks-Evidence: automated-checks.json

## Exact upstream verification

- OpenSpec `1.13.0` was confirmed as the current stable npm release and verified from an isolated temporary package installation; no OpenSpec sources or generated provider skills were vendored.
- `python3 tests/openspec_1_13_regression.py --openspec-command "<exact OpenSpec 1.13.0 CLI>"` passed. It validates duplicate `ADDED` sections, a fenced literal delta header, retirement of a capability whose final scenario uses wrapped `+` bullets, and apply guidance for a change with no spec deltas.

## Platform verification

- `python3 -m compileall -q template/scripts scripts` passed.
- `python3 scripts/managed_projects.py validate` passed.
- `python3 scripts/run_test_groups.py --all` passed: 863 tests across 13 groups.
- `openspec validate upgrade-openspec-1-13 --strict --no-interactive` passed before archive using the available compatible local CLI; archive below uses the exact 1.13.0 CLI.
- `python3 template/scripts/openspec_lifecycle.py check` passed before the change was marked complete.
- `openspec validate --all --strict --no-interactive` passed with the exact 1.13.0 CLI after replacing the 20 legacy placeholder spec purposes that 1.13 promotes from warnings to strict-validation failures.

## Semantic review

The implementation updates every live 1.6.0 policy pin in the central configuration, template configuration, central/rendered CI and adoption workflow, README, and adoption smoke fixture. It also replaces legacy placeholder Purpose text in every affected live specification and guards that baseline in the template-contract test, so OpenSpec 1.13 strict validation remains reproducible. The independent platform lifecycle guards and semantic verification requirements remain intact. The focused CI fixture is pinned to the exact tested release so protected CI repeats the upstream correctness checks.
