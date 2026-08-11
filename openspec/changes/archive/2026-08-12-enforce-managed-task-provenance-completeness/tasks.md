## 1. Map managed provenance surfaces

- [x] 1.1 Reproduce the `dev-platform#157` class using an existing managed branch/PR with missing or mismatched canonical OpenSpec state.
- [x] 1.2 Inventory current importer provenance markers, active/archive OpenSpec evidence and managed start/finish metadata that can deterministically identify the source Issue.
- [x] 1.3 Confirm the design preserves repository-local OpenSpec as canonical after materialization.

## 2. Add resume provenance guard

- [x] 2.1 Resolve source Issue plus canonical change identity for an existing managed branch/worktree.
- [x] 2.2 Accept matching active canonical changes and matching verified/archived changes.
- [x] 2.3 Fail closed on missing canonical change, same-name/different-source change or ambiguous historical state with actionable recovery guidance.
- [x] 2.4 Do not overwrite evolved repository-local OpenSpec from the original backlog package.

## 3. Add publication/completeness guard

- [x] 3.1 Re-check managed provenance before publication/terminal completion.
- [x] 3.2 Require existing task/verification/archive evidence appropriate to the lifecycle stage before terminal managed delivery.
- [x] 3.3 Detect unexplained direct current-spec edits when no matching canonical active/archive lineage exists.
- [x] 3.4 Preserve already-archived publication recovery without rematerialization.

## 4. Regression and delivery

- [x] 4.1 Cover active resume, archived resume, missing change, mismatched source, evolved canonical package, incomplete tasks and unexplained current-spec edits.
- [x] 4.2 Run full managed-task, lifecycle, template/Copier and strict OpenSpec validation.
- [x] 4.3 Record truthful semantic verification, archive and publish through the normal protected-main/immutable-release path if runtime/template behavior changes.
