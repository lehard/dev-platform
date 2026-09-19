# Design: ADD → Intents → OpenSpec

## 1. Pipeline boundary

The architecture is intentionally three-stage:

```text
Business requirement
  → ADD: what must change in the system design?
  → Intents: what atomic bounded outcomes must be specified?
  → OpenSpec: what exact change contract will be implemented and verified?
```

These stages are not interchangeable.

### ADD responsibility

ADD compares the requirement with current accepted system evidence and records only the design delta:
- new/changed capabilities and boundaries;
- integrations/contracts;
- data ownership/persistence/migration implications;
- invariants/domain rules;
- security/trust/privacy;
- material NFR consequences;
- preserved constraints/non-changes;
- assumptions, contradictions, unresolved choices and accepted resolutions.

Existing decisions are referenced, not restated as new choices.

### Intent responsibility

An intent is the decomposition product of an **approved ADD**. It captures one bounded business/system outcome suitable for OpenSpec authoring. It carries:
- stable local identity;
- goal/outcome;
- scope and non-goals;
- relevant ADD element references;
- dependency references to other intents;
- constraints/evidence references needed by authoring;
- explicit unresolved blocker only when decomposition cannot proceed safely.

It does not contain file-level steps and must not introduce new architecture behind the ADD.

## 2. Structured representations

Use compact versioned structured representations for ADD and intent set. Prefer dependency-light formats already comfortable for platform tooling.

ADD should bind:
- requirement identity/digest;
- target repository + exact revision;
- consulted evidence + immutable identity/hash where feasible;
- reused current-system constraints;
- new/changed design elements with stable IDs;
- contradictions/assumptions;
- unresolved and accepted material choices;
- limitations/freshness metadata.

Each intent should bind:
- intent ID;
- parent ADD identity;
- source business goal/context reference;
- bounded outcome;
- scope/non-goals;
- covered ADD element IDs;
- dependencies;
- relevant constraints/evidence refs;
- readiness/blocker state sufficient for pre-authoring validation.

No reasoning transcript is stored.

## 3. ADD approval and human checkpoint

Use existing `selective-domain-interrogation` behavior for consequential ambiguity. Evidence-resolvable facts never become user questions. Related material choices should be grouped into a bounded checkpoint where practical.

ADD is approved only when no consequential unresolved choice remains.

## 4. Decomposition rules

Intent decomposition uses the approved ADD as the authoritative design input for that run. The raw requirement remains available for business purpose/context but is not a second source for re-deciding architecture.

Decomposition should optimize for:
- atomic, independently specifiable outcomes;
- complete structural linkage back to material ADD elements;
- explicit dependencies;
- minimal overlap;
- no hidden redesign.

If a missing decision prevents clean decomposition, return to ADD refinement.

## 5. Validation model

Deterministic checks may prove:
- schema/version validity;
- required identities/references;
- exact revision and evidence freshness/integrity;
- dependency graph validity;
- referenced ADD IDs exist;
- every required ADD element has an intent/non-implementation linkage;
- no unresolved blocker is marked ready.

Semantic quality such as whether the ADD itself is correct or whether decomposition is the best possible partition requires targeted agent/human review and representative evals; deterministic tooling must not overclaim it.

## 6. Intent → OpenSpec mapping

Default expectation: one atomic intent is a strong candidate for one OpenSpec change. This is not a second hard-coded lifecycle rule. The existing OpenSpec split test remains authoritative:
- independent outcome → separate change;
- truly inseparable outcomes → cohesive grouped change.

OpenSpec authoring receives intent + business context + referenced ADD/evidence. It may add implementation detail in `design.md`, but a material design conflict returns to refinement.

## 7. Lifecycle/source-of-truth boundary

ADD and intents are bounded pre-authoring evidence. They may live in machine-local/ignored resumable state or another non-authoritative authoring surface. Do not create a permanent registry, board, or lifecycle.

Once managed OpenSpec is materialized, OpenSpec owns implementation and verification. After archive, accepted OpenSpec + implementation/current project context form the next baseline. No bidirectional ADD/intent synchronization is required.

## 8. Greenfield

For greenfield, select stack and create the skeleton first. Build the initial accepted OpenSpec baseline from intended requirements plus the actual skeleton. ADD then applies incrementally to later requirements. Do not create an upfront classical ADR catalog merely to initialize the project.

## 9. Relationship to adjacent capabilities

- `selective-domain-interrogation`: resolves material ambiguity; does not own ADD/intents lifecycle.
- project context pack (#120): optional evidence source.
- context learning loop (#121): future context-quality improvement.
- goal-driven scans (#123): separate broad/exhaustive analysis capability.

## 10. Reference implementation boundary

At execution time, inspect the user-provided `intents-bundle.tar.gz` and transcript as reference material. Preserve the conceptual staging and semantics they actually support, especially ADD/ADR approval → intent decomposition → downstream specification input. Do not vendor/copy code or corporate/provider/domain assumptions.
