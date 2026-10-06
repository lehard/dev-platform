## Why
After the developer hands off, review, repair and finalization must run without that session, on any machine (local, server or hybrid). A repair worker must not be able to write outside its candidate branch, which repository-wide tokens cannot enforce.

## What Changes
- The coordinator publishes jobs (kind, candidate, exact head, identity, attempt) as handoff-record entries.
- `lifecycle_worker.py work-next [--kinds ...]` claims one job with a head-bound, time-limited claim marker, runs it and posts the result; an expired or head-stale claim is reclaimable and a stale result is discarded.
- LLM execution runs in a disposable checkout of the exact head with no GitHub or publication credential in its environment; a deterministic harness validates any write result (fast-forward from the expected head, within candidate scope, no workflow or lifecycle-evidence edits) and performs the only push with an expected-head guard. Merge authority stays with the coordinator.

## Capabilities
### New Capabilities
- `lifecycle-workers`: job, claim and authority contract.

## Impact
New `lifecycle_worker.py`, coordinator job publication, disposable checkout reuse, delegation containment reuse.

## Outcome and Evidence
Tests prove claim exclusivity, expiry/reclaim, stale-result rejection, credential-free LLM environment, harness rejection of out-of-scope or non-fast-forward results, and that only the harness pushes.

## Non-goals
Specific review/repair semantics (pr-review-repair-gate), server provisioning.
