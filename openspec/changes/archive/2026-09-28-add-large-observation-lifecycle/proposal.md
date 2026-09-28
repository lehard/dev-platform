# Proposal: Add a lifecycle for large observations with exact recall

## Why

Long coding-agent runs can repeatedly replay large tool observations after the full payload has stopped being useful. Existing read-only context delegation reduces selected repository payload before it enters the parent context, but it does not manage large observations that have already been produced by reads, searches, commands, tests or runtime tools.

The platform needs a smaller active representation without sacrificing exact evidence.

## What Changes

- Add a provider-neutral large-observation lifecycle that can retain an exact original payload in bounded run/session-local storage and replace its hot representation with a stable handle, metadata and bounded excerpt.
- Add targeted exact recall by handle and bounded range/query so later work does not need full-payload reinjection by default.
- Keep small observations on the current path.
- Record deterministic source/hot/recall payload measures and trigger rate/intensity, while treating runtime token/cache fields as canonical only when truthfully exposed.
- Fail open to current full-observation behavior when the supported runtime cannot provide the lifecycle safely.

## Capabilities

### Modified Capabilities

- `model-routing`: execution/context-efficiency evidence gains a provider-neutral large-observation lifecycle distinct from read-only context delegation.

## Impact

- Runtime/tool-result adaptation and execution provenance.
- Context-heavy dogfood and efficiency reporting.
- No change to managed task identity, routing tier, verification authority or durable source-of-truth ownership.
