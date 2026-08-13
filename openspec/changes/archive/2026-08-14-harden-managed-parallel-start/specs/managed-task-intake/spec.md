## ADDED Requirements

### Requirement: Managed-start mutation is guarded by a persisted per-change transaction

Before any worktree or agent-board mutation for a managed start in a multi-agent-profile checkout, the platform SHALL persist a machine-local, per-change start transaction identifying the exact package (source issue, target repository, change, package revision, resolved branch/worktree). The transaction SHALL serialize only retries of the same managed change; it SHALL NOT block or interact with the start of a different managed change.

#### Scenario: Transaction precedes workspace mutation

- **WHEN** a managed start begins for change A in a multi-agent-profile checkout
- **THEN** a transaction record for change A is persisted before any worktree or board mutation occurs
- **AND** the transaction is retired only after the start completes successfully

#### Scenario: Unrelated managed changes start independently

- **GIVEN** a start transaction is active for change A
- **WHEN** a start begins for unrelated change B
- **THEN** change B's start proceeds without waiting on or being blocked by change A's transaction

#### Scenario: Interrupted start preserves its retry receipt

- **WHEN** a managed start for change A is interrupted before completion
- **THEN** change A's transaction record remains on disk
- **AND** a subsequent start for change A uses it to resume recovery rather than starting from an unrecorded state

### Requirement: Incomplete managed-start recovery is fenced to exact task identity

When a managed start finds transaction state without matching canonical OpenSpec provenance, the platform SHALL treat this as bounded incomplete creation state for that exact task and MAY recover it. Recovery SHALL act only on the worktree, branch and agent-board entry named by that task's own transaction, and SHALL refuse when the candidate has commits not reachable from the main branch, dirty paths not owned by that task, task-local state naming a different source issue or change, an ambiguous board match, or cannot be proven to be an exact registered Git worktree. Recovery SHALL NOT perform global worktree or board pruning.

#### Scenario: Exact partial task is recovered without touching a sibling

- **GIVEN** task A's transaction names a worktree/branch that is only partially created
- **AND** an unrelated sibling task's worktree is separately dirty
- **WHEN** task A retries its managed start
- **THEN** only task A's exact worktree/branch/board entry is inspected and, if safe, recovered
- **AND** the sibling task's worktree and board entry are left untouched

#### Scenario: Board lookup is fenced to exact task identity

- **GIVEN** the agent board contains a stale entry for an unrelated task
- **WHEN** recovery resolves the board entry for the current task's transaction
- **THEN** it matches only the exact `(worktree, branch)` identity recorded in the transaction
- **AND** more than one matching board entry fails recovery closed as ambiguous rather than picking one

#### Scenario: Unsafe partial state blocks automatic recovery

- **WHEN** the candidate worktree named by the transaction has commits not reachable from `main`, dirty paths the task does not own, or task-local state naming a different source issue or change
- **THEN** recovery fails closed with an actionable diagnostic
- **AND** no worktree, branch or board mutation occurs

#### Scenario: Non-canonical path is never deleted as retry debris

- **WHEN** the transaction names a path that is not an exact registered Git worktree
- **THEN** recovery leaves that path untouched and reports that ownership could not be proven
- **AND** does not guess that the path is safe retry debris
