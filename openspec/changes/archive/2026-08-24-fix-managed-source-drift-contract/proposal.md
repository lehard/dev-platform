# Proposal: Fix managed source-drift contract

## Why

The source-Issue revision guard currently false-positives on a deterministic platform-authored receipt mutation, and the dogfood status wrapper can print a recovery instruction it cannot execute. The normal author → immediate start → status recovery path must be self-consistent while still detecting real human scope edits.

## What Changes

- Exclude/normalize the deterministic managed-task authoring receipt from source revision evidence or record the post-receipt revision atomically.
- Preserve fail-closed detection for real title/body scope edits.
- Make the dogfood status JSON recovery surface executable through the wrapper that prints it.
- Add end-to-end regressions covering immediate start and genuine drift.
