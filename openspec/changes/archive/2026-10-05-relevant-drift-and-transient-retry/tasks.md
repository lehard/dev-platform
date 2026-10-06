## 1. Source-bound freshness
- [x] 1.1 Make ADD/intents/handoff freshness depend on bound source identities rather than exact HEAD equality, keeping provenance.
## 2. Post-handoff independence
- [x] 2.1 Let advance and terminal reconciliation use materialized children without requiring fresh pre-authoring; keep explicit conflict stops.
## 3. Transient retry
- [x] 3.1 Add a shared bounded transient GitHub retry and apply it to advance, terminal reconciliation and the publication queue.
## 4. Verification
- [x] 4.1 Run relevant tests, the affected precheck and required platform checks; perform semantic OpenSpec verification and independent review; record truthful verification evidence.
- [x] 4.2 Archive and commit through the lifecycle helper; complete the child retrospective and hand off for shared Requirement publication.
