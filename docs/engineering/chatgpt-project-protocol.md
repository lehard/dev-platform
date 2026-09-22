# ChatGPT Project protocol

This document is a thin adapter for ChatGPT Projects that discuss, design, and record changes for repositories governed by Dev Platform.

It does not replace repository-local `AGENTS.md`, OpenSpec, or the target
repository lifecycle. Shared intent boundaries, source-of-truth rules, and the
authoring STOP point are owned by [task-intake.md](task-intake.md). For the
detailed Dev Platform workflow, see [agent-workflow.md](agent-workflow.md).

## Project parameters

A ChatGPT Project should declare:

- `BACKLOG_REPOSITORY` — the operator's explicitly configured Development Backlog repository;
- one or more target repositories;
- the Development Backlog `project:*` label used for each target.

For a single-repository project, use `TARGET_REPOSITORY` + `PROJECT_LABEL`.

For a multi-repository project, use an explicit mapping `repository -> project label`. Before recording a managed change, choose the concrete target repository and corresponding label. If a change genuinely spans repositories, identify the primary target and dependencies or split it deliberately; do not silently mix unrelated repository work into one change.

## Connected-GitHub authoring

ChatGPT Project uses the same requirement-first intent contract as repository
agents. Connected GitHub is an alternative transport, not a different intake
meaning.

### Default fixation: Business Requirement

For an explicit fixation-only request such as «зафиксируй», «добавь в бэклог»,
«создай задачу», «отправь в бэклог», or equivalent, create or reuse a
human-facing Business Requirement. This is the connected-GitHub transport
equivalent of:

```text
python3 scripts/requirement_intake.py create ...
```

The resulting Development Backlog Issue MUST:

- carry `type:requirement`;
- contain `## Outcome`, optional `## Context`, optional
  `## Acceptance evidence`, `## Target repository`, optional
  `## Exclusions`, plus the canonical empty requirement-children marker
  block;
- contain business intent only, with no `proposal.md`, `design.md`,
  `tasks.md`, OpenSpec delta, file-level plan, or technical decomposition.

Before creating a new Issue, search bounded open backlog context for an
unambiguous existing Requirement with the same accepted outcome/target. Reuse
that exact Requirement when appropriate; do not create duplicates merely
because wording differs.

After mutation, read the Issue back and verify the title/body, exact target
repository, `type:requirement` label, and children markers. Fixation succeeds
only after this read-back. A fixation-only request then **stops**: do not start
pre-authoring, create OpenSpec, dispatch an executor, move lifecycle status, or
implement anything.

A ChatGPT Project without a checkout must not fall back to direct
`managed-openspec:v1` authoring merely because it cannot execute
`requirement_intake.py` locally. The connected adapter creates the same
Requirement representation; a repository-local agent can later run
`requirement_intake.py start` against that Issue.

### Execute a Business Requirement

When the user explicitly asks to execute a supplied/existing Business
Requirement, hand it to a repository-capable agent and follow the canonical
flow:

```text
requirement_intake.py start
  -> orchestrate_pre_authoring.py
  -> evidence/snapshot
  -> ADD
  -> human decision only for consequential ambiguity
  -> intents
  -> OpenSpec handoff
  -> internal managed OpenSpec child change(s)
  -> requirement_intake.py link-child
  -> normal implementation lifecycle
```

Each technical child is `type:internal-change` and links back to the parent
Requirement. Requirement progress is derived from those children's real
lifecycle states through `requirement_intake.py aggregate`; never maintain a
second manual status ledger.

### Explicit direct technical managed authoring

The following adapter is reserved for cases where the user explicitly asks to
create a **technical managed task**, or explicitly supplies an existing
managed/OpenSpec task identity. It is not the default handler for generic
fixation language.


This path applies only when ChatGPT Project has supported connected GitHub
mutation access and no checkout of the target repository. It is an alternative
transport, not an alternative task format.

For an explicitly requested **direct technical managed task** (or an existing managed/OpenSpec identity that must be authored through this adapter), inspect the bounded target context and the relevant open backlog items, then use this ordered mutation-and-verification sequence. A successful mutation is not successful technical authoring until step 6.

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
idea as work. Then create or reuse the ordinary Business Requirement through
the requirement-first fixation path and stop. After the Requirement identity
exists, close the incubator Issue with a link to that Requirement; never promote
an incubated idea directly into OpenSpec, `Ready`, or implementation merely
because it was parked.

### Fix / add to Backlog

When the user explicitly asks to record accepted work — for example
«зафиксируй», «добавь в бэклог», «создай задачу», «отправь в бэклог», or
equivalent — the default result is a **Business Requirement**, not a managed
OpenSpec task.

1. Consolidate only the currently accepted business decision.
2. Choose the concrete target repository and corresponding Project routing
   parameter.
3. Create or reuse one `type:requirement` Issue using the connected-GitHub
   Requirement adapter above.
4. Verify its business sections and label by read-back.
5. Stop. Do not start pre-authoring or implementation unless execution was also
   explicitly requested.

A fixation contains Outcome, Context when useful, Acceptance evidence when
useful, Target repository, and Exclusions/constraints when useful. It contains
no proposal/design/tasks/OpenSpec package and no technical decomposition.

If an existing Requirement clearly covers the same accepted outcome, update or
reuse it instead of creating a duplicate. If the business scope boundary is
genuinely consequential and unresolved, ask for that decision rather than
guessing.

### Quick task

A small, clear request that the user wants performed immediately may be handled as a quick task without creating a Backlog Issue or ceremonial OpenSpec.

If the work expands into a material behavior, architecture, compatibility, data-contract, safety, or cross-session change, stop treating it as quick work and enter managed intake before further implementation instead of broadening scope silently.

### Fresh non-trivial execution

When the user explicitly asks to execute fresh material business/product work,
use requirement-first execution: create/reuse the Requirement if needed, then
start that exact Requirement through the repository-local
[task-intake contract](task-intake.md). The repository agent drives
`requirement_intake.py start` and resumable pre-authoring through handoff,
creates the internal managed OpenSpec child change(s), links every child back
to the parent, starts those technical tasks, and only then implements.

Do not ask for a second fixation phrase after the user has already authorized
execution. A fixation-only instruction still creates/reuses the Requirement
and stops.

If the user instead explicitly supplies an existing managed Issue/OpenSpec task
or explicitly asks for a technical managed task, use the preserved direct
managed path rather than wrapping it in a new Requirement.

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

Cluster related symptoms by likely root cause before recommending work. A
`context-gap` is a bounded candidate for project-context improvement, not an
automatic context change: name its likely concern/destination only where the
sanitized evidence supports it, and keep observation, evidence, hypothesis,
and proposal distinct. Keep tooling/process defects outside that classification.
Cite the contributing issue numbers, but do not treat issue count as change count.
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
- Business Requirement Issue (`type:requirement`): normal human-facing accepted-work object before technical authoring.
- Internal managed Development Backlog Issue (`type:internal-change` when parented): technical child/provenance record after pre-authoring handoff.
- Direct managed Development Backlog Issue: explicit technical-path provenance when no Requirement wrapper was requested.
- Development Backlog Project: visualization and technical lifecycle status; the primary human view should show Requirements and exclude `type:internal-change`.

For actual implementation of an existing managed task, hand off to the target repository's current lifecycle instead of continuing from this adapter as a parallel implementation plan.
