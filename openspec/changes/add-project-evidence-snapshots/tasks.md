# Tasks

## 1. Define snapshot contracts
- [x] Define versioned manifest/projection schemas and source identity rules.
- [x] Define projection dependency/invalidation semantics and stable digests.
- [x] Document authority boundary versus OpenSpec, `docs/context/`, AGENTS and code/tests.

## 2. Implement deterministic inventory and freshness
- [x] Inventory bounded canonical sources at an exact revision.
- [x] Use Git blob/content identity where available.
- [x] Implement projection hit, partial invalidation and stale detection.
- [x] Add deterministic schema/provenance/digest validation.

## 3. Compose routine semantic workers
- [x] Reuse existing routine/read-only context delegation rather than a new router.
- [x] Define bounded projection requests/results with facts, evidence refs, conflicts and unknowns.
- [x] Add truthful escalation for conflict/low-confidence cases.
- [x] Keep workers read-only and non-authoritative.

## 4. Expose snapshot consumers and evidence
- [x] Provide stable snapshot/projection references suitable for ADD/Intents and future #123 use.
- [x] Record bounded hit/rebuild/worker/escalation/timing evidence via existing provenance where practical.
- [x] Avoid raw transcripts and unsupported usage guesses.

## 5. Verify
- [x] Test hit with zero model work, partial invalidation, full invalidation, stale revision and conflict escalation.
- [x] Add representative routine-worker behavioral evidence and no-unnecessary-read negative case.
- [ ] Record the semantic OpenSpec review/receipt and archive through the supervisor lifecycle after its final review.
