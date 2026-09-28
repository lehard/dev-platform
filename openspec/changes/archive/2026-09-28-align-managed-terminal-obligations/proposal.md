# Proposal: Align managed terminal obligations

## Why

Read-only publication status can report a managed task complete after exact merge while finish still must resolve linked process evidence or required cleanup. Historical evidence that is no longer accessible can block finish indefinitely without an auditable supported disposition.

## What Changes

- Derive full completion from exact merge and the remaining mandatory terminal obligations; expose confirmed merge independently.
- Share the process evidence terminal check between read-only status and finish.
- Allow an explicit, narrow, durable disposition for a demonstrably unavailable historical evidence reference, with actor and reason retained in the managed source Issue.
- Keep transient GitHub and permission failures pending and preserve exact merge proof.

## Success Evidence

Regression tests reproduce merged-but-process-evidence-blocked status and verify recovery after actual resolution or a valid explicit disposition. Checks distinguish 404 from transient failures, and cover cleanup pending status.

## Bounds

No second terminal ledger, silent skip, fabricated evidence restoration, or relaxation of exact PR merge and local reconciliation guarantees.
