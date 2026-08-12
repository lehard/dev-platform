## Context

Managed-task start already gives the platform a natural routing boundary: `start_managed_task.py` materializes the accepted OpenSpec into an isolated task checkout and then requires semantic preflight before implementation. The desired user experience is simple: the user starts work through a strong parent/supervisor and does not manually choose the cheaper executor.

The accepted `platform-delegation` spec currently contains two different kinds of contract mixed together: durable safety invariants (valid assigned worktree, strongest proven write boundary, protected integration state, post-check) and historical implementation choices (all writers must enter one custom guarded path, provider-specific hooks/detection-only handling). New native Codex and Claude capabilities make it reasonable to separate those concerns.

## Goals / Non-Goals

**Goals:** reduce unnecessary strongest-model usage; keep one simple entrypoint; route using current repository context; use native provider-local child models; preserve or improve write isolation; simplify legacy custom containment where it duplicates native enforcement; automatically escalate under-routed work.

**Non-Goals:** cross-provider routing, learned/ML routing, a separate orchestration service, durable per-task model metadata, removal of safety checks, or a rewrite of worktrees/managed lifecycle/publication.

## Decisions

### Containment alignment comes first inside the same change

Do not create a separate architecture rewrite. Before wiring routed writers, update the delegation contract and implementation so the stable requirement is the containment invariant rather than mandatory use of one helper. This avoids building routing on a layer that would immediately be refactored afterward.

### Native containment first, custom guard only where useful

For each supported current Codex and Claude surface, verify the actual sandbox/worktree behavior during implementation preflight. If native OS-level containment proves that writes cannot escape the assigned task boundary for the real filesystem topology, use it directly as the primary prevention mechanism. Keep a lightweight content-aware integration post-check as defense in depth.

Retain only the minimum custom `delegated_write_guard`/hook/detection-only logic required for supported modes that do not have sufficient native isolation. Delete or simplify provider-specific duplicate logic only after equivalent or stronger behavior is covered by deterministic tests. Do not build a new generic security framework to replace the old one.

### Routing boundary

Routing happens after managed-task materialization and bounded semantic preflight, before implementation. Managed-task routing is the required first integration because it has the strongest canonical context boundary.

### Parent as supervisor

The user starts the task through a sufficiently strong parent. The parent reads the canonical change and relevant current context, classifies an abstract execution profile, delegates when appropriate, receives the result and owns escalation/final assessment. A complex/high-risk classification can remain on the parent without a cheap-model trial.

### Abstract profiles, replaceable model mapping

The durable contract names execution profiles, not model IDs. Concrete model/reasoning settings live in the smallest versioned platform-owned runtime configuration/generated agent-profile surface supported by current Codex/Claude runtimes and downstream Copier rollout.

### Provider-local routing

Codex parent routes only to configured OpenAI child profiles in v1. Claude parent routes only to configured Claude child profiles. Cross-provider credentials/context translation are deliberately deferred.

### Escalation is asymmetric

Over-routing mainly costs tokens; under-routing can cost correctness. Routine/standard executors therefore stop and escalate on material contract conflict, unexpected cross-cutting scope, low confidence or bounded substantive verification failures. The stronger profile receives the existing worktree, diff, canonical OpenSpec, findings/check failures and escalation reason.

### No parallel source of truth

Routing assessment is runtime execution state, not a second implementation plan. Canonical task intent remains the Issue/OpenSpec and implementation state remains the task checkout.

## Risks / Trade-offs

Native subagent APIs and model identifiers evolve quickly, so implementation must verify supported capabilities and keep mappings replaceable. Native sandbox claims must be validated against actual writable roots and filesystem topology rather than assumed from marketing-level descriptions.

Simplifying custom containment too aggressively could remove protection for unsupported modes. The implementation therefore keeps fallback behavior until tests prove it redundant. Keeping every historical layer forever would create the opposite failure mode: unnecessary complexity, duplicated policy and more places for behavior to diverge.

## Verification

First verify containment behavior for current supported Codex VS Code/CLI and Claude Code Desktop/CLI surfaces, including attempts to mutate integration/main from a child. Confirm native-contained paths remain blocked and the post-check detects simulated/bypassed violations. Confirm fallback behavior still works where native containment is not available.

Then exercise provider-local routing scenarios: routine/standard delegation, complex retain-on-parent, standard-to-complex escalation and missing cheap executor fallback. Verify downstream rendered projects receive the required agent configuration/guidance through Copier and changing concrete model mappings does not edit managed task artifacts.
