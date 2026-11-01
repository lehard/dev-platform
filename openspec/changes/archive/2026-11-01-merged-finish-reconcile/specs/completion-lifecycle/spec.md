## ADDED Requirements

### Requirement: Finish of a merged PR reconciles before any developer handoff

When the exact PR of the task branch is merged, finish SHALL run the post-merge reconcile path before any managed-candidate developer handoff, and the board scope-claim condition SHALL NOT apply to it. An unreadable PR state SHALL stop finish explicitly.

#### Scenario: Merged PR at a pre-finalize head

- **GIVEN** a task worktree at a pre-finalize head whose exact PR is merged and whose board claim was released
- **WHEN** finish runs
- **THEN** it reconciles delivery without a scope claim and starts no developer handoff
