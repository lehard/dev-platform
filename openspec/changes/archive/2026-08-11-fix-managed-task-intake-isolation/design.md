## Context

See `proposal.md` for motivation. The current importer writes through its
caller root, while the platform task-start workflow is responsible for
synchronization and isolation. Their documented order lets a managed import
dirty the integration copy before task start, after which synchronization
correctly fails closed.

## Goals / Non-Goals

**Goals:**

- Give platform-owned feature-capable profiles one safe command for beginning a
  managed backlog task.
- Keep package parsing deterministic and materialization scoped to the task
  checkout.
- Fail before task creation for invalid, mismatched, or unsupported packages.
- Clean up only the task state just created by the failed invocation.

**Non-Goals:**

- Change the managed OpenSpec package format or its provenance model.
- Implement a worktree/board lifecycle for `harness_mode=project`.
- Alter the intentional `light` profile behavior.
- Repair, move, or delete existing uncommitted imports in integration copies.

## Decisions

### Add a managed-start orchestrator while keeping importer materialization-focused

Introduce a platform-owned managed-task start command. It will use the same
package parser and target checks as the importer in a read-only discovery mode,
then invoke the existing task-start lifecycle using the package change name as
the task identity. After startup it materializes through the existing importer
logic against the resulting task root.

This avoids parsing human-oriented subprocess output or having the importer
silently switch branches. It also makes the safety boundary a named lifecycle
operation. The alternative—teaching `managed_task.py` to create/switch a
branch—would conflate intake with profile-specific task startup and make
multi-agent board/worktree cleanup harder to reason about.

### Preserve profile and harness ownership

The orchestrator supports platform-owned `standard` and `multi-agent`
profiles. Its task-root resolution follows the existing start lifecycle: the
standard profile uses the newly created feature branch and the multi-agent
profile uses the newly registered worktree. `light` may retain standalone
import because its contract intentionally works on the integration branch.
For `harness_mode=project`, the entrypoint exits with the repository-owned
lifecycle guidance instead of assuming platform paths or board semantics.

### Guard the standalone write path

Before it creates a change, direct import detects a platform-owned
feature-capable caller on the configured integration branch and fails with a
managed-start instruction. The check lives immediately before any filesystem
materialization. This leaves valid direct invocations from a standard task
branch usable for recovery and preserves light-profile compatibility.

### Compensate only invocation-owned task state

The orchestrator records the branch/worktree/board state that it created. If
materialization fails, it removes or unregisters only that newly created,
unmodified state using the existing cleanup primitives; it does not reset,
stash, clean, or delete the integration copy or pre-existing task work.

## Risks / Trade-offs

- [Task creation succeeds but cleanup cannot complete] → report the exact
  branch/worktree/board identifier and leave it visible for normal hygiene;
  never hide it with a broad cleanup.
- [Remote package changes between discovery and materialization] → re-parse and
  compare the package revision before writing; fail closed on a mismatch.
- [Existing project scripts have custom lifecycle ownership] → retain explicit
  project-harness routing rather than treating template paths as universal.

## Migration Plan

New renders receive the orchestrator, importer guard, documentation and tests.
Existing managed projects receive them through normal reviewed Copier update
PRs. A repository with an already dirty integration copy must resolve that
state manually before using the new start path; the change deliberately does
not mutate it.
