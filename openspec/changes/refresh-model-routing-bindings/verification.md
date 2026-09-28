# Verification: refresh model routing bindings

OpenSpec-Verify: PASS
Verification-Method: Equivalent manual semantic review of the authored proposal, design, spec scenario and tasks against the resulting diff, plus deterministic repository checks.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Outcome: superseded Codex bindings are replaced (`routine=gpt-6-luna`, `standard=gpt-6-sol`, `complex=gpt-6-sol`) in the template, the built-in `DEFAULT_MODELS` fallback and the central (machine-local, untracked) `.dev-platform.toml`. Claude aliases are unchanged and resolve to the current Haiku 4.5 / Sonnet 5.5 / Opus 5.5.
- Completeness: the new spec requirement states policy-only change, stable-only eligibility, delivery via release/template update, rollback through the same path and readability of historical records; the operating guide gained the matching "Changing bindings and rollback" section.
- Correctness: tiers, assurance and verification policy are untouched; no routing engine, telemetry store or lifecycle code changed. Model stability and ids (`gpt-6-sol`, `gpt-6-luna`) were taken from OpenAI's public model documentation and release coverage; `gpt-6-terra` does not exist.
- Limitation, stated plainly: the acceptance evidence asked for a comparison of candidate models on representative workloads. That was not performed. `routing-calibration` had 28 verified observations for `gpt-5.6-terra` and none for any candidate, so the bindings were chosen on published stability, cost and tier fit at the user's direction, and evidence for them is the dogfood record accumulated after adoption. The `standard` binding equals `complex` because GPT-6 has no Terra tier; `gpt-6-astra` (about 2.5x Sol cost) was not adopted as the default.
- Coherence: only replaceable policy values, one doc section and one spec requirement changed.

## Checks actually run

- `openspec validate refresh-model-routing-bindings --strict`: valid.
- `python3 scripts/check_docs_links.py`: no problems; `git diff --check`: clean; `python3 -m ruff check scripts template/scripts tests`: passed.
- `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`: passed.
- `python3 scripts/run_test_groups.py --all`: 15/15 groups passed.
- `python3 template/scripts/openspec_lifecycle.py check` reported only the expected pre-archive "all tasks complete but change is active" block; it is re-run after archive.
