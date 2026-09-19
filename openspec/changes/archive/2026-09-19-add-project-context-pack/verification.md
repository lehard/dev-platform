# Verification

OpenSpec-Verify: PASS
Verification-Method: Equivalent semantic review of the active delta, implementation diff, rendered guidance, and focused behavioral evidence.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- The fresh template contains one bounded `docs/context/README.md` map and no mandatory empty concern files.
- Root guidance and OpenSpec route only reached product, domain, architecture, anti-pattern, and example concerns; `CLAUDE.md` remains a thin adapter and unrelated work does not load the pack.
- `project_context.py inventory` lists only present bounded evidence and never writes or infers facts; `question` formats one question after the agent has identified an unresolved concern. The guide preserves `TODO`/`Unknown` and raw source material stays machine-local.
- Copier and guarded rollout treat `docs/context/` as project-owned, and directory fingerprints cover reviewed file-content changes.

## Checks before archive

- `python3 -m unittest tests.test_project_context tests.test_template_contract tests.test_rollout_recopy` — PASS (84 tests).
- `python3 scripts/render_agents_md_smoke.py` — PASS (3 profiles).
- `python3 -m compileall -q template/scripts scripts` — PASS.
- `DEV_PLATFORM_OPERATOR_CONFIG=/etc/dev-platform/operator.toml python3 scripts/select_checks.py --base origin/main --execute` — PASS before the final bootstrap-helper refinement; archive reruns the selected/full checks against the committed final candidate and writes `automated-checks.json`.
- `openspec validate add-project-context-pack --strict` — PASS before the final bootstrap-helper refinement; archive reruns strict validation against the committed final candidate.
