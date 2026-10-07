## Why

Work identity: BR-436/T1

`requirement_intake.py create` and the connected-GitHub adapter report Requirement fixation after reading back Issue labels only. Development Backlog Project membership depends on GitHub's asynchronous built-in auto-add, and nothing confirms it. `managed_project_status` also treats a missing item as an unrecoverable error, so a Requirement can be reported as fixed while absent from the operator's board.

## What Changes

Add an idempotent `ensure_item` operation to `managed_project_status` (add via `addProjectV2ItemById`, initialize unset Status to `Backlog`, read back exactly one item). Make `create` confirm membership before success, reuse an identical open Requirement on rerun and fail closed naming the durable Issue. Add `requirement_intake.py reconcile-board` and ensure membership in `start`. Document the connected-GitHub rule: fixation is complete only on confirmed membership, otherwise reported as unconfirmed and completed by operator reconciliation.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `managed-task-intake`: Requirement fixation requires confirmed Project membership.

## Impact

Shared template `managed_project_status.py` and `requirement_intake.py`, task-intake and ChatGPT protocol docs, regression tests. No new service, no Project migration, no change to existing Requirements or children beyond idempotent membership repair.

## Success Evidence

Tests cover auto-add present, absent, existing item, repeated reconciliation, duplicate refusal, unavailable Project API, initial Backlog status, repository-local and connected outcomes. Live read-back shows the existing Requirements on the board with exactly one item each.
