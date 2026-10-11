## ADDED Requirements

### Requirement: Required scope gate fails explicitly

When `[capabilities] agent_board` is `true`, the multi-agent scope gate SHALL stop checks and finish with a diagnostic whenever the board path is not configured, the board file is missing, unreadable or invalid, the board has no valid item list, there is no claim for the current worktree and branch, or the `agent_board` module cannot be imported. When the capability is `false` the gate SHALL NOT apply and the portable path SHALL be unchanged. A missing or non-boolean `agent_board` capability SHALL be an error.

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

### Requirement: Protected checks require main_branch

A protected or coordinator check that needs the main branch SHALL read it from platform configuration without a default and SHALL fail explicitly when it is absent or not a non-empty string.

#### Scenario: Missing main_branch

- **GIVEN** platform configuration without `main_branch`
- **WHEN** a protected check or remote fast-forward verification runs
- **THEN** it fails naming `main_branch` and does not assume `main`.

### Requirement: Publication gates do not mask lost records or git failures

The publication queue SHALL fail when the lineage record of a superseded head is missing, and SHALL treat a git ancestry check as three-valued: success is ancestor, exit status 1 is not an ancestor, and any other status is an error naming the command and its output. A malformed trusted candidate record SHALL raise the malformed-marker error naming the comment instead of being skipped. `verify_remote_fast_forward` and `verify_historical_external_advance` SHALL raise on an absent or unreadable `.dev-platform.toml`, a missing `main_branch` or a git failure instead of returning false, and SHALL return false only for a definite negative answer.

#### Scenario: Git failure during preparation

- **GIVEN** `git merge-base --is-ancestor` exits with status 128
- **WHEN** the queue prepares a candidate
- **THEN** it raises with the command and stderr and does not update the branch.

#### Scenario: Malformed trusted record

- **GIVEN** a trusted candidate comment whose payload fails validation
- **WHEN** the admission record is read
- **THEN** the malformed-marker error names that comment and the admission time is not taken from a later record.

### Requirement: Verification and integration prerequisites are enforced

An invalid `DEV_PLATFORM_TEST_JOBS` SHALL be an error naming the value. Serialized integration SHALL raise on a platform without `fcntl` instead of running unlocked, and the shared-workspace module SHALL be imported without a no-op stand-in.

#### Scenario: Invalid job count

- **GIVEN** `DEV_PLATFORM_TEST_JOBS=abc`
- **WHEN** the test runner resolves parallelism
- **THEN** it fails naming the variable and the value.

### Requirement: Fail-open decisions are inventoried

Every examined fail-open site in the publication and verification gates SHALL have a recorded decision: fixed to an explicit error, or kept only by an explicit owner decision with the location of that decision.

#### Scenario: Kept site

- **GIVEN** a site that is not changed
- **WHEN** the inventory is read
- **THEN** it names the owner decision and where it is recorded.
