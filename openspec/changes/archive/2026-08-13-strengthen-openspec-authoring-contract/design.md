# Design: Outcome-oriented OpenSpec authoring contract

## Decisions

### 1. Improve existing artifacts instead of adding another layer

The useful Intent semantics are folded into the current OpenSpec proposal/design contract. The platform does not introduce a separate `intent.md` or pre-OpenSpec document. Goal refinement remains selective and transient where already defined.

### 2. Proposal carries the minimum outcome contract

For non-trivial work, proposal guidance requires four semantics:

- expected outcome;
- concrete success criteria or verification evidence;
- relevant constraints;
- non-goals.

The policy requires semantics, not rigid section names. Quantitative thresholds are preferred only when meaningful; binary or directly observable evidence is valid for documentation/process/UX-style changes.

### 3. Current -> target is conditional

When a change modifies an existing workflow, UX, behavior, contract, or architecture and the delta is not obvious, the proposal should state a concise current-to-target transition. A self-contained additive change is not required to repeat an empty AS-IS/TO-BE template.

### 4. Risk analysis is proportional

Design guidance requires concrete risks and mitigations when the change materially touches areas such as data or migration, security/privacy, CI/release lifecycle, external integrations, backwards compatibility, or cross-project/platform rollout.

The platform must not incentivize ritual entries such as “risk: bug; mitigation: tests”. Low-risk changes may omit the section.

### 5. Delivery boundary does not become a second backlog

The current iteration is bounded through scope/non-goals and the existing backlog process. Must/Should/Could is not a mandatory OpenSpec layer. Future ideas that are not part of the accepted change remain explicit non-goals/follow-ups and become separate backlog tasks only when a human fixes them.

### 6. Lifecycle metadata stays mechanical

Status, archive state, verification receipts, and task completion already have authoritative lifecycle sources. The authoring standard does not add manual status/date/expiry/artifact-inventory fields that can drift from those sources.

### 7. Central and generated policy move together

The central `openspec/config.yaml` and `template/openspec/config.yaml.jinja` are updated consistently. Durable explanation lives in `docs/engineering/openspec-workflow.md` and generated guidance where appropriate. Tests/checks should focus on structure, rendering, and parity rather than asserting prose word-for-word.

## Risks & mitigations

- **The stronger proposal contract becomes bureaucracy.** Keep only outcome/criteria/constraints/non-goals unconditional; make current-to-target and risks conditional on relevance.
- **Agents invent fake metrics to satisfy “success criteria”.** Explicitly allow binary/observable evidence and reject ceremonial numeric KPIs.
- **Central and downstream rules drift.** Cover central/template policy parity through focused render/structure checks.
- **OpenSpec becomes a second roadmap.** Keep future Should/Could work outside the active implementation contract unless explicitly accepted into scope.
- **AGENTS.md grows again.** Keep detailed authoring guidance in OpenSpec config/docs; add to AGENTS only if an always-on invariant must change.

## Rollout

This change affects new project rendering and reviewed updates to existing managed projects. No application data migration is involved. Rollback is a normal reviewed platform/Copier downgrade or follow-up change to the authoring policy.
