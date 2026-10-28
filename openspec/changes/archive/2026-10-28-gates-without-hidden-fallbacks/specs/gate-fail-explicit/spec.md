## ADDED Requirements

### Requirement: Selected checks use an explicit or task-derived base

`select_checks.py` SHALL derive the changed-file set only from `--changed-file`, from an explicit `--base`, or, on a named task branch other than the configured main branch, from `origin/<main_branch>`, and SHALL print the base it used. It SHALL NOT fall back to the previous commit. Without `--base` or `--changed-file` on the main branch or a detached HEAD it SHALL fail before any check runs, naming both options. A failing `git diff` SHALL fail naming the command. The central wrapper SHALL resolve the base by the same rule before running the selector.

#### Scenario: Task branch without --base

- **GIVEN** the current branch is a task branch
- **WHEN** `select_checks.py` runs without `--base` and `--changed-file`
- **THEN** it compares the branch with `origin/<main_branch>` and prints that base

#### Scenario: Main branch without --base

- **GIVEN** the current branch is the main branch or HEAD is detached
- **WHEN** `select_checks.py` runs without `--base` and `--changed-file`
- **THEN** it fails before any check runs, naming `--base` and `--changed-file`

#### Scenario: Git diff fails

- **GIVEN** `--base` names a ref that does not exist
- **WHEN** `select_checks.py` computes the changed files
- **THEN** it fails naming the `git diff` command and git's message
