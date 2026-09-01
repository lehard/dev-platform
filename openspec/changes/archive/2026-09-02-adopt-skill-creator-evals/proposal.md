# Proposal: Add provider-neutral skill and capability evals

## Why

Dev Platform needs reviewable evidence that reusable skills/capabilities trigger when intended, stay out of irrelevant work, and improve task outcomes. Anthropic `skill-creator` is a strong reference because its own authoring UX is discoverable by intent and treats testing as part of skill creation/iteration, but its current live trigger runner is Claude-specific and cannot become the provider-neutral platform core unchanged.

## What Changes

- Use the optional-capability identity/provenance/invocation contract from Development Backlog #87 rather than creating a separate skill registry.
- Reuse or adapt safe deterministic pieces of Anthropic `skill-creator` while keeping provider-specific runners behind bounded adapters.
- Add an automatic eval-decision surface consumed by the #87 capability-management path: structural validation always; live eval `run`, `skip-with-reason`, or `blocked/unavailable`.
- Define provider-neutral eval cases, statuses, repeated trigger evidence, and objective with/without quality comparisons.
- Keep direct explicit eval requests supported without requiring users to remember an internal lab name.
- Preserve existing routing, single-writer containment, managed lifecycle, and sanitized evidence rules.
