# Proposal: Publish one combined durable Platform Health Review report

## Why

the private Backlog task requires a durable, human-readable GitHub entry point for the Platform Health Review result — a human should never need to remember a local file path or search the repository for output. The platform already proves this pattern works: the periodic process-backlog review (`.github/workflows/weekly-process-backlog-review.md`) persists its dated report as a single GitHub Issue via a `create-issue` safe output, a fixed title prefix, and `close-older-issues` (replace, not accumulate). No spec currently defines this for a *combined* process-plus-architecture report; today the two reviews have no shared report artifact at all.

## Current to target

Today: Process Health Review produces its own dated `[process-backlog]`-prefixed report issue; Architecture Health Review (even once cloud-triggered by the prerequisite changes) has no report artifact of its own.

Target: the combined Platform Health Review (from `add-platform-health-review-orchestration`) produces exactly one dated, human-readable GitHub Issue report per run, covering both process and architecture findings, using the same `create-issue` + fixed-title-prefix + `close-older-issues` mechanism already proven by the existing process-backlog report — this becomes the single durable entry point the requirement asks for.

## What changes

- Add an OpenSpec requirement to the `platform-health-review` capability defining the combined report: one safe-output-produced GitHub Issue per run, dated, recording `reviewed_at`, the exact `main` SHA, and the previous-review boundary, replacing the prior same-prefix report rather than accumulating duplicates.
- Wire the combined trigger's two review jobs to feed one shared report-generation step (or safe output) instead of each producing an independent, uncoordinated report.
- Keep the report strictly advisory: no source-issue mutation beyond what each individual review's existing rules already allow, no managed-task/OpenSpec/PR creation.

## Success evidence

- A combined Platform Health Review run produces exactly one dated report Issue containing both process and architecture findings.
- A second run replaces the prior report (same title prefix, `close-older-issues`) rather than creating a duplicate.
- `openspec validate --strict` passes for the updated `platform-health-review` delta.

## Constraints and non-goals

This change does not add any notification/delivery mechanism (a separate linked change). It does not change either review's own findings/reasoning, and does not alter the existing source-issue mutation rules (ritual comments remain prohibited).

## Delivery scope

An OpenSpec delta to `specs/platform-health-review/spec.md` plus the report-generation wiring in the relevant `.github/workflows/*.md` source(s) and their compiled lock workflow(s). No application/product code changes.

Identity-Redaction: Direct private Backlog identifiers were removed from this current-tree archive after the original review.
