## 1. Define receipt and source binding

- [x] 1.1 Reconcile #131 observation identity/recall and current execution/check provenance.
- [x] 1.2 Define the smallest structured reducer receipt: source handle/digest, command/result fields, exact evidence spans/quotes, findings and uncertainty.
- [x] 1.3 Identify fields that should be parsed deterministically before any model reduction.

## 2. Implement reducer path

- [x] 2.1 Add reducer eligibility for supported noisy execution logs only.
- [x] 2.2 Use deterministic extraction first and optional routine-profile semantic reduction for the remainder.
- [x] 2.3 Verify receipt source binding, exact spans/quotes and structured exit/result consistency.
- [x] 2.4 Fail open to exact source evidence on unsupported runtime, reducer failure, low confidence or receipt-verification failure.

## 3. Preserve verification authority and evidence

- [x] 3.1 Ensure test/check/CI pass-fail and terminal completion never rely on reducer prose as canonical evidence.
- [x] 3.2 Reuse bounded execution provenance for reducer participant, source/receipt size, verification result, fallback/recall and supported usage.
- [x] 3.3 Keep unavailable canonical token/cache evidence unknown.

## 4. Regression coverage and delivery

- [x] 4.1 Cover long passing/failing logs, deterministic-only extraction, semantic reduction and exact source recall.
- [x] 4.2 Reject wrong digest, fabricated/mismatched quote/range and inconsistent exit-status receipts.
- [x] 4.3 Prove contradictory reducer output cannot satisfy a green verification path.
- [x] 4.4 Run platform-required checks and prepare the verified change for normal archive and publication.
