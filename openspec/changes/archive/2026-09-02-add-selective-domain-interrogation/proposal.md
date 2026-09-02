# Proposal: Add selective domain interrogation

## Why

Materially ambiguous domain work can fail before coding begins if the agent silently invents terminology, assumptions or product choices. Dev Platform should offer a selective pre-design interrogation mode that resolves repository-answerable facts from evidence and surfaces only genuine human/product decisions, while keeping OpenSpec as the sole implementation contract.

## What Changes

- Consume the shared optional engineering capability lifecycle from Development Backlog #87 for identity, provenance, opt-in, provider materialization and update/removal.
- Add domain-interrogation/refinement behavior for ambiguous or domain-heavy managed work.
- Resolve repository-answerable uncertainty from evidence before asking the human.
- Route accepted decisions into existing OpenSpec proposal/spec/design artifacts.
- Avoid mandatory new context/ADR/status documents or a competing planning lifecycle.

## Outcome and success criteria

Qualitative instruction/workflow change; success is directly observable, not a KPI:

- A representative ambiguous domain task surfaces at least one materially consequential ambiguity before implementation and routes the resolution into an existing OpenSpec artifact.
- A repository-resolvable ambiguity is closed from evidence with its source recorded and no user question.
- A sufficiently clear task proceeds with no interrogation step.
- The capability adds no `CONTEXT.md`, ADR/status ledger, second backlog, or competing implementation plan, and introduces no domain-interrogation-specific registry/config/update lifecycle — it consumes the #87 optional-capability lifecycle only.
- After refinement, the materialized OpenSpec package remains the single canonical implementation contract.
