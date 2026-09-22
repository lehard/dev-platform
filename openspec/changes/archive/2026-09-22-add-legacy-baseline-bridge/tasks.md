# Tasks

## 1. Bridge implementation
- [x] Add `ensure_legacy_baseline_tag_available()` using Copier's own mirror-cache internals.
- [x] Narrow the mirror's `origin` fetch refspec before injecting the legacy tag, so Copier's own refresh cannot prune it.
- [x] Extend `ensure_platform_tag_available()` with the same optional legacy fallback.
- [x] Thread `legacy_repository` through `rendered_template_fingerprints`/`baseline_equivalent_conflict_paths`/`copier_update_with_guarded_recopy`/`apply_rollout`/`main()` as `--legacy-repository`.

## 2. Workflow wiring
- [x] Add `DEV_PLATFORM_LEGACY_REPOSITORY` repository variable.
- [x] `rollout.yml`: pass `--legacy-repository` to `rollout_project.py` only when configured.

## 3. Documentation
- [x] `docs/managed-rollout.md`: document the mechanism and the variable.

## 4. Verify
- [x] Unit-test the bridge's no-op/already-present/narrow-and-fetch paths and `ensure_platform_tag_available`'s fallback.
- [x] Workflow-content contract test for `rollout.yml`'s new variable/flag threading.
- [x] Full test suite green.
- [x] Verify source/template parity and semantic OpenSpec completion.
