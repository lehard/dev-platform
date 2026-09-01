# ChatGPT Project protocol

This document is a thin adapter for ChatGPT Projects that discuss, design, and
record changes for repositories governed by Dev Platform.

It does not replace repository-local `AGENTS.md`, OpenSpec, or the target
repository lifecycle. Shared intent boundaries, source-of-truth rules, and the
authoring STOP point are owned by [task-intake.md](task-intake.md).

## Project parameters

A ChatGPT Project should declare:

- `BACKLOG_REPOSITORY` — the Development Backlog repository;
- one or more target repositories; and
- the Development Backlog `project:*` label used for each target.

For a single-repository project, use `TARGET_REPOSITORY` plus `PROJECT_LABEL`.
For a multi-repository project, keep an explicit `repository -> project label`
mapping. Choose one concrete target before authoring; identify dependencies or
split genuinely independent cross-repository work.

## Connected-GitHub authoring

This path applies only when ChatGPT Project has supported connected GitHub
mutation access and no checkout of the target repository. It is an alternative
transport, not an alternative task format.

For an accepted non-trivial fixation, inspect the bounded target context and
the relevant open backlog items, then create or update exactly one Issue in
`BACKLOG_REPOSITORY` with the selected target label and priority. The Issue
body identifies the target repository and OpenSpec change. Its one active
package is a `managed-openspec:v1` comment that contains:

- a JSON manifest with `version`, `source_issue`, `target_repository`,
  `change`, the exact `prepared_against` default-branch revision, ordered
  `artifacts`, and the current routing receipt;
- source-Issue revision evidence when the platform contract requires it; and
- one explicit, non-empty artifact block for each declared `proposal.md`,
  `design.md`, `tasks.md`, and delta-spec path.

Use the normal package markers and artifact block layout consumed by
`start_managed_task.py`; do not invent a ChatGPT-specific manifest or import
step. If an exact existing managed task covers the change, update or reuse it
instead of creating a second package. If the connector cannot create one valid
Issue/package pair, report the authoring blocker rather than changing intent.

Leave the result in `Backlog`. Do not implement, start the task, dispatch an
executor, mutate Project status, or publish a delivery. Lack of local
`managed_task.py` is not itself a blocker for this connector-authorized path,
and no local shell is required during its authoring.

## Intent boundaries

### Discuss

Discussion, design, comparison, and repository inspection do not create
Backlog state by themselves.

### Incubate / park an idea

When the user explicitly wants an idea preserved for later but does not accept
it as work, use the canonical Incubator contract in [task-intake.md](task-intake.md).
Do not add a target `project:*` label, priority, managed package, routing
decision, task workspace, or execution state. Promotion requires a later
explicit human acceptance and ordinary managed authoring.

### Fix / add to Backlog

When the user explicitly asks to record accepted work, apply the connected
GitHub authoring mechanics above and stop in `Backlog`.

### Quick task and fresh non-trivial execution

Use the target repository's [task-intake.md](task-intake.md) contract. A quick
task remains bounded; material work first receives one managed task and starts
that exact task. An explicit fixation-only instruction still authors and stops.

## Sources of truth

- Target repository `AGENTS.md` and engineering docs: current workflow and
  safety rules.
- Materialized OpenSpec package: implementation contract after managed start.
- Development Backlog Issue: human-facing task/provenance record.
- Development Backlog Project: visualization and managed-task status only.

For implementation of an existing managed task, hand off to the target
repository lifecycle rather than continuing from this adapter as a parallel
plan.
