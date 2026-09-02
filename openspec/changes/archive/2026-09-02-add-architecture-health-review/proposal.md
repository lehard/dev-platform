# Proposal: Add Architecture Health Review

## Why

Process Health Review observes engineering-process friction, but agent-first delivery can accumulate architecture debt even when individual tasks complete successfully. Dev Platform needs a separate read-only architecture evidence surface that can reveal weakening boundaries and design seams without automatically refactoring or creating work.

## What Changes

- Consume the optional engineering capability lifecycle from Development Backlog #87 rather than defining architecture-review-specific installation/configuration mechanics.
- Add an advisory Architecture Health Review bound to an exact repository revision.
- Evaluate module/interface depth, locality, coupling, leaking boundaries, seams and repeated abstractions using evidence-backed findings.
- Support bounded alternative-design analysis for high-consequence architecture decisions.
- Keep findings read-only until a human separately accepts a managed change.
