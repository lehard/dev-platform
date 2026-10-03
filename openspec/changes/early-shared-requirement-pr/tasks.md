# Tasks

- [x] Extend the shared manifest with `expected_changes` and a derived `complete` flag, with append-only history validation (child commits plus bind commits) and a one-child incomplete candidate.
- [x] Make `compose_candidate` and `publish_candidate` append to an existing candidate and publish a draft PR for an incomplete manifest, resuming an existing PR by branch without duplicates.
- [x] Make `project_publish.py` refuse ready, merge arming and queue admission for an incomplete manifest, and mark the same PR ready for a complete one.
- [x] Make `execute_requirement.py advance` publish or update the draft after each ready child, require the retrospective checkpoint only for the complete publication, and keep terminal reconciliation gated on exact merge and all mandatory children.
- [x] Add regression tests for early draft, append to the same PR, incomplete-candidate gates, divergent/changed-head blockers, and interrupted rerun without duplicate; update `docs/engineering/task-intake.md`.
- [x] Run focused and full validation, semantic OpenSpec verification, independent review; record truthful evidence and archive.
