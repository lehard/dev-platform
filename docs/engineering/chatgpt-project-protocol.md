# ChatGPT Project protocol

This document is a thin adapter for ChatGPT Projects that discuss, design, and record changes for repositories governed by Dev Platform.

It does not replace repository-local `AGENTS.md`, OpenSpec, or the target
repository lifecycle. Shared intent boundaries, source-of-truth rules, and the
authoring STOP point are owned by [task-intake.md](task-intake.md). For the
detailed Dev Platform workflow, see [agent-workflow.md](agent-workflow.md).

## Project parameters

A ChatGPT Project should declare:

- `BACKLOG_REPOSITORY` — normally `lehard/development-backlog`;
- one or more target repositories;
- the Development Backlog `project:*` label used for each target.

For a single-repository project, use `TARGET_REPOSITORY` + `PROJECT_LABEL`.

For a multi-repository project, use an explicit mapping `repository -> project label`. Before recording a managed change, choose the concrete target repository and corresponding label. If a change genuinely spans repositories, identify the primary target and dependencies or split it deliberately; do not silently mix unrelated repository work into one change.

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

Discussion, design, comparison, and repo inspection do not create Backlog state by themselves.

### Incubate / park an idea

When the user explicitly wants an idea preserved for later but does **not** yet
accept it as work, follow the canonical Incubator contract in
[task-intake.md](task-intake.md). Create or update an ordinary Issue in
`BACKLOG_REPOSITORY` with the dedicated `incubator` label and record the target
repository in its body. Do **not** add the target `project:*` label, priority,
managed OpenSpec package, routing decision, or execution state.

Keep the Issue bounded to the idea/hypothesis, why or source, and a revisit
condition. Project placement is optional visualization: if configured, an
auto-add workflow may surface `label:incubator` Issues in an `Incubator` view.
Lack of Project-field mutation must not force a manual copy/paste step or block
saving the idea.

Promotion from Incubator requires a later explicit human decision to accept the
idea as work. Then use the ordinary managed-task authoring flow and leave the
new managed task in `Backlog`. After the managed identity exists, close the
incubator Issue with a link to the promoted task; never move an incubated idea
directly to `Ready` or start implementation merely because it was parked.

### Fix / add to Backlog

When the user explicitly asks to record accepted work — for example «зафиксируй», «добавь в бэклог», «создай задачу», «отправь в бэклог», or equivalent — follow the current Dev Platform managed-task authoring contract.

For a non-trivial managed change:

1. Consolidate only the currently accepted decision.
2. Check relevant open backlog tasks to avoid an obvious duplicate.
3. Inspect only the target-repository context needed to author the task correctly.
4. Create or update the Development Backlog Issue and linked managed OpenSpec package using the current platform process.
5. Leave a newly recorded task in Backlog. Do not implement it, dispatch it, or move it to `Ready` unless the user separately authorizes execution.

If the existing task clearly covers the same change, update it instead of creating a duplicate. If the scope boundary is genuinely ambiguous, ask for resolution rather than guessing.

### Quick task

A small, clear request that the user wants performed immediately may be handled as a quick task without creating a Backlog Issue or ceremonial OpenSpec.

If the work expands into a material behavior, architecture, compatibility, data-contract, safety, or cross-session change, stop treating it as quick work and enter managed intake before further implementation instead of broadening scope silently.

### Fresh non-trivial execution

When the user explicitly asks to execute a fresh material change, follow the
target repository's platform-owned
[managed task-intake contract](task-intake.md): author or reuse one managed
task and immediately start that exact task before implementation. Do not ask
the user for a second fixation phrase after they have already asked to execute.
An explicit fixation-only instruction still authors and stops.

## Verification

Verification should be proportional to actual risk.

- Semantic-preserving documentation/instruction changes should use focused checks for structure, consistency, links/destinations, rendering, and preservation of meaningful rules as applicable.
- An instruction change intended to alter observable agent behavior should use targeted behavioral evidence where the current runtime/process supports it.
- Executable, lifecycle, harness, configuration, API/data-contract, or other behavioral changes should use the relevant software checks required by the target repository.
- Execution must obey the target repository's current authoritative gates; do not assume a proposed validation improvement is already implemented.

Do not create test ceremony that does not reduce the real risk of the change.

## Process Health Review

Process issues are durable, sanitized evidence rather than a second task
system. A review is advisory and read-only until a human explicitly fixes a
candidate into managed work.

Each dated review report records `reviewed_at`, the exact current `main` SHA,
and the previous-review boundary. It reads a bounded current set of open
process issues plus relevant managed tasks and recently merged/closed work
since that boundary. It classifies source evidence as unmanaged, managed,
likely resolved/superseded, needs more evidence, or ready for human decision.
Before calling an older issue resolved or superseded, inspect current repository
evidence; stale issue prose alone is insufficient.

Cluster related symptoms by likely root cause before recommending work. Cite
the contributing issue numbers, but do not treat issue count as change count.
The review may write its dated report, but it must not create a managed task,
close or relabel a source process issue, or implement a fix.

When a human explicitly fixes accepted process evidence into a managed task,
include each exact `owner/repo#N` reference in the task's canonical
process-evidence linkage. Those issues remain open while delivery is in
progress and are resolved only by the terminal managed lifecycle. Project
Instructions should only provide the repository/label parameters and a trigger
to use this contract; they should not copy the procedure.

## Sources of truth

- Target repository `AGENTS.md` and engineering docs: current repository workflow and safety rules.
- Materialized OpenSpec package: implementation contract for a managed change.
- Development Backlog Issue with `incubator` and no `project:*` label: durable pre-commitment idea record.
- Managed Development Backlog Issue: human-facing task/provenance record.
- Development Backlog Project: visualization and managed-task workflow status; Project placement alone does not promote an incubated idea.

For actual implementation of an existing managed task, hand off to the target repository's current lifecycle instead of continuing from this adapter as a parallel implementation plan.
