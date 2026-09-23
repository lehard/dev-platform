# Tasks

## 1. Contract

- [x] Define the canonical input and terminal publication gate for board projection.
- [x] Specify stage mapping, precedence and drift behavior.

## 2. Implementation

- [x] Add source-owned Requirement board reconciliation through the existing Project adapter.
- [x] Wire reconciliation into Requirement execution and terminal delivery without a second status ledger.
- [x] Document the human-facing semantics and recovery behavior.

## 3. Verification

- [x] Test nonterminal, blocked/unknown, drift, idempotence and protected Done cases.
- [x] Run affected/full checks, semantic verification and archive with truthful receipt.
