# Semantic verification

OpenSpec-Verify: PASS
Verification-Method: documented manual equivalent review

## Review scope

Reviewed the proposal, platform-lifecycle delta, design and completed task list
against the implementation diff from `origin/main` to this task branch.

- **Completeness:** `start_managed_task.py` performs read-only discovery and
  schema preflight before `start_task`, materializes only through the resulting
  task root, and cleans only task state created by the invocation on failure.
  The standalone importer rejects platform-owned `standard` and `multi-agent`
  integration branches while preserving feature-branch and `light` use.
- **Correctness:** regression tests cover integration-branch refusal, invalid
  package/schema refusal before task creation, task-root-only materialization,
  failure cleanup, and standard feature-branch creation. Generated guidance and
  `platform_doctor.py` require the new entrypoint.
- **Coherence:** the implementation preserves existing package revision and
  provenance handling, uses the existing profile/harness start paths, and does
  not modify the integration checkout during managed materialization.

## Executed checks

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 -m unittest discover -s tests -v`
- `python3 template/scripts/openspec_lifecycle.py check`
- `openspec validate fix-managed-task-intake-isolation --strict --no-interactive`
- `python3 tests/upgrade_smoke.py --profile multi-agent --publish-mode pr`
- Fresh `copier copy --vcs-ref HEAD` render for `multi-agent`, followed by
  `python3 -m compileall -q scripts` and `python3 scripts/platform_doctor.py`

All checks passed. The environment reported only pre-existing compatibility
warnings that the installed OpenSpec and Copier versions are newer than the
platform-tested versions; their required smoke checks completed successfully.
