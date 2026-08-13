## Context

The platform must maintain group-writable collaboration metadata without assuming that every ignored machine-local path belongs to the platform. Existing broad `.claude` traversal is unsafe because tool runtimes may manage symlinks and high-churn caches there.

## Goals / Non-Goals

**Goals:** explicit ownership, bounded traversal, preserved repair of owned metadata, regressions for known false blockers.

**Non-Goals:** recursively normalizing arbitrary user/tool caches, changing project application-file ownership policies, or removing existing safety boundaries.

## Decisions

- Derive the audit set from a reviewed allowlist rather than walking all `.claude` children.
- Treat unknown `.claude` entries as foreign and leave them untouched; known platform state stays audited.
- Keep project wrapper exclusions narrowly pattern-based for transient partial dependency caches rather than broadly disabling permission checks.
- Cover the behavior with isolated filesystem fixtures so no real agent cache is inspected or repaired during tests.

## Risks / Trade-offs

An allowlist can miss a newly added platform state path. New platform writers must therefore register their path and receive a test. This is preferable to changing or blocking arbitrary machine-local tool data.

## Verification

Run shared-workspace and rendered-wrapper tests, a doctor smoke with an external symlink fixture, strict OpenSpec validation, and template/Copier rendering smoke where available.
