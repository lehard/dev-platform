# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent semantic review plus automated platform regression
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- **Completeness:** the implementation exposes launched, verified/eligible and
  missing-verification observations; decision-quality sufficiency needs at
  least 15 verified executions and a measured cross-runtime field across that
  eligible sample.
- **Correctness:** Codex `turn.started` and DeepSeek Harness
  `assistant/message` counts now remain runtime-local counters;
  `model_request_count` stays unknown because neither supported contract proves
  its one-to-one semantic. Legacy `request_count` is reported separately.
- **Coherence:** active/archive receipts are looked up through durable
  integration lifecycle roots, while task checkout lookup remains a fallback;
  source and template documentation use the same comparable-vs-local policy.

## Automated checks run before receipt

- `python3 -m unittest tests.test_model_routing tests.test_deepseek_harness_runtime`
- `python3 -m compileall -q template/scripts scripts`
- `python3 -m unittest tests.test_model_routing tests.test_deepseek_harness_runtime tests.test_template_contract`
- `python3 scripts/run_test_groups.py --all --quiet` — 719 tests in 13 groups, all passed.
- `python3 scripts/managed_projects.py validate`
- `openspec validate tighten-execution-baseline-comparability --strict --no-interactive`
- `python3 template/scripts/openspec_lifecycle.py check`

The archive lifecycle reruns the selected applicable checks and records their
machine-readable result in `automated-checks.json`.
