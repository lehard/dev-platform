# Proposal: Recover a shared Requirement candidate after main advances

## Why

The first #164 candidate was composed at main `f40baaf` and passed child verification. An unrelated protected PR advanced main before first publication. The shared supervisor currently requires each old child head to descend from current main and has only one fixed candidate branch, so it cannot safely retry.

## What changes

Allow a new base-bound candidate generation after authoritative main changes. The new generation reuses exact archived child receipts and deltas, checks their branch heads, applies them to current main without rewriting the children, validates the combined tree and uses the unchanged protected publisher. Make the candidate receive the integration checkout's ignored local source contract for validation. Preserve prior generations untouched.

## Success evidence

Git-backed tests demonstrate resume from a moved main, deterministic generation identity, preservation of old candidate and fail-closed conflicts; #164 reaches an exact merged PR with full checks and terminal board reconciliation.

## Risks and bounds

This is a publication safety boundary. A patch conflict, changed child head, divergent source contract, occupied generation, or failed validation blocks; no reset, force push or manual PR fallback is permitted.
