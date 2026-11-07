# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual walk of both delta scenarios against tests/test_lifecycle_scenarios.py; the tests ran locally and were shown to fail with each source fix reverted; selected checks and strict `openspec validate` ran locally.
Automated-Checks-Evidence: automated-checks.json

## What was checked

- Reconcile conflict with a declared generated file: `ReconcileConflictHintScenario` runs the real `scripts/finish_task.py --reconcile` in a temporary repository with a bare remote and only `git` and `python3` on `PATH`. The conflict names `gen/manifest.txt` and `shared.txt`; during the unfinished merge `--status` exits 0 without a traceback naming reconcile, and a repeated reconcile prints the same steps; every printed step after the manual edit runs as printed; the last reconcile is a no-op, the generated file is regenerated, and the merge commit has the task commit and main as parents.
- Test file without a group: `UngroupedTestStopsPreflightScenario` takes the coverage command from this repository's `preflight_commands`, and `check_project_cheap_gates` refuses a tree with an ungrouped test naming it, then passes once the test is grouped.
- Reverting the regenerate step of the hint made the first test fail (conflict markers committed into the generated file); removing the coverage line from `preflight_commands` made the second fail naming the missing command. Both reverts were restored before commit.
- `tests.test_lifecycle_scenarios` is in the `git_lifecycle` group; `run_test_groups.py --verify-coverage` passes.

## Not checked here

No lifecycle behavior changed. GitHub-dependent branches are not exercised: the scenarios run without the GitHub CLI by design.
