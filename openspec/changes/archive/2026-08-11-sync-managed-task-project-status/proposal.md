## Why

Source backlog issue: `lehard/development-backlog#8`

Development Backlog is intended to be the human control plane for managed work,
but its Project `Status` currently stops reflecting reality as soon as work is
picked up. `start_managed_task.py` creates the task workspace/branch and
materializes the managed OpenSpec package without changing the Project item, so a
real running task can remain in `Ready` until the source Issue is eventually
closed. The board therefore cannot reliably answer the basic operational
question: what is waiting, running, awaiting review, blocked, or done?

The lifecycle already has deterministic events that can drive this projection:
managed start, reviewable PR publication, explicit blocker/recovery, confirmed
remote merge and terminal reconciliation. Project status should follow those
events instead of requiring the user or model to remember manual moves.

## What Changes

- Make GitHub Project `Status` a lifecycle projection for managed tasks.
- Keep `Backlog -> Ready` human-owned; automation starts only after an explicitly
  selected managed task is actually accepted for execution.
- Move a successfully started managed task to `In progress` before implementation
  continues.
- Move an active task to `In review` when its reviewable delivery PR is published
  or reused and delivery is awaiting CI/review/merge.
- Represent a genuine human/external stop as `Blocked`, and restore the correct
  active state on resume.
- Move to `Done` only after confirmed terminal delivery/reconciliation, never for
  local completion, a green-but-open PR, or an unmerged review.
- Add idempotent Project-status reconciliation so interrupted or historically
  stale managed tasks can converge to the state supported by authoritative
  lifecycle evidence.
- Add the stable Project workflow configuration/identity required for generated
  managed repositories to perform these updates without UI scraping.

## Capabilities

### Modified Capabilities

- `platform-lifecycle`: project managed-task workflow state from real lifecycle
  events and reconcile it after interruption.
- `project-factory`: deliver the configuration and self-contained runtime needed
  for managed Project-status synchronization to downstream repositories.

## Non-goals

- Selecting or dispatching tasks from `Ready`.
- Automating the human `Backlog -> Ready` decision.
- A background daemon/scheduler that polls the Project.
- Turning the machine-local multi-agent board into the Development Backlog.
- Creating Issues for individual status transitions.
- Changing quick-task behavior when no central managed Issue exists.
