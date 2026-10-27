## ADDED Requirements

### Requirement: Select checks and finish keep no hidden fallbacks

`select_checks.py` SHALL import the scope-conflict Project status helper directly and SHALL NOT substitute a no-op when it cannot be imported. `finish` SHALL run the current-candidate private-reference guard on the proposed pull-request title and body whenever private lineage is enabled; with private lineage enabled a missing guard script SHALL be a completion blocker naming the script, and with private lineage disabled the guard SHALL NOT apply by configuration rather than by the absence of a file. Releasing the agent-board claim after publication SHALL fail with a diagnostic naming the board when the board is unreadable, not a JSON object, or has a non-list item list, and SHALL fail naming the claim and the rerun command when the release command fails, in every finish path. An absent board file or a board without an item for the worktree SHALL be the inventoried legitimate absence "no claim to release".

#### Scenario: Scope-conflict helper missing

- **WHEN** `managed_project_status` cannot be imported by `select_checks.py`
- **THEN** the import fails naming the module and no stub hides the scope-conflict status

#### Scenario: Private lineage enabled without the guard

- **GIVEN** private lineage is enabled and `scripts/check_private_backlog_refs.py` is absent
- **WHEN** finish evaluates completion blockers
- **THEN** it stops naming the missing guard and publishes nothing

#### Scenario: Private lineage disabled

- **GIVEN** private lineage is not enabled
- **WHEN** finish evaluates completion blockers
- **THEN** the private-reference guard does not apply and is not looked up

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
