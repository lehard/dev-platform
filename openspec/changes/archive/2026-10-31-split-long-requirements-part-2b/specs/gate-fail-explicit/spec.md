## MODIFIED Requirements

### Requirement: Required scope gate fails explicitly

When `[capabilities] agent_board` is `true`, the multi-agent scope gate SHALL stop checks and finish with a diagnostic whenever the board path is not configured, the board file is missing, unreadable or invalid, the board has no valid item list, there is no claim for the current worktree and branch, or the `agent_board` module cannot be imported.

#### Scenario: Corrupt board with the capability on

- **GIVEN** `agent_board = true` and a board file that is not valid JSON
- **WHEN** the scope gate runs before validation or publication
- **THEN** it fails naming the unreadable board and does not report no conflicts.

#### Scenario: Capability off

- **GIVEN** `agent_board = false` and no board file
- **WHEN** the scope gate runs
- **THEN** it does not block and the portable path runs.

#### Scenario: Disposable checkout declared not applicable

- **GIVEN** `agent_board = true` and a checkout with no machine-local board (a CI run or a coordinator proven-base or contribution-base run)
- **WHEN** `select_checks.py` runs with `--scope-gate not-applicable` or with `--proven-base` or `--contribution-base`
- **THEN** it prints `Scope gate not applicable: <reason>` and does not fail on the missing board
- **AND** without that explicit declaration (`--scope-gate enforce`, the default) the missing board still stops the run
- **AND** `--scope-gate not-applicable` is refused with an explicit error in a linked task worktree or a checkout holding `.managed-task-state.json`, and accepted only in a plain checkout.

### Requirement: Publication gates do not mask lost records or git failures

The publication queue SHALL fail when the lineage record of a superseded head is missing.

#### Scenario: Git failure during preparation

- **GIVEN** `git merge-base --is-ancestor` exits with status 128
- **WHEN** the queue prepares a candidate
- **THEN** it raises with the command and stderr and does not update the branch.

#### Scenario: Malformed trusted record

- **GIVEN** a trusted candidate comment whose payload fails validation
- **WHEN** the admission record is read
- **THEN** `MalformedMarkerError` names that comment and the admission time is not taken from a later record.

### Requirement: Fail-open decisions are inventoried

Every examined fail-open site in the publication and verification gates SHALL be classified in the design inventory into exactly one of two categories. FIXED: absence or corruption is now an explicit error. LEGITIMATE ABSENCE (not fail-open): the state is a normal part of the lifecycle, nothing is substituted, the code has an explicit `None` branch, and the inventory records a per-site justification of why absence there is not a lost record. There SHALL be no other category.

#### Scenario: Legitimate absence site

- **GIVEN** a site that still handles an absent record without raising
- **WHEN** the inventory is read
- **THEN** it names the category "legitimate absence" and states why absence there is a normal lifecycle state and not a lost record
- **AND** the code at that site has an explicit `None` branch and substitutes nothing.

#### Scenario: Fixed site

- **GIVEN** a site where absence or corruption would hide a lost record
- **WHEN** the inventory is read
- **THEN** it names the category "fixed" and the explicit error raised.

### Requirement: Select checks and finish keep no hidden fallbacks for scope-conflict status and board release

`select_checks.py` SHALL import the scope-conflict Project status helper directly and SHALL NOT substitute a no-op when it cannot be imported.

#### Scenario: Scope-conflict helper missing

- **WHEN** `managed_project_status` cannot be imported by `select_checks.py`
- **THEN** the import fails naming the module and no stub hides the scope-conflict status

#### Scenario: Corrupt agent board at release

- **GIVEN** a multi-agent finish whose agent board file is not valid JSON
- **WHEN** finish releases the board claim
- **THEN** it fails naming the board path instead of treating the worktree as unclaimed

#### Scenario: Failed claim release

- **WHEN** `agent_board.py finish` for the worktree's claim exits non-zero in any finish path
- **THEN** finish fails naming the claim and the rerun command

#### Scenario: No claim to release

- **WHEN** the board file is absent or has no item for the worktree
- **THEN** finish releases nothing and continues

### Requirement: Selected checks use an explicit or task-derived base

`select_checks.py` SHALL derive the changed-file set only from `--changed-file`, from an explicit `--base`, or, on a named task branch other than the configured main branch, from `origin/<main_branch>`, and SHALL print the base it used. It SHALL NOT fall back to the previous commit.

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

## ADDED Requirements

### Requirement: The scope gate does not apply when the agent board capability is off

When the `[capabilities] agent_board` capability is `false` the multi-agent scope gate SHALL NOT apply and the portable path SHALL be unchanged.

#### Scenario: Agent board capability is false

- **GIVEN** `agent_board = false`
- **WHEN** checks or finish run
- **THEN** the multi-agent scope gate does not apply
- **AND** the portable path is unchanged

### Requirement: A missing or non-boolean agent board capability is an error

A missing or non-boolean `agent_board` capability SHALL be an error.

#### Scenario: Agent board capability is missing or not a boolean

