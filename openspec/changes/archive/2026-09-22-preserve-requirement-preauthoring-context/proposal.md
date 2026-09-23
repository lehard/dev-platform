# Proposal: Preserve complete Requirement context through pre-authoring

## Why

`requirement_intake.py start` currently extracts all Requirement sections but writes only `Outcome` to the local file consumed by the pre-authoring orchestrator. Consequently a later edit to Context, Acceptance evidence, or Exclusions cannot invalidate local design artifacts, and ready handoffs omit accepted business constraints. This contradicts the Requirement-first outcome that the single human-facing Requirement retains the accepted meaning of the work.

## Current to target

Today the local pre-authoring input is an Outcome-only text file. Target behavior derives a canonical local representation of every business section and target repository from the source Issue. Starting or resuming compares the complete representation to its recorded binding. A material source edit stops reuse at the earliest dependent stage; unchanged content remains reusable. Handoffs carry the complete business context as bounded authoring input.

## What changes

- Extend Requirement extraction and local pre-authoring binding to include Outcome, Context, Acceptance evidence, Exclusions, and target repository.
- Make orchestrator freshness/invalidation depend on the complete canonical Requirement representation, not Outcome alone.
- Include complete Requirement business context in handoff envelopes while retaining ADD/intents and managed OpenSpec lifecycle boundaries.
- Specify and test source-edit, unchanged-resume, and handoff-context behavior.

## Success evidence

- Focused tests prove each meaningful Requirement section participates in resume invalidation.
- A resume with unchanged complete content preserves valid upstream stages.
- A validated handoff contains the accepted business context needed for OpenSpec authoring.

## Constraints and non-goals

The Requirement Issue remains the only business-facing source of truth. Machine-local pre-authoring files remain derived evidence, not a second backlog or lifecycle. This change does not alter fixation-only behavior, internal child aggregation, or managed OpenSpec materialization.
