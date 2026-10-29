## 1. Runner
- [x] 1.1 Add `scripts/post_merge_runner.py`: argument validation, single-instance lock, rate-limit guard, bounded work-next loop, journal, interrupted-round detection, `journal` reader.
- [x] 1.2 Add `launchagent` render/install/remove (explicit paths, 600 s interval).
- [x] 1.3 Document owner install and rollback in `docs/engineering/hosted-lifecycle-workers.md`; update platform manifest and test-group classification.

## 2. Verification
- [x] 2.1 Tests with a fake `work-next` and fake `gh`: chain to idle, max-jobs/duration bounds, first failure stops, low remainder skip (start and between runs), lock contention, interrupted round, missing config/credential errors, journal content, plist content, install/remove guard.
- [x] 2.2 Dry check against real GitHub with `--dry-run` work-next (no claims) and `launchagent --print`; do not install.
- [x] 2.3 Run full validation and semantic OpenSpec verification.
