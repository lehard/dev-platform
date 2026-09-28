# Proposal: Add an evidence-preserving reducer for execution logs

## Why

Execution logs are often large but semantically sparse. Replaying them verbatim wastes live-context budget, while an unchecked model summary can hide or invent the evidence used for diagnosis and verification.

After the large-observation lifecycle exists, Dev Platform can reduce selected logs without changing which artifact is authoritative.

## What Changes

- Preserve supported test/build/CI/command logs as exact cold observations.
- Allow an optional routine-profile reducer to create a compact structured receipt for noisy logs.
- Bind receipt claims deterministically to the original observation through source identity/digest, exact quote/range validation and structured command/exit fields where available.
- Prefer deterministic parsing when a log format already provides reliable structure; use model reduction only for semantic extraction that remains.
- Reject or fall back from unverified reducer output rather than treating it as evidence.
- Reuse existing execution/routing provenance for reducer identity, payload reduction, fallback and exact usage where supported.

## Capabilities

### Modified Capabilities

- `model-routing`: bounded execution/context-efficiency evidence may include verified reducer receipts whose authority remains the preserved source observation.

## Impact

- Execution-log handling and context efficiency.
- Verification/diagnosis evidence references.
- No change to the pass/fail authority of tests, CI or completion lifecycle.
