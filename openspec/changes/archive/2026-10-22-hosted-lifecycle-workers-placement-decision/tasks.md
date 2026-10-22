## 1. Observe

- [x] 1.1 Confirm the automatic triggers are live on `main` and observe the first hosted review of a real PR after its developer session ended (claim and result by a `gha-` worker, evidence push, queue outcome).
- [x] 1.2 Record duplicate-trigger, expired-claim, moved-head, advanced-`main` and failure behavior only as actually observed.

## 2. Record

- [x] 2.1 Extend `docs/engineering/hosted-lifecycle-workers.md` with the per-kind constraint record and the hosted-versus-minimal-local-fallback comparison.
- [x] 2.2 Record the placement decision per kind, naming the BR-433 basis for any kind left off the hosted path.
- [x] 2.3 Fix a defect the observation exposed within the existing contract with a regression test, or record it as friction.

## 3. Delivery

- [x] 3.1 Required platform checks, truthful verification, developer handoff.
