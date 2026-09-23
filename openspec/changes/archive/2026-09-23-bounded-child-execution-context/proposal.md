# Proposal: Bounded child execution context

## Why

The Requirement supervisor currently carries substantial pre-authoring and sibling context into child execution. This creates avoidable context growth and permits stale or unrelated details to influence a child.

## What changes

Define a small, provider-neutral execution handoff assembled from the imported managed OpenSpec package, repository revision, parent identity and exact dependency receipts. Start and resume validate this boundary. No accumulated pre-authoring transcript or sibling task body is passed as child input.

## Success evidence

Tests prove the handoff includes only canonical child and bounded dependency facts, rejects stale dependency evidence, and can be refreshed safely.

## Constraints

Preserve existing managed start, routing, containment and OpenSpec authorities. Do not introduce a task queue or a second progress ledger.
