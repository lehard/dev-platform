# Proposal: Shared Requirement integration

## Why

The current managed lifecycle publishes every internal child independently. For a decomposed Requirement this repeats full CI and produces multiple authoritative PRs even when children are only parts of one accepted business outcome.

## What changes

- Add a verified child handoff to a requirement-level integration candidate without equating that handoff to terminal delivery.
- Compose exact child results and provenance in one isolated integration worktree, validate their interaction, and publish one protected PR/full-CI candidate by default.
- Keep separate child publication as an explicit exception justified by independent delivery or rollout risk.

## Success evidence

A local/bare-remote two-child CLI rehearsal proves isolated child work, exact combined-candidate composition and safe retry. Tests cover stale heads, conflicting edits, failed integration checks and terminal reconciliation only after an exact merged PR. The first live two-child GitHub PR/full-CI dogfood is an acceptance gate for the later terminal Requirement execution change, after this bootstrap primitive is published.

## Constraints and non-goals

Reuse existing managed OpenSpec, worktree, protected PR, review and archive authorities. No parallel scheduler, queue, relaxed verification, or duplicate status database.
