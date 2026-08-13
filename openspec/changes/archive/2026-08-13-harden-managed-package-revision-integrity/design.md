# Design: Revision-safe managed package lifecycle

## Principles

1. **Exact-state validation.** `prepared_against` is evidence, not decoration. The semantic/structural authoring validation must observe the same target state.
2. **One active package revision.** Historical predecessor evidence may remain, but importer ambiguity is never accepted.
3. **Canonical-after-materialization.** The source Issue can signal human intent drift, but it never silently overwrites repository-local OpenSpec.
4. **Repair before execution, not a second planning system.** Supersede/repair is a narrow transport operation over the existing package format/revision model.
5. **No raw history warehouse.** Store only the bounded metadata needed to identify source-Issue revision and predecessor package revision.

## Authoring

Authoring first resolves current remote main and establishes an exact validation context for that SHA. A stale integration checkout must not be used while claiming the newer SHA as `prepared_against`. The implementation may validate in a temporary detached/worktree context or fail closed and require synchronization; it must not mutate integration main merely to validate a bundle.

The package records bounded source-Issue revision evidence. The preferred shape is deterministic and machine-comparable (for example GitHub `updated_at` plus a normalized body hash), without storing a second full Issue snapshot.

## Drift semantics

Before materialization, source-Issue drift means the accepted transport may no longer reflect current human intent. Start therefore stops with an actionable choice: author/supersede a reconciled package or explicitly confirm that the existing package remains the intended scope.

After materialization, local OpenSpec remains canonical. Status/finish may surface the source-Issue drift as bounded evidence, but they do not rewrite scope or block an already agreed implementation solely because the human-facing issue was edited.

## Supersede/repair

A supported command accepts a new authoring bundle for an existing source Issue, validates it against current exact target state, computes a new package revision, and only then makes it the single active package. It records a bounded predecessor revision link. Retries with the same revision converge.

The implementation should prefer the smallest compatible evolution of the existing GitHub comment/package mechanics. It must not create two simultaneously active `managed-openspec` packages that the importer cannot distinguish.

## Failure handling

Any ambiguity about active revision, source Issue identity, target repository, exact prepared-against state, or replacement validation fails closed before implementation/publication side effects.
