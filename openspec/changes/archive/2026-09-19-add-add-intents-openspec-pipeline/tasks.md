# Tasks

## 1. Define ADD and Intent contracts
- [x] Add provider-neutral ADD/intents capability guidance and template counterpart.
- [x] Define ADD semantics as system-design delta relative to current accepted evidence.
- [x] Define Intent semantics as atomic decomposition output from approved ADD and normalized input to OpenSpec authoring.
- [x] Define clear-change bypass and greenfield baseline behavior.
- [x] Update selective-domain-interrogation guidance for composition without making it the ADD/intents owner.

## 2. Implement structured ADD representation and checks
- [x] Add one compact versioned ADD schema/model.
- [x] Bind requirement identity, exact revision, bounded evidence and evidence freshness/integrity.
- [x] Separate reused current-system constraints from new/changed ADD elements.
- [x] Represent contradictions, assumptions, unresolved choices and accepted resolutions.
- [x] Add deterministic validation for schema/provenance/freshness/unresolved blockers without claiming semantic completeness.

## 3. Implement ADD construction and approval
- [x] Perform bounded evidence-first discovery against accepted OpenSpec, relevant active deltas, project context when available, and scoped code/tests.
- [x] Prevent already-established decisions from being presented as new.
- [x] Produce only material system-design delta.
- [x] Compose with selective-domain-interrogation for unresolved consequential choices.
- [x] Support bounded human review/approval and clear-change bypass.

## 4. Implement Intent decomposition
- [x] Add a versioned intent-set/intent representation.
- [x] Decompose approved ADD into atomic bounded intents with scope/non-goals and dependencies.
- [x] Keep the raw business requirement available for goal/context while forbidding silent architecture re-discovery/re-design at decomposition time.
- [x] Link each material ADD element to an intent or explicit non-implementation disposition.
- [x] Add structural gates for IDs/linkage/dependency graph/coverage references/readiness.
- [x] Return material missing-design gaps to ADD refinement.

## 5. Implement Intents → OpenSpec authoring handoff
- [x] Make atomic intents available as structured input to the normal OpenSpec proposal authoring path.
- [x] Carry business context and ADD/evidence references without re-running broad discovery.
- [x] Use the existing OpenSpec split test for intent→change mapping; avoid inventing another lifecycle rule.
- [x] Detect material conflict with approved ADD and route back to refinement instead of silently changing architecture.
- [x] Keep ordinary managed-task materialize/start/verify/archive semantics unchanged.

## 6. Reference-driven verification
- [x] At execution time inspect the supplied `intents-bundle.tar.gz` and author transcript as reference-only context before finalizing the detailed implementation.
- [x] Do not vendor/copy reference code or provider/corporate/domain assumptions.
- [x] Add representative evals for business requirement → ADD, ADD approval → intents, structural coverage/atomicity/dependencies, and intent → OpenSpec handoff.
- [x] Add negative evals for existing-decision reuse, missing design returned to ADD, stale evidence, and clear-change bypass.
- [x] Verify source/template parity, capability descriptor/hash/audit as applicable, focused platform checks, and semantic OpenSpec verification through normal lifecycle.
