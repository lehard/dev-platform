# Verification

OpenSpec-Verify: PASS  
Verification-Method: equivalent semantic review plus deterministic routing/containment tests
Automated-Checks-Evidence: automated-checks.json

## What was checked

- Reviewed every added `model-routing` requirement against
  `template/scripts/model_routing.py`, generated agent guidance, the
  replaceable `[model_routing]` policy, and the new template delivery paths.
  The implementation records routing only after materialized managed OpenSpec,
  supports routine/standard/complex, preserves a strong complex parent,
  carries bounded task context, and records standard-to-complex escalation.
- Reviewed both modified `platform-delegation` requirements against
  `delegation_containment.py` and `delegated_write_guard.py`. Codex native
  `workspace-write` is the prevention layer; the renamed observer preserves
  assignment validation, content-aware post-check and friction recording.
  Claude's emitted agent definition requires `isolation: worktree`, with the
  parent-side post-check retained as defense in depth. Unproven Codex native
  containment fails with an actionable retain-on-parent/fallback outcome.
- Exercised the actual managed task routing preflight in this worktree:
  `prepare --provider codex --profile complex` recorded the cross-cutting
  classification and configured strong model, and `postcheck` returned clean.
- `python3 -m compileall -q template/scripts scripts` passed.
- `python3 scripts/managed_projects.py validate` passed.
- The authoritative archive precheck ran the configured normal full suite:
  `python3 -m unittest discover -s tests -v` passed in 261.94 seconds. Its
  exact command/outcome receipt is `automated-checks.json`. A prior test-only
  no-`gh` run also exercised the local pending-fallback without creating
  GitHub process-friction issues from unit fixtures. Focused routing,
  containment and template-contract tests passed explicitly (30 tests).
- `openspec validate adopt-native-model-routing --strict --no-interactive`
  passed.

## Copier note

`copier` is not installed in this environment, so no rendered-project smoke
was claimed. Template delivery is covered structurally by `test_template_contract`
and `tests/upgrade_smoke.py` now asserts that Copier updates materialize both
`scripts/model_routing.py` and `docs/engineering/model-routing.md`. A host
with Copier should run the normal three-profile upgrade smoke before adopting
this source revision downstream.
