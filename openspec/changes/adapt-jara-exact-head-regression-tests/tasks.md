# Tasks

## 1. Implement reviewed compatibility

- [x] 1.1 Record the current Jara #73 CI failure and reviewed fingerprints: the three strict mocks lack `git rev-parse` and exact-PR-list responses; `scripts/merge_to_main.py` is `a201795ddc3785630e789e409e510a471a8b848699014a815f461a0a2a38d91d` and `scripts/tests/test_merge_to_main.py` is `756c1b87df8c4abb2e4539785998e07e87bd6bf8f617cb3234908db5368537a4`.
- [x] 1.2 Add deterministic Jara test-surface adaptation with companion publication migration.
- [x] 1.3 Prove idempotence, partial-known recovery, and fail-closed unknown drift.

## 2. Verify and deliver

- [x] 2.1 Run CLI and rollout compatibility regression coverage plus full platform checks.
- [ ] 2.2 Archive the verified change and release the next patch.
- [ ] 2.3 Confirm the replacement Jara rollout is green without merging #73, Planner #46, or Cuby #57.
