# Proposal: Add semantic same-context compaction with an economic gate

## Why

Same-context compaction is already recognized as distinct from durable cross-context handoff, but the platform does not define when a live session should compact. A fixed fullness threshold is too blunt: compacting can save future replay, but it can also rebuild cache/prompt state and discard useful working context.

## What Changes

- Define a small set of semantic compaction opportunities at bounded work transitions.
- Add a simple economic gate that compares expected future replay avoided with compaction overhead/risk using available deterministic/runtime evidence.
- Compact only when the gate passes; otherwise keep the current context.
- Preserve canonical task/OpenSpec identity, verified facts and evidence references, unresolved assumptions/blockers and next intent.
- Compose with cold-observation handles from #131 instead of duplicating exact evidence into the compact state.
- Start as advisory/dogfood, provider-neutral and fail-open.
- Before compaction, inspect the remaining hot payload for cheaper static reductions: repeated system instructions, rarely needed tool/capability definitions, and unstable prompt boundaries. Apply compaction to the residual live history only.

## Capabilities

### Modified Capabilities

- `agent-workflow`: same-context compaction gains semantic opportunities, an inspectable economic gate and truth-preserving continuation requirements.

## Impact

- Long managed-agent sessions and context efficiency.
- No redesign of durable interoperable handoff or task lifecycle.
