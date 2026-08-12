# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic completeness/correctness/coherence review plus subprocess-isolation and Git-diagnostic regressions with full local platform validation
Automated-Checks-Evidence: automated-checks.json

## Scope reviewed

Reviewed the managed proposal, design, delta requirements, common Git helper,
platform check runner, and all `run_git` call sites that deliberately use
`check=False` or classify a lifecycle blocker.

- **Completeness:** validation commands remove precisely the six inherited
  `GIT_*` variables that bind a child process to a parent repository,
  worktree, index, common directory, or object store, while preserving normal
  environment/tool context. Checked `run_git` failures now include sanitized,
  bounded command, cwd, exit code, stderr and useful stdout.
- **Correctness:** the nested-repository regression proves its commit object
  is not written to the parent object store. `check=False` still returns the
  unchanged inspectable `CompletedProcess`; higher-level freshness handling
  wraps the new detailed Git error in its existing resumable state, and the
  managed-intake non-checkout fallback catches that common error as before.
- **Coherence:** no general subprocess framework was added. Validation-only
  environment isolation is used by the existing selector; operation-specific
  Git environments remain opt-in at `run_git` call sites. Existing task
  freshness, protected-main, and project-harness behavior remains covered by
  lifecycle regressions.

## Automated evidence

- `python3 -m unittest tests.test_platform_common tests.test_select_checks tests.test_task_freshness tests.test_git_lifecycle tests.test_merge_lifecycle_resilience -v` — focused subprocess/check/lifecycle regression coverage passed (the two long lifecycle modules were also run in isolated cases because the interactive command runner has a short output window).
- `python3 -m compileall -q template/scripts scripts` — passed.
- `python3 scripts/managed_projects.py validate` — passed.
- `python3 -m unittest discover -s tests -q` — passed as the complete local unit suite.
- `openspec validate harden-lifecycle-subprocess-boundaries --strict` — passed.
- `python3 template/scripts/openspec_lifecycle.py check` — passed before completion/archive.

`copier` is not installed in this environment (`copier: command not found`),
so a separate render/doctor smoke was not performed. Template/runtime coverage
is included in the complete local suite.
