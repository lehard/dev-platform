## 1. Stabilize confirmed concurrent-test timing assumptions

- [ ] 1.1 Reproduce the lock/readiness flake from process issue #194 under concurrent load.
- [ ] 1.2 Reproduce/classify the contention-sensitive Codex tier probe from #215.
- [ ] 1.3 Replace fragile startup timing assumptions with explicit readiness where applicable and bounded environment-tolerant deadlines.
- [ ] 1.4 Preserve deterministic failure for a truly hung subprocess and avoid retry masking.

## 2. Make dogfood finish cleanup caller-safe

- [ ] 2.1 Reproduce the external deleted-cwd false failure from #197/#225.
- [ ] 2.2 Distinguish terminal delivery authority from post-delivery worktree cleanup.
- [ ] 2.3 Avoid synchronously deleting the caller's cwd when that would poison the parent runner; reuse/add bounded idempotent deferred cleanup.
- [ ] 2.4 Preserve current synchronous cleanup when it is safe.
- [ ] 2.5 Prove genuine merge/reconciliation/check failures remain non-zero.

## 3. Verification

- [ ] 3.1 Add regression coverage for #194, #215, #197 and #225.
- [ ] 3.2 Run the current authoritative risk-selected/full validation once against the combined final diff, avoiding redundant full-suite cycles.
- [ ] 3.3 Perform semantic OpenSpec verification and archive through the normal lifecycle.
