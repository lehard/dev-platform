# ChatGPT Project protocol

This document is a thin adapter for ChatGPT Projects that discuss, design, and record changes for repositories governed by Dev Platform.

It does not replace repository-local `AGENTS.md`, OpenSpec, or the target repository lifecycle. For the detailed Dev Platform workflow, see `docs/engineering/agent-workflow.md`.

## Project parameters

A ChatGPT Project should declare:

- `BACKLOG_REPOSITORY` — normally `lehard/development-backlog`;
- one or more target repositories;
- the Development Backlog `project:*` label used for each target.

For a single-repository project, use `TARGET_REPOSITORY` + `PROJECT_LABEL`.

For a multi-repository project, use an explicit mapping `repository -> project label`. Before recording a managed change, choose the concrete target repository and corresponding label. If a change genuinely spans repositories, identify the primary target and dependencies or split it deliberately; do not silently mix unrelated repository work into one change.

## Intent boundaries

### Discuss

Discussion, design, comparison, and repo inspection do not create Backlog state by themselves.

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
- Development Backlog Issue: human-facing task/provenance record.
- Development Backlog Project: managed-task workflow status.

For actual implementation of an existing managed task, hand off to the target repository's current lifecycle instead of continuing from this adapter as a parallel implementation plan.
