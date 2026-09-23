# Proposal: Shared Requirement integration

## Why

The current managed lifecycle publishes every internal child independently. For a decomposed Requirement this repeats full CI and produces multiple authoritative PRs even when children are only parts of one accepted business outcome.

## What changes

- Add a verified child handoff to a requirement-level integration candidate without equating that handoff to terminal delivery.
- Compose exact child results and provenance in one isolated integration worktree, validate their interaction, and publish one protected PR/full-CI candidate by default.
- Keep separate child publication as an explicit exception justified by independent delivery or rollout risk.

## Success evidence

An end-to-end two-child dogfood proves isolated child work, one integration PR and full CI, child-level traceability, safe retry and terminal reconciliation. Tests cover stale heads, conflicting edits and a failed integration check.

## Constraints and non-goals

Reuse existing managed OpenSpec, worktree, protected PR, review and archive authorities. No parallel scheduler, queue, relaxed verification, or duplicate status database.
