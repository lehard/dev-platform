# Proposal: Check completion blockers before expensive validation

## Why

The completion lifecycle can spend minutes on a full suite before stopping on a blocker that was already observable. Sequential fail-fast gates also require repeated finish invocations, and sparse progress encourages unsafe ad-hoc pollers.

## What Changes

- Evaluate existing read-only and cheap completion gates before expensive checks.
- Report independently observable blockers together.
- Emit bounded stage and test-group progress from the existing synchronous finish.
- Preserve validation, publication and resumability semantics.
