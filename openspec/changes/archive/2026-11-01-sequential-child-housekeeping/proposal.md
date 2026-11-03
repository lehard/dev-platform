## Why

A Requirement whose children are delivered one at a time stops twice for housekeeping: in a standalone checkout the delivered child's `.managed-task-state.json` stays and the next import refuses ("task-local managed state conflicts with requested package") until it is moved by hand, and without the coordinator queue a missing Requirement retrospective is raised as an error although it is simply the next step.

## What Changes

- `execute_requirement.advance` archives a Done child's task state before starting the next child when local main equals origin/main and the child's archived contract is on it; a state for a child that is not Done, or a local main behind/ahead of origin/main, still refuses with the named reason.
- `requirement_retrospective.require_checkpoint` raises `RetrospectivePending` (a `RequirementRetrospectiveError`) for a missing or stale receipt; `advance` returns `await-requirement-retrospective` with the exact checkpoint command for it. Unreadable, unsupported or malformed receipts keep failing.

## Impact

- `template/scripts/{execute_requirement,requirement_retrospective}.py`, tests, task-intake docs, manifest.
- Spec: agent-workflow (requirement added).
