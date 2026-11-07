## Context

`task_reconciliation.reconcile` prints numbered steps on a conflict, built from `[[generated_files]]` of the committed check configuration. Existing tests mock `generated_files` and assert only the text. `lifecycle_preflight.check_project_cheap_gates` runs `[settings].preflight_commands`; its tests use stand-in commands, not this repository's configuration.

## Decisions

**Real entrypoints, local Git.** The reconcile scenario copies `template/scripts` whole into a temporary repository instead of a hand-picked module list, so a new dependency of the lifecycle does not break the fixture. The remote is a bare repository. `PATH` holds only `git` and `python3`, so no GitHub CLI is reachable and the GitHub-dependent branches report themselves unavailable.

**Literal steps.** The scenario parses the numbered steps from the reconcile output and runs each command step as printed. Only step 1, editing the conflicting files, is done by the test. A small generator declared in `[[generated_files]]` stands in for the platform manifest generator: the subject is the hint and reconcile, not a particular generator.

**Configured preflight.** The group scenario takes the coverage command from this repository's `dev-platform/checks.toml` `preflight_commands` and fails explicitly if it is missing, so removing that line fails the test. It runs the command through `check_project_cheap_gates` in a temporary tree that has a test group configuration and the group runner.

**Test groups.** The new test module is registered in a test group of `dev-platform/checks.toml`.

## Risks

The reconcile scenario spawns several Git and Python processes; it stays in seconds. A future change of the hint format breaks the parse; the test then fails naming the output, which is the intended signal.
