# Proposal: Add systematic bug diagnosis protocol

## Why

Unknown failures need causal evidence before agents edit production code. A reusable diagnosis protocol should make reproduction, hypothesis falsification and regression evidence normal for genuine diagnosis tasks without burdening obvious bounded quick fixes.

## What Changes

- Consume the optional engineering capability lifecycle from Development Backlog #87 for capability identity, provenance, opt-in, materialization, update and removal.
- Add a provider-neutral diagnosis protocol informed by upstream `diagnosing-bugs`.
- Require a confirmed failure condition and falsifiable evidence path before claiming root cause.
- Prefer a failing regression test before the fix where a reasonable seam exists.
- Re-run the original reproducer after the fix and clean temporary instrumentation.
