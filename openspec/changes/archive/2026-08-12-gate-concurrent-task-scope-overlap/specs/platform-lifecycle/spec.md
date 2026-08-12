## ADDED Requirements

### Requirement: Platform-owned multi-agent execution passes admission before implementation

For `workflow_profile=multi-agent` with platform-owned lifecycle semantics, a task SHALL receive a successful coordination admission before its first implementation change. Task discovery, isolated worktree creation, managed OpenSpec materialization, and semantic preflight MAY occur before admission when needed to resolve exact scope, but `WAIT` SHALL prevent implementation changes.

`standard` and `light` profiles SHALL NOT acquire mandatory multi-agent coordination semantics from this requirement.

#### Scenario: Managed task reaches hard overlap after materialization

- **GIVEN** a managed task has a valid package and an isolated task worktree with canonical OpenSpec materialized
- **AND** semantic scope resolution establishes a hard overlap with an active task
- **WHEN** admission runs before implementation
- **THEN** the result is `WAIT`
- **AND** no implementation change is performed
- **AND** the existing worktree and canonical OpenSpec are preserved for resume

#### Scenario: Multi-agent task has only soft overlap

- **WHEN** preflight finds only soft or potential overlap
- **THEN** the lifecycle surfaces the warning
- **AND** the task is not blocked solely by that warning

### Requirement: Managed overlap waiting projects truthful workflow state

When a managed task receives `WAIT` because of a hard active-scope conflict, the platform SHALL reconcile the configured GitHub Project status to `Blocked` and surface the conflicting task/scope as the blocker reason. A successful later admission SHALL restore the managed task to `In progress` before implementation continues.

#### Scenario: Hard overlap blocks a managed task

- **WHEN** managed task B receives `WAIT` because active task A owns a conflicting concrete path
- **THEN** task B's Project item is reconciled to `Blocked`
- **AND** the blocker context identifies task A and a bounded conflicting scope
- **AND** normal CI or remote processing is not reclassified as this kind of blocker

#### Scenario: Hard-overlap blocker clears

- **GIVEN** the conflicting task no longer owns the concrete path
- **WHEN** the blocked managed task is explicitly resumed and admission succeeds
- **THEN** its Project item is reconciled to `In progress`
- **AND** implementation may continue

### Requirement: Admission resume reuses canonical managed task state

A managed task that previously reached `WAIT` SHALL be resumed from its existing task worktree and canonical repository-local OpenSpec. The next explicit start/resume invocation SHALL re-check admission and SHALL NOT create a duplicate worktree or re-import the original transport package over the canonical change.

No background daemon or automatic autoresume is required.

#### Scenario: Waiting task is retried while conflict remains

- **GIVEN** a managed task is preserved in a task worktree after `WAIT`
- **WHEN** the operator explicitly retries start/resume before the hard conflict clears
- **THEN** the lifecycle reuses that worktree
- **AND** re-checks admission
- **AND** remains `Blocked` without duplicate materialization if the conflict still exists

#### Scenario: Waiting task resumes after conflict clears

- **GIVEN** a managed task is preserved in its existing worktree
- **AND** the conflicting active claim has been released or is no longer valid
- **WHEN** start/resume is invoked again
- **THEN** the lifecycle reuses the existing canonical OpenSpec and worktree
- **AND** admission is evaluated again
- **AND** a successful `RUN` allows normal implementation to continue
