# Design: Cold observations, exact evidence

## Current baseline

At the prepared revision, `model-routing` already owns truthful execution-efficiency evidence and read-only context delegation. Context delegation acts before selected bulk repository payload reaches the parent. This change addresses a separate stage: observations already returned into a live run.

## Decisions

1. **Preserve original evidence.** Eligible large observations are stored exactly for the supported run/session lifetime before a compact live representation may replace them.
2. **Stable handle, bounded hot representation.** The live representation contains a stable handle plus bounded metadata such as source/type, original size and excerpt. It is not a semantic source of truth.
3. **Exact targeted recall.** Recall resolves against the stored original and returns only the requested exact bounded portion unless the caller explicitly needs the full payload.
4. **Soft eligibility first.** V1 uses configurable/evidence-driven eligibility and does not copy a paper-specific byte threshold as universal policy.
5. **Fail open.** Archive/recall failure never silently drops evidence; the current full observation remains available or the operation reports an actionable fallback.
6. **Reuse provenance.** Source bytes/lines, hot bytes/lines, recall volume, trigger count/intensity and supported runtime usage attach to existing bounded execution-efficiency evidence. No transcript warehouse is introduced.
7. **Provider-neutral contract.** Provider-specific tool/runtime mechanics stay in adapters; the platform contract is observation identity, preservation, compact reference and exact recall.
8. **No durable memory semantics.** Observation storage is run/session-local infrastructure, not cross-task memory, OpenSpec state or project context.

## Verification

Use controlled small and large observations. Prove that large observations can become cold without content loss, exact targeted recall returns byte-for-byte expected content, small observations stay unchanged, unsupported/failure paths preserve evidence, and payload metrics do not masquerade as measured token usage.
