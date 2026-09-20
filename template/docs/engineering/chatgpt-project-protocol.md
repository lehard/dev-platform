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
the relevant open backlog items, then use this ordered mutation-and-verification
sequence. A successful mutation is not a successful fixation until step 6.

1. Resolve the selected target's default-branch revision and prepare one
   package for that exact `prepared_against` SHA. Before writing, validate its
   routing receipt and artifacts with the same managed-package, schema, and
   strict OpenSpec semantics that ordinary managed start will use at that SHA.
   If the connected surface cannot run an equivalent validation against the
   exact revision, it must stop and report that authoring cannot be proven.
2. Search open backlog Issues for an exact task identity, including an Issue
   that has the target/change/authoring receipt but is missing a project or
   priority label. Do not restrict this duplicate search to already-labelled
   Issues. Reuse one unambiguous incomplete Issue; if candidates conflict or
   their scope diverges, stop with the exact partial state instead of guessing.
3. Create the Issue only when no such candidate exists. Its body identifies the
   target repository and OpenSpec change, and it carries the selected target
   label and priority. A retry fills missing deterministic labels on the same
   Issue; it never creates a second Issue for the accepted change.
4. Record source-Issue revision evidence after the Issue body is durable, then
   publish exactly one active package comment. Do not add a second active
   package to repair a malformed or conflicting package: report that state for
   explicit resolution.
5. Read back the Issue, labels, and every Issue comment from GitHub. The one
   active package is a `managed-openspec:v1` comment that contains:

- a JSON manifest with `version`, `source_issue`, `target_repository`,
  `change`, the exact `prepared_against` default-branch revision, ordered
  `artifacts`, and the current routing receipt;
- source-Issue revision evidence when the platform contract requires it; and
- one explicit, non-empty artifact block for each declared `proposal.md`,
  `design.md`, `tasks.md`, and delta-spec path.

6. Treat the read-back as successful only when all of the following are true:

   - the exact open Issue has one selected `project:*` target label and one
     selected `priority:*` label;
   - its body target/change, package `source_issue`, target repository, change,
     and `prepared_against` all agree with the intended identity;
   - exactly one active supported package is present; it has required,
     non-empty source-Issue revision evidence and every declared artifact has
     one explicit, non-empty matching block;
   - the package's routing receipt passes the supported tier/confidence/
     assurance/effort/trigger contract, its source-Issue evidence still matches
     the Issue title/body, and its artifacts pass strict OpenSpec validation at
     the exact `prepared_against` revision.

Use the normal package markers and artifact block layout consumed by
`start_managed_task.py`; do not invent a ChatGPT-specific manifest or import
step. A connected adapter may share a repository-local validator or reproduce
its bounded checks through supported GitHub/repository APIs, but it must fail
closed if it cannot prove every read-back condition. If the connector cannot
create and verify one valid Issue/package pair, report the authoring blocker and
the exact partial state rather than changing intent.

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
