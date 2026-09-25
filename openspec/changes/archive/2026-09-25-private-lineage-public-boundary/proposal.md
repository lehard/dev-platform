## Why

Private Backlog identifiers remain in current public managed archive provenance and older public review logs despite the combined report now running privately. Current public source can expose the identity of private tasks, and future managed archives would repeat it.

## What Changes

- Give a private managed task an opaque public lineage handle while its exact Issue mapping stays in its existing private Backlog Issue and ignored local execution state. Preserve exact authorized recovery and verification.
- Migrate current tracked historical archive and integration records without fabricating past verification results.
- Add bounded public source/output checks and audit mutable GitHub surfaces; remove confirmed affected old public Actions runs and sanitize public Issue text.
- Record that already published Git history remains reachable and is an accepted residual risk; do not rewrite published refs.

## Impact

Managed task intake, archive receipts, reconciliation, public distribution checks, and test fixtures change. The private Backlog remains the only durable exact task mapping; no additional store or public report is introduced.
