## 1. Implement contract-first selection

- [x] 1.1 Grep tests and scripts for `platform_version = "source"` configs with a non-GitHub, non-PR or project-harness combination; update the design first if any real use is found.
- [x] 1.2 Add `PlatformConfigError` and `lifecycle_mode(config)` to `template/scripts/_platform_common.py` (portable / coordinator / named error; no defaults masking a missing `platform_version`).
- [x] 1.3 Make `openspec_lifecycle.archive_change` call the selector before importing `pr_review_gate`; portable mode never imports it.
- [x] 1.4 Reorder `pr_review_gate.managed_candidate` so the selector precedes `resolve_canonical_provenance`.
- [x] 1.5 Make `execute_requirement._contribution_publication_supported` use the selector and raise for an unsupported source combination.
- [x] 1.6 Keep `scripts/` mirrors identical to `template/scripts/` for every touched file and report (not change) the pre-existing `ImportError` stubs and `publication_queue.enabled` bootstrap.

## 2. Verify behavior

- [x] 2.1 Add `tests/test_downstream_boundary.py`: downstream archive in a copied-`template/scripts` checkout with `pr_review_gate`, `publication_queue`, `lifecycle_workers` made unimportable completes the archive path.
- [x] 2.2 Add cases: two active managed packages under a downstream contract (`managed_candidate` is `False`, no exception); same checkout under the supported source contract still raises the ambiguity error.
- [x] 2.3 Add selector cases: downstream; supported source; source+gitlab, source+direct, source+project harness each raise a named error; missing `platform_version` raises.
- [x] 2.4 Add Requirement lifecycle cases: portable `_contribution_publication_supported` is `False`; unsupported source raises; `execute_requirement`, `requirement_terminal` import with the coordinator modules blocked.
- [x] 2.5 Run existing source suites (`test_pr_review_gate`, `test_openspec_lifecycle`, `test_requirement_execution`, `test_publication_queue`) and `python3 scripts/run_test_groups.py --all`; run semantic OpenSpec verification and write a truthful verification.md.

## 3. Deliver through managed lifecycle

- [x] 3.1 Resolve the developer friction checkpoint and publish through the managed lifecycle.
- [x] 3.2 Complete coordinator handoff or terminal archive/publication according to the authoritative lifecycle state.
