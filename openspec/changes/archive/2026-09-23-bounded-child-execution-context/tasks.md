# Tasks

## 1. Contract

- [x] Specify the bounded canonical child context and its dependency freshness rules.
- [x] Identify child start/resume entrypoints and exact source provenance.

## 2. Implementation

- [x] Build and validate the derived child handoff from managed package and repository state.
- [x] Require exact canonical parent backlinks when materializing and starting dependent children.
- [x] Wire it to child execution without a second durable ledger or provider-specific transcript.

## 3. Verification

- [x] Test exclusion of pre-authoring transcript and unrelated sibling bodies, plus stale dependency refresh.
- [x] Run affected and full platform checks, semantic OpenSpec verification, and archive with truthful receipt.
