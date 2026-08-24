# Proposal: Capture execution efficiency baseline

## Why

Dev Platform already records truthful routing/execution provenance, but it cannot yet establish a comparable before/after baseline for execution efficiency. We need bounded runtime-neutral evidence for wall-clock time, token/context usage where authoritative, request counts where authoritative, and completion/verification outcomes without creating another observability system.

This is motivated by real process evidence `lehard/dev-platform#255`, where a bounded task completed while consuming millions of tokens despite a high cache-hit ratio.

## What Changes

- Extend the existing execution provenance with runtime-efficiency measurements and explicit source/unknown semantics.
- Measure elapsed wall-clock time at the platform boundary for managed executions.
- Capture normalized token/cache/output/request-count data only when the supported runtime exposes authoritative values.
- Reuse existing verification, retry/escalation, fallback, human-intervention and containment outcomes rather than duplicating them.
- Add a bounded baseline report with sample-size/insufficient-evidence handling.
- Keep the schema runtime-neutral so a later external runtime adapter can emit the same evidence.

## Relationship to existing work

`lehard/development-backlog#30` remains the routing-calibration task. This change supplies additional execution-efficiency evidence that #30 and later runtime comparisons may consume; it does not change routing policy.