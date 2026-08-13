# Proposal: Strengthen OpenSpec authoring around outcomes

## Why

Dev Platform already has strong lifecycle semantics: current specs plus active deltas are canonical, implementation may not silently diverge, and semantic verification is required before archive/publication. The weaker point is upstream task formulation. A proposal can satisfy the current structure while still leaving the desired outcome, success evidence, constraints, or behavior transition implicit.

That ambiguity is expensive for agent-first work because executors then reconstruct intent from chat history or optimize the implementation checklist rather than the result.

## Current -> target

**Current:** proposal rules require goals/non-goals and affected areas, while design focuses on compatibility/rollback and tasks on execution. Outcome evidence, explicit constraints, behavior transition, and risk framing are inconsistently authored.

**Target:** every non-trivial OpenSpec carries enough outcome-oriented context to let a fresh executor and semantic verifier understand what success means, what must not change, and where proportional risk analysis is required, without adding another mandatory planning artifact.

## Expected outcome

A compact shared authoring contract is applied to `dev-platform` itself and to generated managed projects. OpenSpec proposals make the desired result and success evidence explicit; relevant constraints and non-goals bound scope; current-to-target framing and risk mitigation are required only when they materially improve clarity or safety.

## Success criteria

- A representative non-trivial proposal states an expected outcome plus concrete quantitative or binary/observable success evidence.
- Qualitative work can use binary/observable criteria without inventing numeric KPIs.
- Existing-behavior changes use concise current-to-target framing when the transition is otherwise ambiguous.
- Materially risky designs record concrete risks and mitigations; low-risk changes are not forced to create boilerplate risk sections.
- Central and generated OpenSpec configuration express the same contract and downstream rendering/update remains valid.
- No new mandatory `intent.md`, lifecycle status/date fields, MoSCoW layer, or parallel backlog is introduced.
- Semantic verification guidance explicitly checks the authored outcome/success evidence in addition to specs completeness, correctness, and coherence.

## Scope

- Central OpenSpec authoring policy and guidance.
- Generated OpenSpec policy for managed projects.
- Durable specification for the authoring contract.
- Focused validation/rendering coverage needed to prevent central/template drift.

## Constraints

- Preserve the existing OpenSpec artifact model: proposal, specs, design, and tasks.
- Keep detailed mechanics out of the bounded `AGENTS.md` unless an always-on invariant genuinely changes.
- Do not require fake metrics, empty risk tables, or current/target prose where they add no information.
- Preserve reviewed Copier update semantics for existing projects.

## Non-goals

- A separate Intent lifecycle or mandatory `intent.md`.
- Mandatory Must/Should/Could classification.
- A new backlog, workflow engine, or OpenSpec CLI fork.
- Manual duplication of lifecycle status, dates, expiry, or artifact inventories.
