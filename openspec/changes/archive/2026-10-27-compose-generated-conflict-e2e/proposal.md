## Why

The derived merge of declared generated files (`template/dev-platform/platform-manifest.json`) is covered by unit tests of its pieces: `_prepare` routing with a mocked derivation, `rederive_archived_specs` on a managed candidate, and the worker's handling of a mocked `_prepare`. No test runs a Requirement composition candidate through the queue worker with a real derived merge, although Compose PRs (#684 on 2026-10-22) are where operators had to merge main by hand. The composition branch of the derivation (owned manifest lookup, composition task-content identity before and after, fast-forward push) has no test at all.

## What Changes

- One end-to-end test in `tests/test_autonomous_integration_contour.py`: real git repositories (a bare remote, a Requirement composition with two archived children and a sealed manifest, a trusted default-branch checkout declaring the generated manifest and its generator), GitHub I/O faked at the queue's GitHub boundary. `publication_queue.worker` runs unmocked through `_prepare` and the real `prepare_derived_specs` / `rederive_archived_specs` to `merged`.
- Assertions: the merged head is a merge of the admitted head and main with the regenerated manifest; the composition task-content identity is equivalent before and after; no `update-branch`, no integration-repair or integration-merge job, no "Repair needed" comment.
- Spec: one scenario added to "Declared generated files are regenerated on integration".

## Impact

- `tests/test_autonomous_integration_contour.py` only; `openspec/specs/publication-queue/spec.md` (one scenario).
- No production code change unless the test proves a defect.
