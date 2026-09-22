# Proposal: Bridge a pre-cutover legacy baseline into Copier's mirror cache during rollout

## Why

The first real post-cutover `Roll Out Platform` run for a managed project still on a pre-cutover baseline tag failed: Copier resolves its template source through its own local mirror cache of the real canonical remote, which by design (fresh-history public cutover) never contains a tag older than the first canonical release. `copier update` cannot compute its 3-way diff without that old tag, so rollout is currently impossible for any project not already on a post-cutover version.

## What Changes

- Add `ensure_legacy_baseline_tag_available()` to `scripts/rollout_project.py`: resolves Copier's own mirror cache for a project's template source, narrows its `origin` fetch refspec so Copier's own periodic mirror refresh cannot prune an injected tag, then fetches the project's exact recorded baseline tag from a configured legacy repository into that same cache.
- Extend `ensure_platform_tag_available()` (used by guarded-recopy's baseline-equivalence comparison) with the same optional legacy fallback.
- Thread an optional `--legacy-repository` CLI flag through `rollout_project.py` to both call sites.
- Add the non-secret `DEV_PLATFORM_LEGACY_REPOSITORY` repository variable and pass it from `rollout.yml`.
- Document the mechanism in `docs/managed-rollout.md`.

## Success Evidence

A managed project still on a pre-cutover baseline tag can complete a real `copier update --vcs-ref <post-cutover version>` through the normal rollout path when `DEV_PLATFORM_LEGACY_REPOSITORY` is configured, with no `.rej` files and no manual `.copier-answers.yml` edits. A project already on a post-cutover baseline never triggers a legacy fetch. Nothing is pushed to, or rewritten in, the canonical or legacy repository; the combined objects exist only in the CI runner's local Copier cache.

## Dependencies

None. No change to `.copier-answers.yml` schema, `scripts/managed_projects.py`, or the private operator registry mechanism.
