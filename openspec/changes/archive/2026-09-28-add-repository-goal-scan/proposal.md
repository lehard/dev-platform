# Proposal: Add revision-bound repository goal scans

## Why

Dev Platform has a strong lifecycle for implementing a known change, but broad engineering goals often begin with a different problem: the repository must first be investigated comprehensively enough to identify what should change. A normal search-driven agent has no finite coverage boundary and can stop because it believes it has seen enough.

Cognition's Agentic MapReduce pattern demonstrates a useful architecture for this class of work: an agent defines relevance selectors, deterministic selection produces a finite queue, bounded workers investigate every selected shard, and a reducer synthesizes the structured results. Dev Platform should adopt the provider-neutral architectural idea without depending on Devin/Cognition or creating a second task system.

## What Changes

- Add an opt-in, explicit-only, tool-backed `repository-goal-scan` engineering capability.
- Add a deterministic repository-scan adapter that binds a scan to an exact commit, executes a bounded selector profile over the committed tree, emits a finite candidate/shard manifest, and validates batch accounting.
- Keep Plan/Map/Reduce reasoning provider-neutral: the current executor may process batches sequentially or use native parallel/delegation support, but the platform scan adapter does not become another scheduler.
- Require truthful coverage receipts that distinguish complete processing of the selected scope from selector recall/selection confidence.
- Keep findings advisory until a human explicitly promotes accepted work through the existing quick-task or managed OpenSpec lifecycle.
- Add focused tests/evals that prove completeness accounting and prevent ordinary local implementation/review work from accidentally triggering an exhaustive scan.

## Capabilities

### Modified Capabilities

- `engineering-capabilities`: optional capabilities can include an explicit whole-repository goal scan with deterministic selection/sharding and bounded evidence.

## Impact

- New capability descriptor/instructions and deterministic eval fixture.
- New source + rendered/template scan adapter.
- Capability documentation and ignored machine-local scan state.
- Focused unit/contract tests for selector execution, shard coverage, result accounting, truthful finalization, and trigger boundaries.

## Reference

Architecture reference only: Cognition, "Agentic MapReduce" (2026-07-01) and "Introducing Code Scans" (2026-09-16). No Cognition code, prompts, or proprietary runtime are vendored.
