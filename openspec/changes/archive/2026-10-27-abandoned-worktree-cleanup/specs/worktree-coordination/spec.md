## ADDED Requirements

### Requirement: An abandoned candidate worktree is removed only with exact closed-PR proof

Worktree cleanup SHALL provide an explicit operation that removes one exact task worktree, identified by path, branch and head, together with its local branch and its exact agent-board claim, when the candidate was abandoned. Abandonment SHALL be proven from GitHub: a pull request of that branch into main whose head is exactly that head is closed without merge, and no merged pull request with that head and no open pull request exists for the branch. The head SHALL NOT be contained in main. The worktree SHALL be registered with that branch and head, inside the managed worktree directory, unlocked, clean and not in use. Any unmet condition, unavailable GitHub evidence or ambiguous board claim SHALL refuse with a named reason and a non-zero exit, removing nothing. Scan and global cleanup SHALL NOT infer abandonment, and the board doctor's merge-proof rules are unchanged.

#### Scenario: Closed exact PR

- **GIVEN** a clean, idle worktree whose exact head's PR into main was closed without merge
- **WHEN** the operator runs the abandoned cleanup for that exact worktree, branch and head
- **THEN** the worktree, its local branch and its exact board claim are removed
- **AND** the result is `completed` with exit 0

#### Scenario: PR open, merged or missing

- **WHEN** the branch has an open PR, the exact head has a merged PR, or no closed PR has exactly that head
- **THEN** cleanup refuses naming the reason and removes nothing

#### Scenario: Unsafe local state

- **WHEN** the worktree is dirty, in use, locked, outside the managed directory, its registered branch or head differs from the target, or a board claim names it with another branch
- **THEN** cleanup refuses naming the reason and removes nothing

#### Scenario: GitHub evidence unavailable

- **WHEN** GitHub authentication or the PR list is unavailable
- **THEN** cleanup refuses and removes nothing
