## 1. Derived merge
- [x] 1.1 Generalize `rederive_archived_specs` into a derived merge that also regenerates declared generated files from the trusted default-branch root; allow candidates without archived deltas.
- [x] 1.2 Extend `derived_merge_only` to declared generated paths.

## 2. Queue preparation
- [x] 2.1 In `publication_queue._prepare`, route a merge whose conflicts are only derived paths, or a both-sides change of a declared generated file, to the derived merge; keep `update-branch` and integration repair otherwise.
- [x] 2.2 Document the behaviour where queue integration bookkeeping is described.

## 3. Verification
- [x] 3.1 Regression tests: manifest-only conflict integrates with a regenerated manifest that passes `--check`; ordinary-file conflict goes to integration repair; regeneration failure goes to integration repair; unrecorded-update recovery accepts a generated-only merge; no candidate code runs for regeneration.
- [x] 3.2 Run full validation and semantic OpenSpec verification.
