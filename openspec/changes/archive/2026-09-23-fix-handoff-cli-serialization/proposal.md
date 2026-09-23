# Proposal: Fix successful handoff CLI serialization

## Why

The handoff adapter creates and links a child, then raises `UnboundLocalError` while printing the result because a branch-local `import json` shadows the module name in `main`. This makes a successful durable operation appear to fail and blocks automatic Requirement execution.

## What changes

Use the module-level JSON import for every command path and add a CLI regression that exercises a confirmed success and retry.

## Success evidence

The regression proves exit zero, parseable output, exact child reuse, and intact bidirectional links. Existing intake tests and platform checks remain green.

## Constraints and non-goals

No change to handoff validity, issue identity, or managed OpenSpec authority.
