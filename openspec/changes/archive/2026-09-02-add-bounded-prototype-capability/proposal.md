# Proposal: Add bounded prototype capability

## Why

Material product, UI and technical uncertainty is sometimes cheaper to resolve through a small observable experiment than through more analysis. Dev Platform has no sanctioned way to run one, so agents either over-analyze or let disposable experimental code leak into a managed implementation. The platform needs a bounded prototype/spike mode that produces a decision plus evidence without creating a second task lifecycle or bypassing managed intake.

## What Changes

- Consume the shared optional engineering capability lifecycle (Development Backlog #87) for identity, provenance, opt-in, provider materialization and update/removal.
- Add an opt-in `bounded-prototype` capability with explicit triggers and negative controls for a disposable experiment that resolves material uncertainty.
- Require the experiment to run in an isolated temporary workspace or an explicitly declared prototype area, and to leave production source, dependencies, credentials and task state unchanged.
- Require a bounded record of question, options/hypotheses, declared bounds, observation, decision/remaining uncertainty and an evidence reference.
- Require default cleanup of temporary state with explicit, policy-compatible retention only, and prohibit automatic promotion of prototype code into production.
- Route any follow-on implementation through the ordinary managed OpenSpec lifecycle.

## Outcome and success criteria

Qualitative instruction/workflow change; success is directly observable, not a KPI:

- A representative UI comparison and a representative falsifiable technical spike each run as a bounded experiment, in an isolated area, and end with a recorded decision and evidence reference.
- A sufficiently clear task triggers no prototype ceremony.
- An experiment that would need unapproved credentials, production writes, sensitive data or wider permissions is refused with the boundary reported.
- Temporary state is cleaned by default; retention is explicit and never promotes prototype code into production source.
- The capability adds no branch, issue, progress file, status or second backlog, and introduces no prototype-specific registry/config/update lifecycle — it consumes the #87 optional-capability lifecycle only.
- Structural validation and the capability eval decision pass.

## Non-goals

- Implementing a concrete Planner prototype or any other specific experiment.
- A new issue tracker, progress file, or status model.
- Automatic acceptance of a product decision from an experiment.
- Permanent retention of experimental code as production source.
