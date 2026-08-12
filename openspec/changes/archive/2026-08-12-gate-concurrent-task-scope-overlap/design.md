# Design: Concurrent task admission gate

## Context

Issue #23 establishes deterministic worktree identity, normalized declared/factual scope comparison, and bounded overlap diagnostics. This change turns exact-path overlap from advisory information into an execution admission decision for platform-owned multi-agent work.

The existing lifecycle already owns managed task worktree creation/materialization and GitHub Project reconciliation. The new gate must compose with those mechanisms rather than create a second scheduler, task database, or OpenSpec plan.

## Dependency

Implementation MUST begin only after `lehard/development-backlog#23` is complete and its `harden-worktree-context-coordination` result is merged to target `main`.

Semantic preflight for this change MUST first inspect the final #23 repository-local implementation/spec and adapt insertion points to that result. If #23 lands with materially different coordination primitives than its prepared package, preserve the requirements in this change and use the smallest compatible extension rather than recreating the planned #23 internals.

## Decisions

### Reuse one coordination model

Admission consumes the canonical task/worktree identity and normalized scope representation delivered by #23. There is no second overlap parser or independent coordination store.

### Keep the gate before implementation, not necessarily before planning materialization

Exact scope may require repository-local OpenSpec and semantic preflight. Therefore package discovery, isolated worktree creation and materialization may happen before the gate. The hard boundary is the first application/platform implementation mutation.

### Treat exact file ownership as blocking and broad proximity as advisory

Hard overlap is based on the same concrete repository-relative path in current claimed scope and another valid active task's claimed or factual scope. Broad directories, subsystems and globs remain warnings unless exact paths are resolved from them.

When factual changed-file evidence exists for an active task, it is the preferred concrete evidence for hard-overlap classification; a broader declaration remains advisory context.

### Make read-and-claim race-safe

The admission operation must serialize the decision that reads active concrete claims and records the current task's successful claim. Reuse the machine-local coordination state and locking primitive produced by #23 if available. If #23 does not expose a suitable primitive, implementation preflight should add the smallest lock/atomic-update boundary around the existing coordination state rather than introduce another state system.

### Preserve managed work on WAIT

`WAIT` is a resumable lifecycle state, not task teardown. If a managed worktree/OpenSpec already exists, preserve it. Re-entry uses provenance to identify that same canonical task, re-runs admission, and only then reconciles to `In progress`.

For managed tasks, a hard-overlap `WAIT` uses the existing Project status reconciliation capability to project `Blocked`. The conflict diagnostic is the blocker reason; this change does not add a second Project workflow field.

### Release claims through existing lifecycle truth

A concrete claim must stop blocking other work when its owning active task is no longer valid/active according to the coordination lifecycle. Exact cleanup/release insertion points depend on the final #23 implementation and SHALL be chosen during implementation preflight so stale claims cannot become permanent blockers.

## Non-Goals

- scheduler or queue service;
- background daemon or automatic autoresume;
- distributed coordination across different machines;
- automatic rebase, merge, reset or mutation of another task's worktree;
- blocking merely because tasks mention the same directory or subsystem;
- changing backlog business priority or choosing the next task automatically;
- changing `standard`/`light` into mandatory coordinated workflows.

## Verification

Use controlled multi-worktree fixtures to cover exact-path blocking, soft-overlap warning, factual-scope precedence, simultaneous claim races, stale/terminal claim release, managed `Blocked -> In progress` reconciliation and reuse of an already materialized task worktree. Run strict OpenSpec validation plus relevant lifecycle/board tests and template/Copier smoke checks.
