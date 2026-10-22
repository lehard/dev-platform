## ADDED Requirements

### Requirement: Sandboxed Claude writers work in a disposable copy and return a patch

A platform-launched sandboxed Claude writer SHALL run in a disposable copy of the assigned task worktree containing its HEAD and current uncommitted task state, never in the task worktree or integration checkout. The harness SHALL build the result in its own staging clone without executing Git in the writer checkout, SHALL apply the lifecycle write rules, and SHALL apply the resulting patch to the assigned task worktree only when task content still equals the route pre-snapshot; otherwise it SHALL refuse and retain the patch. Integration `main` moving during the run SHALL NOT be classified as a containment violation of this writer.

#### Scenario: Sibling session advances integration main during the run
- **GIVEN** a sandboxed Claude writer is running
- **WHEN** another session fast-forwards integration `main`
- **THEN** the writer's result is still applied and no containment violation is recorded

#### Scenario: Task content changed during the run
- **WHEN** the assigned task worktree content differs from the route pre-snapshot at apply time
- **THEN** the patch is not applied, it is retained, and the dispatch fails naming the diverged paths
