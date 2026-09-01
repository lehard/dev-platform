# Proposal: Add independent verification perspectives

## Why

Agent-first implementation benefits from separating the context that produced a change from the context that judges it. Existing semantic OpenSpec verification remains authoritative, but it should be able to incorporate independent evidence for contract fidelity and engineering quality.

## What Changes

- Add distinct spec-fidelity and engineering-quality review perspectives for material changes.
- Bind both reviews to the exact candidate/base being verified.
- Feed findings into the existing verification receipt/lifecycle rather than creating another state machine.
- Keep runtime/provider choice replaceable and fail truthfully when independent review cannot be obtained.

## Current to target

Today the completion lifecycle accepts a semantic PASS receipt and deterministic
check evidence but has no structured way to bind an independent review to the
candidate. The target adds an opt-in evidence gate for managed material work:
two fresh, read-only perspectives must be bound to the exact candidate, and
unresolved material findings or unavailable required reviews prevent archive
readiness.

## Success evidence

- A provider-neutral request and two bounded reports are accepted only for the
  exact base/candidate/diff identity they name.
- When the capability is enabled, archive readiness rejects a missing,
  unavailable, stale, or materially unresolved report even when ordinary tests
  and a PASS receipt are otherwise present.
- Spec-fidelity and engineering-quality controlled failures are independently
  covered by regression tests; quick and unmanaged work stays outside the
  gate.

## Scope and non-goals

This change supplies the request/report contract, validation, lifecycle gate,
template distribution, and documentation. It does not select, install, or
operate a specific review provider, make review mandatory where no capable
runtime is configured, create a separate completion state machine, or permit a
reviewer to publish code or mutate Backlog/Project state.
