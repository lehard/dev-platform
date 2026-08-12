# Proposal: Harden worktree context and scope coordination

## Why

Multi-agent lifecycle safety depends on knowing which checkout is being changed and on spotting overlapping work before costly validation or a rebase. Current path normalization and board visibility leave avoidable ambiguity.

## What Changes

- Require a canonical worktree identity at board registration.
- Add bounded overlap diagnostics from declared and factual changed-file scope at lifecycle boundaries.
- Preserve existing Git safety controls; this change improves diagnosis and prevention, not automatic history manipulation.

## Impact

- Affected specifications: `worktree-coordination` (new).
- Affected platform surfaces: agent board, start/publication preflights and unit tests.
- This is reusable multi-agent lifecycle behavior, not downstream product behavior.
