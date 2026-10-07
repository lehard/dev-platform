## Why
Private Issue references in child OpenSpec artifacts currently survive until shared publication, wasting full candidate validation and requiring rebuilds. Early rejection must use the existing privacy semantics and opaque diagnostics.

## What Changes
- Run the existing private-reference guard before archive review, selected checks, evidence writes or OpenSpec mutation in privacy-enabled checkouts.
- Run it for shared Requirement candidates before full checks and publication.
- Fail explicitly when a configured privacy guard is missing or fails; retain publication rechecks.

## Success Evidence
Regressions with private references in proposal/design or archived artifacts stop archive and shared publication before expensive work. Clean candidates proceed. Diagnostics do not expose private identifiers. Missing guard stops configured enforcement.

## Non-goals
No new scanning syntax, automatic sanitization, altered validation coverage, generic downstream privacy opt-in, or retrospective backlog repair.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `completion-lifecycle`: enforce privacy before child archive and shared full validation.

## Impact
Template archive and shared Requirement publication entrypoints, focused lifecycle tests, and operating guidance. Downstream behavior is enabled only by the existing private-lineage opt-in.
