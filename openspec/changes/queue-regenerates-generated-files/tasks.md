## 1. Derived merge
- [x] 1.1 Generalize `rederive_archived_specs` into a derived merge that also regenerates declared generated files from the trusted default-branch root; allow candidates without archived deltas.
- [x] 1.2 Extend `derived_merge_only` to declared generated paths.

## 2. Queue preparation
- [x] 2.1 In `publication_queue._prepare`, route a merge whose conflicts are only derived paths, or a both-sides change of a declared generated file, to the derived merge; keep `update-branch` and integration repair otherwise.
- [x] 2.2 Document the behaviour where queue integration bookkeeping is described.

## 3. Identity exclusion (owner decision 2026-10-22)
- [x] 3.1 Require `check` in each `[[generated_files]]` entry and require it in `[settings].full_commands`; explicit error otherwise. Declare the manifest check in `dev-platform/checks.toml` and add it to `full_commands`.
- [x] 3.2 Exclude declared generated paths, read at `merge-base(HEAD, origin/<main>)`, in `review_exclusion`, used by review and composition identity.
- [x] 3.3 Tests on an archived candidate: manifest-only regeneration keeps identity and gates; a manifest change plus an ordinary task path changes identity; a declaration present only in the candidate is ignored; a declaration whose check is not in `full_commands` fails explicitly.

## 4. Verification
- [x] 4.1 Regression tests: manifest-only conflict integrates with a regenerated manifest that passes `--check`; ordinary-file conflict goes to integration repair; regeneration failure goes to integration repair; unrecorded-update recovery accepts a generated-only merge; no candidate code runs for regeneration.
- [ ] 4.2 Run full validation and semantic OpenSpec verification.
