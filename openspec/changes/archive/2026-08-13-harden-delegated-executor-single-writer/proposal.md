# Proposal: Harden delegated executor single-writer lifecycle

## Why

A real routed Codex handoff left two write-capable executor processes active in the same assigned worktree. Worktree containment does not prevent those writers from racing with each other, so the routing lifecycle needs an explicit single-writer invariant and truthful abnormal-exit cleanup.

## What Changes

- Bind each Codex delegated launch to one monitorable writer identity and process tree.
- Refuse a second write-capable executor for an assigned worktree while the prior writer is still active or ambiguous.
- Terminate and reap launched writer processes on abnormal return before the worktree is eligible for another writer.
- Preserve existing native containment and post-delegation checks.

## Impact

- Modified specifications: `model-routing`, `platform-delegation`.
- Expected surfaces: Codex dispatch/routing, delegated process lifecycle, execution provenance and focused regression tests.
