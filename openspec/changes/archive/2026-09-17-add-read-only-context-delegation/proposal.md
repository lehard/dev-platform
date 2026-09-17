# Proposal: Add read-only context delegation for bulk repository reads

## Why

Current provider-local model routing selects an executor for a managed task, but it does not prevent an already selected R2/R3 session from consuming large repository payloads for narrow exploratory questions. A cheaper read-only context worker can compress that I/O before it reaches the stronger session.

The first version must test the idea conservatively: reuse existing routing/runtime primitives, keep normal direct reading available, collect truthful local evidence, and avoid hard interception until our own workload data supports it.

## What Changes

- Add a provider-neutral context-delegation contract for question-directed bulk repository reads.
- Resolve the auxiliary worker through the existing provider-local routine profile/model mapping rather than durable concrete model IDs.
- Use supported Claude/Codex read-only delegation surfaces and truthful fallback when a runtime cannot provide the capability.
- Return structured evidence rather than raw full-file payloads.
- Record bounded per-observation payload/fallback/timing provenance in the existing execution evidence lifecycle.
- Dogfood the capability softly in dev-platform; do not hard-block Read calls or force downstream projects in this change.

This change is distinct from Development Backlog #31: it does not enable R1 for whole managed tasks.
