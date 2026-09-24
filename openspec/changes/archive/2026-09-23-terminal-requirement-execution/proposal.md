# Proposal: Terminal Requirement execution

## Why

The Requirement flow still stops at handoff and depends on an agent remembering manual child dispatch, resume and integration steps. A user who explicitly requested execution should not manage that internal list.

## What changes

Add a bounded, resumable source-owned supervisor entrypoint that derives current child work from canonical handoffs, managed Issues, child receipts and Git state. It invokes existing lifecycle operations for deterministic transitions and exposes exact next actions where execution itself requires the current agent. It completes only after authoritative shared publication and reconciliation.

## Success evidence

State-transition tests cover fresh execution, interruption/resume, exact reuse and fail-closed blockers; #164 dogfood follows the path through final delivery.

## Constraints

Preserve the existing managed OpenSpec, routing, containment, verification and protected publication authorities. No second lifecycle ledger or automatic parallelism.
