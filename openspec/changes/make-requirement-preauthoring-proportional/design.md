# Design: Proportional pre-authoring selection

## Decision record

The orchestrator records a deterministic depth decision alongside its source/evidence binding. A deterministic path performs no model call. A bounded-evidence path requests only the projections it needs and uses the existing routine, read-only routing tier. A material design path proceeds to ADD and intents under the existing R2 default; documented R3 hard triggers remain the sole escalation mechanism.

## Reuse and invalidation

Each decision names the Requirement digest, target repository, selected projections, and evidence revision. An unchanged matching decision can resume without repeating work. A changed Requirement or stale/missing projection invalidates only the decision and descendants that consumed it. A skip receipt is first-class derived evidence, not a competing lifecycle state.

## Risks

Classification must be deterministic and explainable. The implementation therefore exposes the selected depth, reason, evidence scope, and next action through the existing CLI/state rather than relying on an opaque model choice.
