# Proposal: Add a small Harness Replay Lab with capability-first gates

## Why

Context/harness optimizations can reduce payload, token usage or wall time while silently weakening task correctness. Existing calibration and runtime pilots cover specific decisions, but Dev Platform lacks one small reusable replay surface for evaluating platform-level harness optimizations with capability/fidelity checked before efficiency.

## What Changes

- Add a small frozen replay suite, initially about 5–10 representative completed Dev Platform tasks with reconstructable exact pre-change revision and canonical accepted task/OpenSpec contract.
- Preserve authoritative verification outcomes/reference evidence independently from the candidate optimization.
- Evaluate candidates through ordered gates: capability/fidelity first, efficiency only after capability passes.
- Reuse historical native execution evidence when semantically comparable instead of rerunning for ceremony.
- Freeze case identity/content so candidates cannot silently tune or rewrite held-out cases.
- Keep outputs advisory; replay results do not self-promote routing, context, runtime or release changes.

## Capabilities

### New Capabilities

- `harness-evaluation`: reproducible frozen replay cases and capability-before-efficiency evaluation for platform harness/process optimizations.

## Impact

- Platform evaluation fixtures/scripts/reports.
- Reuses managed task, OpenSpec, verification and execution-efficiency provenance.
- No production runtime switch or autonomous self-improvement loop.
