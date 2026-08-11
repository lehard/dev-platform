## Why

Source backlog issue: `lehard/development-backlog#15`  
Prepared against: `lehard/dev-platform@3c970b815b92f0711d85957a263330b8ecd9d439`

`lehard/dev-platform#157` exposed a managed-task drift case in which an existing managed PR no longer carried the expected canonical OpenSpec package in its task checkout, directly edited accepted current specs and implemented only a fragment of the accepted task. The current contract correctly says that the backlog package is only a planning handoff and repository-local OpenSpec becomes canonical after materialization, but resume/publication does not yet assert that provenance strongly enough.

## What Changes

- Persist and re-resolve managed source provenance across start, resume and finish.
- Require a matching canonical active or archived repository-local OpenSpec change for managed execution/delivery.
- Fail closed on missing/mismatched provenance or unexplained direct current-spec edits.
- Reuse existing OpenSpec task, semantic verification and archive evidence for completeness; do not add fuzzy Issue-to-diff scoring.
- Keep repository-local OpenSpec canonical after import and do not overwrite it from the original backlog package during resume.

## Capabilities

### Modified Capabilities

- `managed-task-intake`: provenance survives materialization and can be validated later without restoring the backlog package as a second plan.
- `platform-lifecycle`: managed resume/publication requires matching canonical OpenSpec lifecycle evidence.
