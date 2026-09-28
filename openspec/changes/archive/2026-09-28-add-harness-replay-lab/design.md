# Design: Small frozen replay before large benchmark infrastructure

## Relationship to existing evaluation

- #104 remains a narrow context-delegation calibration and is not generalized by this change.
- External runtime compatibility pilots remain owned by `agent-runtime`.
- Decision-layer pilots remain owned by `decision-layer-evaluation`.
- This capability evaluates Dev Platform's own harness/process optimization candidates across a small representative task set.

## Decisions

1. **Exact replay identity.** A case identifies an exact pre-change repository revision plus canonical accepted task/OpenSpec contract and authoritative verification/reference outcome. Reconstructed prose is insufficient.
2. **Small representative suite.** Start with at least five and roughly 5–10 cases spanning several work shapes; no benchmark farm or scheduler.
3. **Frozen/held-out integrity.** Case content has a stable digest/identity. Candidate work cannot silently mutate the case or acceptance contract.
4. **Capability gate first.** Each candidate declares its acceptable capability/fidelity tolerance before comparison. Required verification/reference outcomes are evaluated before efficiency.
5. **Efficiency only for capability-qualified candidates.** Compare deterministic payloads and authoritative token/cache/request evidence where available, wall time, cost where supported, retries/escalations and human intervention. Missing/incompatible metrics remain unknown.
6. **Reuse historical evidence.** If native baseline evidence is already durable and semantically comparable, reuse it rather than paying for duplicate baseline runs.
7. **Isolation.** Replay work occurs in isolated disposable workspaces against exact source revisions and cannot mutate integration/main or historical truth.
8. **Advisory result.** Reports support a later managed decision. They do not alter routing/context policy, runtime defaults, release state or backlog automatically.
9. **Candidate coverage.** Representative replay comparisons include removal of harness complexity: shorter system/instruction surfaces, lazy tool/capability definitions, less explicit explorer/subagent delegation guidance, and cache-friendly prompt/tool boundaries. Every such candidate uses the same capability gate; upstream savings claims are not Dev Platform evidence.

## Verification

Create controlled replay cases and candidate fixtures including one efficiency-improving but capability-breaking candidate. Prove that capability failure prevents efficiency promotion, a capability-equivalent candidate receives a truthful efficiency comparison, frozen-case drift is detected and replay cannot mutate authoritative source state.

## Bounded execution boundary

The first iteration reconstructs each exact source revision in a disposable detached repository and evaluates candidate outcome evidence supplied by a separate, independently verified run. The lab does not accept executable candidate commands: a caller must isolate that run and retain its verification evidence. Bundled fixtures exercise the evaluator, not a production harness candidate. The native control reuses pinned historical automated-check receipts and is the only bundled case with comparable wall-time evidence. Candidate-supplied observations are labelled in reports and cannot produce a positive optimization conclusion without independent assessment.
