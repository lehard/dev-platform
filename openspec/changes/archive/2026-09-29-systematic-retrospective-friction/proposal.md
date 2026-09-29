# Proposal: Capture meaningful retrospective friction systematically

## Why

Current retrospective gates can accept `none` even when an agent has seen a successful override, a recurrence of an open process issue, or relevant drift in operator-owned state. The later review in dev-platform#172 exposed this gap.

## What Changes

- Make child and Requirement reviews walk a bounded evidence checklist over the actual execution path before checkpointing.
- Treat meaningful successful workarounds, non-default overrides, manual state changes, repeated known problems and observed cross-owner drift as candidates for existing friction evidence.
- Preserve recurrence as a new occurrence linked to the existing process issue, and keep clean completion concise.
- Add regression evidence for the omission class in #172.

## Impact

Existing retrospective/checkpoint, agent friction routing, Requirement terminal flow, and their instructions/tests. No new telemetry store, backlog, or lifecycle.
