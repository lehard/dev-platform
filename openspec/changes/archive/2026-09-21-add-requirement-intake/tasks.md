# Tasks

## 1. Requirement representation
- [x] Define the Requirement body template (Outcome/Context/Acceptance evidence/Target repository/Exclusions) and the children-block marker format.
- [x] Define the `requirement-<N>` identity slug, compatible with orchestrate_pre_authoring.py's id shape.

## 2. Entrypoint
- [x] Implement `create`: author a Requirement Issue with no OpenSpec artifact.
- [x] Implement `start`: bridge a Requirement into `orchestrate_pre_authoring.py init`.
- [x] Implement `link-child`: idempotent parent/child linkage plus label/back-reference.
- [x] Implement `aggregate`: read-through status derived only from linked children's real Project status.

## 3. Main-board visibility
- [x] Add `type:requirement` / `type:internal-change` labels (idempotent creation).
- [x] Document the one-time manual Project-filter step the owner adds.

## 4. Verify
- [x] Unit-test body render/parse round-trip and children-block idempotency.
- [x] Unit-test `aggregate`'s derived-status rules against mocked child observations.
- [x] Unit-test `start` composes the correct orchestrate_pre_authoring.init() call from a parsed Requirement body.
- [x] Confirm no new backlog/status/Project schema beyond the two labels.
- [x] Verify source/template parity and semantic OpenSpec completion.
