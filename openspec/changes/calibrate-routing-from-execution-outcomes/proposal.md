# Proposal: Calibrate Routing v2 from real execution outcomes

Source backlog issue: `lehard/development-backlog#30`.

## Context

The original proposal predated the current execution baseline. Its prerequisites are now implemented: Routing v2 and truthful provenance are live, and `capture-execution-efficiency-baseline` plus `tighten-execution-baseline-comparability` already provide durable routing records, verified/eligible observation semantics, verification lookup and a read-only `efficiency-baseline` report.

The remaining gap is narrower: turn those existing outcomes into routing-specific evidence that a human can use to review the R2/R3 rubric.

## Outcome

Add a bounded read-only routing calibration report that reuses the current routing-record scanner and outcome/verification evidence. It exposes routing-specific sample adequacy, R2 success without frontier escalation, R2-to-R3 escalation paths and reasons where recorded, success after escalation, frontier exposure, and useful breakdowns by task family/rubric/provider-model generation when sample size permits.

The report may produce a human-readable candidate decision such as “no change”, “insufficient evidence”, or a specific rubric/hard-trigger/mapping change to review. It never applies that change itself.

## Activation

Implementation may start now. The first step is to read the current `efficiency-baseline` and determine how many verified executions are usable for routing calibration.

Insufficient routing evidence does not block building the report. It blocks only confident policy-tuning advice. In that case the correct first real result is `insufficient evidence / no policy change yet`.

## Non-goals

- no second telemetry or execution database;
- no ML/classifier/embeddings/vector DB;
- no automatic policy mutation or managed-task creation;
- no R1 rollout;
- no mandatory counterfactual replay;
- no new human-feedback state surface in v1.
