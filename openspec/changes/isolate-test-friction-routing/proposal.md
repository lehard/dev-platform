# Proposal: Isolate test friction routing from live GitHub

## Why
Containment/delegation tests intentionally generate synthetic violations and invoke the real local friction recorder. On an authenticated host these fixture events can reach the live GitHub process backlog; `lehard/dev-platform#137` is the evidence.

## What Changes
- Keep synthetic tests hermetic with respect to external GitHub writes.
- Preserve fixture-local friction recording assertions.
- Preserve production friction routing for real runtime events.
- Add regression coverage independent of host `gh` authentication.
