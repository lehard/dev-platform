## ADDED Requirements

### Requirement: Scope-claim reconciliation never takes over a sibling worktree

Using authoritative publication state to reconcile a stale scope claim SHALL mutate only bounded coordination metadata. It SHALL NOT clean, reset, switch, delete or otherwise take over the sibling task worktree.

#### Scenario: Stale merged claim is reconciled

- **GIVEN** a sibling managed task is proven terminally merged
- **WHEN** its stale coordination claim is reconciled
- **THEN** scope ownership metadata may be released
- **AND** the sibling worktree content is left untouched

#### Scenario: Sibling worktree is dirty

- **GIVEN** the exact sibling PR is merged but its local worktree still exists with local state
- **WHEN** claim reconciliation runs
- **THEN** the platform does not clean or delete that worktree as part of scope gating
- **AND** worktree cleanup remains governed by its separate lifecycle