- **GIVEN** platform configuration without `[capabilities] agent_board` or with a non-boolean value
- **WHEN** the multi-agent scope gate configuration is read
- **THEN** it is an error

### Requirement: The publication queue treats a git ancestry check as three-valued

The publication queue SHALL treat a git ancestry check as three-valued: success is ancestor, exit status 1 is not an ancestor, and any other status is an error naming the command and its output.

#### Scenario: Ancestry check exits with another status

- **WHEN** a git ancestry check in the publication queue exits with a status other than success or 1
- **THEN** it is an error naming the command and its output
- **AND** success means ancestor and exit status 1 means not an ancestor

### Requirement: A malformed trusted candidate record raises MalformedMarkerError

A malformed trusted candidate record SHALL raise `MalformedMarkerError` (a new error class in `candidate_lifecycle.py`) naming the comment instead of being skipped.

#### Scenario: Trusted candidate record is malformed

- **WHEN** a trusted candidate record is malformed
- **THEN** `MalformedMarkerError` is raised naming the comment
- **AND** the record is not skipped

### Requirement: The queue surfaces a malformed trusted candidate record as an explicit outcome

The publication queue and integration contour SHALL surface a `MalformedMarkerError` for a malformed trusted candidate record as an explicit blocked or `QueueError` outcome naming the comment, never as a bare exception.

#### Scenario: Queue meets a malformed trusted candidate record

- **WHEN** `MalformedMarkerError` is raised for a malformed trusted candidate record in the publication queue or integration contour
- **THEN** the outcome is an explicit blocked or `QueueError` outcome naming the comment
- **AND** it is not a bare exception

### Requirement: Remote fast-forward verification raises on missing config or git failure

`verify_remote_fast_forward` and `verify_historical_external_advance` SHALL raise on an absent or unreadable `.dev-platform.toml`, a missing `main_branch` or a git failure instead of returning false, and SHALL return false only for a definite negative answer.

#### Scenario: Configuration or git fails during verification

- **WHEN** `verify_remote_fast_forward` or `verify_historical_external_advance` meets an absent or unreadable `.dev-platform.toml`, a missing `main_branch` or a git failure
- **THEN** it raises instead of returning false

#### Scenario: Definite negative answer

- **WHEN** the verification has a definite negative answer
- **THEN** it returns false

### Requirement: A fail-open site whose absence would mean a lost record is FIXED

In the design inventory of examined fail-open sites in the publication and verification gates, a site where absence would mean a lost record SHALL be FIXED.

#### Scenario: Absence would lose a record

- **WHEN** absence at an examined fail-open site in the publication and verification gates would mean a lost record
- **THEN** the design inventory classifies the site FIXED

### Requirement: Board release fails on a corrupt agent board

Releasing the agent-board claim after publication SHALL fail with a diagnostic naming the board when the board is unreadable, not a JSON object, or has a non-list item list, in every finish path.

#### Scenario: Agent board is corrupt at claim release

- **WHEN** the agent board is unreadable, not a JSON object, or has a non-list item list when a finish path releases the claim after publication
- **THEN** the release fails with a diagnostic naming the board

### Requirement: Board release fails when the release command fails

Releasing the agent-board claim after publication SHALL fail naming the claim and the rerun command when the release command fails, in every finish path.

#### Scenario: Claim release command fails

- **WHEN** the release command fails when a finish path releases the agent-board claim after publication
- **THEN** it fails naming the claim and the rerun command

### Requirement: No agent-board claim to release is a legitimate absence

When releasing the agent-board claim after publication, an absent board file or a board without an item for the worktree SHALL be the inventoried legitimate absence "no claim to release".

#### Scenario: Nothing to release

- **WHEN** the agent board file is absent or has no item for the worktree when the claim is released after publication
- **THEN** it is the inventoried legitimate absence "no claim to release"

### Requirement: Selected checks fail without a base on main or a detached HEAD

Without `--base` or `--changed-file` on the main branch or a detached HEAD `select_checks.py` SHALL fail before any check runs, naming both options.

#### Scenario: No base on main or detached HEAD

- **WHEN** `select_checks.py` runs without `--base` or `--changed-file` on the main branch or a detached HEAD
- **THEN** it fails before any check runs, naming both options

### Requirement: Selected checks fail when git diff fails

When `select_checks.py` derives the changed-file set, a failing `git diff` SHALL fail naming the command.

#### Scenario: Changed-file git diff fails

- **WHEN** `git diff` fails while `select_checks.py` derives the changed-file set
- **THEN** it fails naming the command

### Requirement: The central wrapper resolves the selected-checks base by the same rule

The central wrapper SHALL resolve the base by the same rule as `select_checks.py` (from `--changed-file`, from an explicit `--base`, or, on a named task branch other than the configured main branch, from `origin/<main_branch>`) before running the selector.

#### Scenario: Central wrapper runs the selector

- **WHEN** the central wrapper runs `select_checks.py`
- **THEN** it first resolves the base by the same rule as `select_checks.py`
