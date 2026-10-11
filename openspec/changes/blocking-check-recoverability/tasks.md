## 1. Catalog and helper

- [x] 1.1 Add `template/dev-platform/blocking-gates.toml` schema and the shared failure helper in `_platform_common.py` (catalog id required, class and recovery/justification printed, non-zero exit, no default).
- [x] 1.2 Platform test: catalog well-formed, recoverable entries name a recovery step and tests, hard-stop entries carry justification, helper use with an unknown id fails, acceptance tests resolve.

## 2. Inventory and migration

- [x] 2.1 Inventory existing blocking gates, including those named in the Requirement, classify each with its current recovery or hard-stop justification, and record follow-ups for gaps instead of redesigning gates.
- [x] 2.2 Move the inventoried gates onto the helper with unchanged exit conditions, except the shell `pre-merge-commit` hook (it cannot call the Python helper and its modification is a sensitive protected-surface edit left to an explicit owner decision); add rejection and recovery acceptance tests per gate.

## 3. Protected-surface negative tests

- [x] 3.1 Tests that hotfix and recovery paths cannot disable independent review, protected publication, worktree isolation, credential limits, routing/provenance/evidence authenticity, history protection or immutable releases, and that no force option exists.

## 4. Documentation and delivery

- [x] 4.1 Document failure classes in `change-classes.md`; Copier render/update coverage for the new files.
- [ ] 4.2 Required platform checks, truthful semantic verification, archive, retrospectives, publication.
