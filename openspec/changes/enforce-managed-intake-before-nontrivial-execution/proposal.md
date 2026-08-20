# Proposal: Enforce managed intake before non-trivial execution

## Why

Dev Platform already has the mechanical pieces for managed authoring and managed start, but the user-facing intent contract still makes managed authoring depend on an explicit fixation phrase such as “зафиксируй”. A user who instead opens Codex or Claude Code and says “сделай” can therefore enter implementation directly: the agent may create a normal OpenSpec change and worktree without ever creating the Development Backlog task that the same change would have received when discussed through ChatGPT.

A second gap makes this behavior persist downstream. Mature repositories may keep project-owned root `AGENTS.md` or workflow guidance across Copier updates. The executable managed-task capability can arrive while the always-on intake semantics remain frozen at an older version. `Jara_Fin` demonstrates this split: it already has Development Backlog configuration and managed-task scripts, while its root guidance still describes the older OpenSpec/worktree flow.

The result is entrypoint-dependent process state and the possibility of an orphan non-trivial OpenSpec/implementation with no managed provenance.

## Current -> target

**Current:** discussion creates no backlog state; explicit fixation creates a managed task and stops; quick execution may start directly; a fresh non-trivial execution request has no mandatory composition from authoring into managed start. Shared intake guidance can also remain stale in project-owned files after a platform rollout.

**Target:** every supported interface uses one semantic boundary. Discussion stays read-only. Explicit fixation authors and stops. Quick work stays quick. An explicit request to execute a fresh non-trivial change first creates or finds the managed task, then starts that same managed task before implementation. Shared intake semantics have a platform-owned canonical destination that existing managed repositories can adopt without losing project-specific rules.

## Expected outcome

A user can describe the same non-trivial problem in ChatGPT, Codex, or Claude Code and receive the same durable task/OpenSpec lineage before code changes begin. The user does not have to remember an extra “зафиксируй” step when they already said “сделай”, while “зафиксируй” still remains authoring-only. Existing managed repositories receive future intake-contract changes through ordinary platform rollout instead of silently retaining stale process semantics.

## Success criteria

- A controlled fresh Codex execution request creates/fetches one managed task, materializes it through managed start, and only then performs implementation.
- Claude Code follows the same contract from the same repository-wide source.
- Explicit fixation still stops after authoring and leaves the task in Backlog.
- Discussion alone and representative quick tasks do not create managed backlog noise.
- A quick task that grows into a material/OpenSpec change transitions to managed intake before further implementation.
- A normal active OpenSpec implementation cannot reach the ordinary completion/publication path without matching managed provenance unless it is using an explicit supported recovery/legacy path.
- Existing managed project migration preserves project/domain rules while making shared intake semantics updateable by platform rollout.
- `Jara_Fin` is used as a representative existing-project acceptance case.

## Scope

- Managed-task intake/authoring/start intent contract.
- A deterministic orchestration entry path for fresh non-trivial execution.
- Provenance enforcement sufficient to catch orphan active OpenSpec work on normal platform-owned paths.
- Central/generated guidance and platform-owned canonical intake documentation.
- Ownership/migration behavior for existing managed repositories, including a representative `Jara_Fin` rollout/migration check.
- Focused Codex/Claude behavioral and template/Copier regression evidence.

## Constraints

- Reuse `managed_task.py create`, `start_managed_task.py`, `managed-openspec:v1`, current Development Backlog configuration, and existing lifecycle state.
- Do not create a second dispatcher, backlog, package format, or task state machine.
- Do not make detailed discussion automatically durable.
- Do not require the user to issue a second command between authoring and start when their original intent was execution.
- Preserve quick-task ergonomics for genuinely small bounded work.
- Preserve project-owned domain rules during migration.

## Non-goals

- Automatically adopting every `candidate` repository into Dev Platform.
- Repackaging an already-in-progress unmanaged task without inspecting its actual local state.
- Background scheduling/dispatch.
- Changing Development Backlog prioritization policy.
- Replacing OpenSpec or existing managed provenance semantics.
