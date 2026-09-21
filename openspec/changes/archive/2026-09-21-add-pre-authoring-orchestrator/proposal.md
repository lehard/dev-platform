# Proposal: Add a resumable pre-authoring orchestrator

## Why

Once Project Evidence Snapshots and a content-bound ADD → Intents → OpenSpec pipeline exist, the stages still require manual sequencing and can repeat expensive work after interruption. Add a thin orchestrator that composes existing primitives, mediates human decisions through the main agent, and resumes from the earliest stale stage without creating a second implementation lifecycle.

## What Changes

- Add one bounded pre-authoring entrypoint for snapshot preflight/reuse, ADD stage, human decision pause, intent decomposition/gates, and OpenSpec handoff.
- Use deterministic code for inventory/freshness/gates, existing routine/read-only workers for snapshot extraction, and R2/standard stages for design/decomposition by default.
- Add a small machine-local run receipt for safe resume and dependency-aware invalidation.
- Keep subagent questions mediated by the main agent and preserve accepted human decisions through the canonical ADD approval path.
- Reuse existing routing escalation and OpenSpec lifecycle rather than introducing a scheduler/task state machine.

## Success Evidence

A representative flow can pause for a human decision or process restart and resume without rebuilding fresh upstream stages; mutation of an upstream artifact invalidates only dependent downstream stages; failures/escalations preserve state; no new backlog/status/source-of-truth lifecycle appears.

## Dependencies

Requires Development Backlog #127 and #128.

