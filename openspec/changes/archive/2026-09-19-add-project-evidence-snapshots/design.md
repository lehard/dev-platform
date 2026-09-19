# Design: Reusable Project Evidence Snapshots

## Architecture

Use a small manifest bound to repository/revision plus compact independently invalidatable projections. Persist source identities using Git blob/content hashes when available; avoid mtime as the primary truth signal.

Initial projection concerns:
- accepted/current OpenSpec and applicable active changes;
- topology/components/boundaries;
- integrations/contracts/data ownership;
- rules/invariants/constraints;
- project/domain context;
- conflicts/unknowns.

A projection stores conclusions and bounded evidence references, never raw chain-of-thought or bulk source copies.

## Build path

1. Deterministically inventory candidate sources and identities.
2. Compare against prior projection dependencies.
3. Reuse fresh projections with zero model calls.
4. Rebuild only invalidated projections.
5. Use routine/read-only semantic workers by default for extraction.
6. Escalate only conflict, low confidence, or materially complex interpretation.
7. Deterministically validate schema, source linkage, revision/freshness and digest.

Do not build a new scheduler. Parallelism may use provider-native workers when available.

## Consumer boundary

Consumers bind to stable snapshot/projection digests and requested concern views, not to a giant always-loaded context blob. `docs/context/`, OpenSpec, AGENTS, code/tests and engineering docs remain canonical according to their existing ownership.

## Efficiency evidence

Record bounded hit/partial/full rebuild, routine-worker count, escalation count/reason, elapsed time and only supported usage metrics. Reuse existing routing/context-worker provenance instead of a new telemetry backend.

## Reference

Re-check the supplied Intents reference bundle/transcript at implementation time for snapshot staging/freshness semantics. Adapt concepts clean-room; do not vendor implementation or corporate/provider assumptions.
