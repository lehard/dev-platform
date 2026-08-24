# Proposal: Add an experimental DeepSeek Harness runtime adapter

## Why

DeepSeek Harness is a promising external agent runtime, but adopting it as a platform foundation before evidence would couple Dev Platform to a fast-moving developer-preview system. We need a deliberately small experimental integration surface that can later support a controlled comparison while leaving the current production execution path unchanged.

## What Changes

- Add an optional DeepSeek Harness runtime adapter behind a minimal platform-owned runtime boundary.
- Pin an exact upstream DSH version and define a tested upgrade path.
- Keep the adapter disabled by default and outside automatic downstream execution.
- Normalize bounded result/timing/usage/containment evidence into the runtime-neutral execution evidence from `lehard/development-backlog#68`.
- Preserve Dev Platform ownership of task/OpenSpec/workspace/routing/verification/publication/release lifecycle.
- Add contract tests and a safe host-level smoke path without requiring a production switch.

## Dependency and gate

The normalized execution evidence from `lehard/development-backlog#68` is the comparison contract. This change may build the adapter in parallel, but it SHALL NOT decide or enable production runtime switching before a separate evidence-based pilot.