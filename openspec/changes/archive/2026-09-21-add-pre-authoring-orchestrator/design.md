# Design: Resumable pre-authoring orchestrator

## Scope

The orchestrator is composition glue. Snapshot semantics stay in #127; ADD/Intent integrity, atomicity and OpenSpec handoff stay in #128; managed task/OpenSpec/GitHub delivery stays in the existing lifecycle.

## Stage graph

```text
preflight
  -> snapshot build/reuse
  -> ADD build/refine/approve
  -> intent decomposition + gates
  -> OpenSpec authoring handoff
```

Represent dependencies explicitly enough to invalidate downstream stages when an upstream digest changes. Do not create a general DAG engine.

## Stage execution

- deterministic inventory/freshness/schema gates: local code;
- snapshot semantic extraction: existing routine/read-only workers;
- ADD and intent semantic work: R2/standard by default;
- OpenSpec authoring: existing authoring/routing behavior;
- escalation: only existing hard triggers/bounded substantive-failure rules.

Provider-native subagents may be used, but the platform does not build a scheduler around them.

## Human decision protocol

A stage worker may return a bounded decision request: question, alternatives where known, evidence, consequences/tradeoffs, optional supported recommendation, affected ADD elements. The main agent asks the user and applies the accepted result through ADD refinement. Workers do not self-approve product/architecture choices.

## Resume receipt

Store only machine-local navigation data such as requirement/repository identity, snapshot digest/status, ADD digest/approval digest/status, intent-set digest/status, handoff digest/status, current/next stage and bounded blocker evidence.

No raw transcript, prompts or chain-of-thought. Receipt state never overrides canonical source identities.

## Failure behavior

Retry/resume the culprit or invalidated stage only. Preserve fresh upstream artifacts. Missing evidence fails closed. Avoid background polling and unbounded model retries.

## Reference boundary

Re-check the supplied Intents bundle/transcript for isolated-stage orchestration, central user mediation, session state and resume behavior; adapt clean-room and omit Jira/Confluence/provider-specific lifecycle machinery.

