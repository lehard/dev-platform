# Proposal: Adopt provider-local model routing with native-first containment

Source backlog issue: lehard/development-backlog#26

## Why

`dev-platform` already materializes managed work into an isolated task checkout and requires semantic preflight before implementation, but executor selection is still effectively manual. A strong model is therefore commonly used for the entire task even when most implementation work could be completed reliably by a cheaper model.

The required model level cannot always be decided when the backlog task is authored. Real complexity often becomes visible only after the current OpenSpec, relevant accepted specs, active changes and implementation context are inspected together. Model selection should therefore be a runtime execution decision with safe escalation, not durable task metadata.

The existing delegation contract also binds safe write delegation to a specific custom guarded-launch implementation. That was appropriate when native agent runtimes exposed weaker isolation, but current Codex and Claude Code provide native sandbox/worktree mechanisms that may already satisfy the same containment invariant. Keeping duplicate provider-specific guard layers where native enforcement is sufficient would add complexity exactly where model routing needs a simple, reliable execution path.

## What Changes

- Add a provider-local model-routing layer after managed-task materialization and semantic preflight, before implementation.
- Treat the strong parent model as supervisor/router: it performs bounded preflight, selects an abstract execution profile, delegates suitable work to a cheaper executor, and reviews/escalates as needed.
- Support at least `routine`, `standard` and `complex` execution profiles without binding backlog/OpenSpec contracts to today's concrete model IDs.
- Use supported Codex child-model capabilities for OpenAI-local routing and supported Claude Code child-model capabilities for Claude-local routing.
- Change platform delegation from **custom-guard mandatory** to **containment invariant mandatory, native containment preferred**.
- Keep assigned task worktree validation and a lightweight content-aware integration post-check as stable safety invariants.
- Retain custom `delegated_write_guard` behavior only as the smallest fallback/compatibility path needed where native runtime isolation is unavailable or cannot be proven sufficient.
- Remove or simplify redundant provider-specific hooks/detection-only layers only after equivalent or stronger native containment is demonstrated by tests.
- Add explicit escalation and fallback behavior so under-routing does not silently degrade final quality.
- Keep existing checks, OpenSpec semantic verification and publication lifecycle authoritative regardless of executor model.

## Impact

- New specification: `model-routing`.
- Modified specification: `platform-delegation`.
- Expected affected surfaces: generated agent guidance/configuration, runtime-specific agent profiles/adapters, delegated execution integration, containment helper(s) and contract/regression tests.
- Implementation sequence is intentionally incremental: first align/simplify containment, then add routed writers on that boundary. This is not a rewrite of the worktree or publication lifecycle.
- `development-backlog#24` remains independent: goal definition improves the task objective; this change selects compute/executor after task materialization.
