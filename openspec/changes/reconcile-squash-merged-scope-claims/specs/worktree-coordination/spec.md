## ADDED Requirements

### Requirement: Scope claims use authoritative managed completion state when squash merge removes branch ancestry

Before a managed sibling claim blocks hard scope gating, the platform SHALL be able to reconcile that claim against the exact task's authoritative GitHub publication state. An exact merged PR SHALL be sufficient evidence that the sibling is completed for scope ownership even when squash merge means the feature branch is not an ancestor of `main`.

#### Scenario: Exact sibling PR was squash-merged

- **GIVEN** an active board claim belongs to an exact managed sibling task
- **AND** that task's exact PR is reported `MERGED` by GitHub
- **AND** the feature branch is not an ancestor of `main` because the repository used squash merge
- **WHEN** another task evaluates hard scope overlap
- **THEN** the completed sibling claim does not block the new task
- **AND** the decision does not require branch ancestry to reconstruct the squash merge

#### Scenario: Publication state is ambiguous or unavailable

- **WHEN** the platform cannot prove the exact sibling PR is merged
- **THEN** it retains the existing active claim
- **AND** hard overlap remains fail-closed
