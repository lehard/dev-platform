# Proposal: Materialize ready Requirement handoffs idempotently

## Why

Prepared handoffs currently require a human to rebuild a managed-task bundle and separately remember parent linkage. A retry can therefore create duplicate technical work or leave the business Requirement reporting a misleading partial state.

## What changes

- Add a validated handoff-to-managed-bundle adapter using the existing managed-task intake contract.
- Identify a prior successful creation by stable handoff identity and reuse only an exact match.
- Repair missing linkage before returning success, while failing safely for invalid input or ambiguity.

## Success evidence

- Tests exercise new, repeated, interrupted, invalid, and ambiguous materialization paths.
- A successful result has both canonical managed provenance and the immediate parent/child link.

## Constraints and non-goals

Managed OpenSpec is canonical after import. The adapter is a boundary layer, not a replacement for managed-task creation, lifecycle, or downstream rollout.
