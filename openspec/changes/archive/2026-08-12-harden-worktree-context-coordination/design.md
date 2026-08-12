## Context

The board is shared operational memory, but it cannot safely infer a caller's intended current directory or surface conflicts only after a lengthy validation cycle. Existing main-copy hooks remain essential but are a late boundary for some errors.

## Goals / Non-Goals

**Goals:** canonical path validation, deterministic diagnostics, early overlap visibility and tests.

**Non-Goals:** automatic history repair, automatic task cancellation, a global lock for independent work or an alternate backlog system.

## Decisions

- Make the CLI boundary explicit: accept absolute resolved paths, reject ambiguous relative ones.
- Reuse Git worktree metadata to prove branch/path identity before an entry is written.
- Compare normalized repo-relative paths only; report a bounded set of conflicts and preserve board privacy conventions.
- Run overlap observation at start and pre-publication, when the factual diff is known, but keep it advisory until an existing safety rule requires blocking.

## Risks / Trade-offs

Declared scope can be incomplete and factual diff may expand over time, so the check is deliberately repeated. Diagnostics can be stale immediately after reading them; they are a coordination aid, not a concurrency lock.

## Verification

Use temporary multi-worktree fixtures to cover invalid paths, branch mismatch, main rejection, declared overlap and factual overlap; run lifecycle/board tests and strict OpenSpec validation.
