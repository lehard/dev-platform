## 1. Queue contract and implementation

- [x] Implement durable exact-PR admission, ordering, status and idempotent recovery in the source lifecycle.
- [x] Implement a single GitHub-hosted coordinator that safely updates one candidate, waits for required CI on actual head, and merges with expected-head guard.
- [x] Add scheduled/event wakeup workflow and documented configuration/recovery; preserve bootstrap publication of this change.

## 2. Evidence and completion

- [x] Exercise multiple concurrent candidates, restart, normal main advancement, changed content, conflict, failed CI and external movement with representative tests.
- [x] Run required checks and semantic OpenSpec verification; record truthful receipt.
