## Context
`add_intents.validate_add` compares `prepared_against` to the current HEAD. `project_evidence` already tracks per-source blob identities, and handoff staleness re-checks ADD/intents/snapshot. `execute_requirement._ordered_handoffs` requires `current_stage == complete` from `orchestrate_pre_authoring.status` on every advance.

## Decisions
1. ADD freshness: fresh when the recorded snapshot evidence is still provably fresh (source identities unchanged) even if HEAD moved; `prepared_against` stays as provenance. Stale only when a bound source changed or the snapshot cannot be proven.
2. Post-materialization: when every handoff has a linked child (materialized), advance and terminal reconciliation derive the child order from the linked children and recorded handoff digests without requiring a fresh pre-authoring status. Missing children still require fresh handoffs. A contract conflict surfaced by a child remains an explicit stop.
3. Retry: `run_github_with_retry` classifies transient failures from stderr/exit (connection reset, TLS handshake timeout, EOF, HTTP 5xx, secondary rate limit) with bounded exponential backoff (default 4 attempts, overridable); non-transient errors return immediately. Only read calls are retried; mutations are never retried automatically.

## Risks and Mitigations
Accepting HEAD movement could hide a relevant change: freshness still requires every bound source identity to match. Retrying a non-idempotent mutation could duplicate it: mutating calls run once and callers re-observe state before deciding on another operation.

## Verification
Unit tests for ADD freshness with unrelated vs bound-source commits, post-materialization advance/terminal without fresh pre-authoring, retry classification and bounds; regression for BR-341/BR-354 terminal path.
