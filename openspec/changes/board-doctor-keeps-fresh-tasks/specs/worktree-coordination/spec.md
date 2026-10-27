## ADDED Requirements

### Requirement: Board doctor removes only entries whose merge is proven

Board registration SHALL record the registered branch head as the entry's registration base. When a registered branch is an ancestor of `main`, the board doctor SHALL classify the entry as merged only with proof: either the branch moved on from its registration base and its head is not on main's first-parent line since that base, or the exact task PR is reported merged by GitHub. A branch that still points at its registration base has no own commits and SHALL NOT be classified merged. When the merge cannot be proven, because the entry has no registration base, its base is not a known commit, or the moved branch head lies on main's first-parent line (for example after a fast-forward to a newer `main`) or no longer descends from its base, without an exact merged PR, the doctor SHALL classify the entry as degraded with a named reason and SHALL NOT remove it under `--fix`.

#### Scenario: Freshly registered task without commits survives doctor --fix

- **GIVEN** a task registered on the board whose branch was created from the tip of `main`, has no commits and has a clean worktree
- **WHEN** another session runs `agent_board.py doctor --fix`
- **THEN** the entry remains on the board
- **AND** it is not classified `merged-branch`

#### Scenario: Merged and abandoned task is still removed

- **GIVEN** a registered task whose own commits were merged into `main` through a merge commit and whose worktree is clean
- **WHEN** `agent_board.py doctor --fix` runs
- **THEN** the entry is classified `merged-branch` and removed

#### Scenario: Commitless task fast-forwarded over a merge commit survives doctor --fix

- **GIVEN** a registered task without commits whose branch was fast-forwarded to a `main` that gained a merge commit after registration
- **WHEN** `agent_board.py doctor --fix` runs without an exact merged PR for the branch
- **THEN** the entry remains on the board with a named unproven-merge reason

#### Scenario: Unprovable merge is kept with a named reason

- **GIVEN** a registered entry whose branch is an ancestor of `main` but whose merge cannot be proven
- **WHEN** `agent_board.py doctor --fix` runs
- **THEN** the entry remains on the board
- **AND** the doctor output names the reason the merge is unproven
