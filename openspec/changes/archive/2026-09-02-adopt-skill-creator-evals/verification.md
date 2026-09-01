# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent-review
Automated-Checks-Evidence: automated-checks.json

The implementation was reviewed against the active proposal, design, delta spec,
and the accepted `engineering-capabilities` specification. It consumes the
existing descriptor id/content hash from #87 and does not create a second
capability registry, provider materialization store, runtime daemon, or
automatic promotion path.

Evidence reviewed:

- `python3 -m compileall -q template/scripts scripts`
- `python3 -m unittest tests.test_capability_manager` (10 tests): lifecycle
  decisions, direct fixture evaluation, positive/hard-negative aggregation,
  objective baseline comparison, unsupported-provider truthfulness, timeout
  separation, descriptor integrity and derived-surface isolation.
- `python3 scripts/capability_evals.py --json run --fixture
  dev-platform/evals/capability-catalog-pilot.json --runtime fixture --runs 3`:
  20 synthetic cases, 3 samples each, 30 triggered and 30 not-triggered
  observations, no incomplete records, and one verified candidate-versus-
  baseline objective comparison.
- `python3 scripts/capability_manager.py --json evaluate capability-catalog
  --fixture dev-platform/evals/capability-catalog-pilot.json --runtime codex
  --runs 3`: all 60 samples remain `unsupported` and are not converted into
  negative triggering evidence.
- `python3 scripts/managed_projects.py validate` and
  `python3 template/scripts/openspec_lifecycle.py check`.

The upstream review is pinned and recorded in
`docs/engineering/engineering-capabilities.md`; no upstream source file is
vendored. Claude/Codex live triggering remains explicitly unsupported until a
supported adapter can provide truthful evidence without nested provider CLI
execution or containment bypass.
