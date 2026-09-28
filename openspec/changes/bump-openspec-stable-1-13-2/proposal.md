# Proposal: Bump the tested OpenSpec version to the current stable release

## Why

The platform's minimum/tested OpenSpec CLI is `1.13.0`. Confirmed against the
primary upstream sources on 2026-09-28 (npm `@fission-ai/openspec` dist-tag
`latest` and the `Fission-AI/OpenSpec` GitHub release marked "Latest"), current
stable is `1.13.2` (2026-09-23); the only newer-numbered tags are older
prereleases (`beta` = `1.6.0-beta.1`), so no prerelease is involved.

The releases after `1.13.0` fix correctness-sensitive behavior the platform
relies on:

- `1.13.1`: archive refuses a requirement name that differs from an existing
  one only in case, and a `RENAMED` section whose `FROM:`/`TO:` lines do not
  pair; validation rejects scenario-less requirements; task progress counts
  `+`, `1.` and `1)` markers and treats unknown markers such as `[~]` as
  unfinished.
- `1.13.2`: `/opsx:verify` no longer reports skipped checks as passing, checks
  removed requirements for absence and renamed requirements against their
  original behavior; agent-driven archive uses schema-aware task progress.

This is ordinary dependency maintenance through the existing pin/regression
surfaces, governed by the existing "OpenSpec stable-version upgrades preserve
lifecycle correctness" requirement.

## What changes

- Raise the recorded tested OpenSpec version from `1.13.0` to `1.13.2`
  everywhere it is recorded: `template/.dev-platform.toml.jinja`
  (`[tools.openspec]` `min_version`/`tested_version`),
  `template/.github/workflows/dev-platform.yml.jinja`,
  `.github/workflows/ci.yml`, `.github/workflows/adopt-project.yml`,
  `README.md`, `tests/test_template_contract.py`, and
  `tests/project_harness_adoption_smoke.py`.
- Extend the exact-CLI regression `tests/openspec_1_13_regression.py` with
  focused fixtures for the motivating upstream fixes (case-only duplicate,
  unpaired `RENAMED`, `RENAMED`+`REMOVED` archive, task-marker progress, and
  generated verify-workflow removed/renamed/not-verified semantics). The new
  fixtures fail against `1.13.0` and pass against `1.13.2`.
- Retain all platform semantic verification, receipt, automated-evidence,
  routing and archive gates: the `1.13.2` verify workflow itself declares
  verification advisory and defers to archive's own checks, so no platform
  guard is proven redundant.

## Spec delta

`MODIFIED` the `openspec-authoring` requirement "OpenSpec stable-version
upgrades preserve lifecycle correctness" to make explicit that every recorded
copy of the tested version moves together and that focused regressions for the
adopted release's correctness fixes stay in the exact-CLI regression suite.

## Non-goals / exclusions

- Do not adopt a prerelease/beta/RC as the production default.
- Do not build a new verification/archive subsystem.
- Do not remove platform-level guarantees based only on release notes.

## Rollback

Rollback to `1.13.0` is an ordinary platform release that reverts the pin;
downstream projects keep consuming immutable release refs, so an earlier
release tag continues to pin `1.13.0` unchanged.

## Success criteria / verification evidence

- No recorded copy of `1.13.0` remains outside archived history.
- `tests/openspec_1_13_regression.py` passes against exact `1.13.2` and its
  new fixtures demonstrably fail against `1.13.0`.
- `npx @fission-ai/openspec@1.13.2 validate --all --strict --no-interactive`
  passes on this repository.
- `python3 -m compileall -q template/scripts scripts`,
  `python3 scripts/managed_projects.py validate`,
  `python3 scripts/run_test_groups.py --all` and
  `python3 template/scripts/openspec_lifecycle.py check` pass.
- This managed change itself (materialize -> validate -> verify -> archive ->
  publish) is the representative managed path run with the new pin.
