# Design: Legacy baseline bridge for rollout

## Root cause, confirmed empirically

Reproduced the failure live: dispatched `Roll Out Platform` for `lehard/planner-agent-lab` (`v1.4.38 -> v1.5.1`) against the real `lehard/dev-platform`; it failed with `fatal: invalid reference: v1.4.38` from `git worktree add --detach --force <tmp> v1.4.38` against Copier's own mirror cache at `~/.cache/copier/git/<sha256(url)>.git`. Confirmed the exact cache-path algorithm by calling `copier._vcs.get_repo`/`_get_mirror_path` directly against `gh:lehard/dev-platform` and matching the hash in the failure log byte-for-byte. Reproduced a full local fix end-to-end (real `git`, real `copier`, real `lehard/dev-platform-legacy`) before writing any workflow change.

## Why a naive tag injection does not work

`copier._vcs._get_or_create_mirror()` refreshes an existing mirror via `git remote update --prune`. A `--mirror` clone's default fetch refspec is `+refs/*:refs/*`, so `--prune` deletes any ref not currently on the real remote -- including a manually injected legacy tag -- the very next time Copier (or anything else) touches that cache. Verified this failure mode locally first, before finding the fix.

## Fix

`ensure_legacy_baseline_tag_available(project_root, *, legacy_repository, version)`:

1. No-op if `legacy_repository` is not configured.
2. Resolve the project's template source URL (`copier._vcs.get_repo(answers["_src_path"])`) and its mirror path (`copier._vcs._get_or_create_mirror(url)`) -- the exact same private APIs Copier itself uses, so the cache is shared rather than duplicated.
3. No-op if the recorded baseline tag already resolves in that mirror (a project already on a post-cutover release never touches the legacy repository).
4. Narrow the mirror's `origin` fetch refspec to `+refs/heads/*:refs/heads/*` plus `+refs/tags/<version>:refs/tags/<version>` (the exact version this rollout run needs from the real canonical remote) -- proven locally to survive a subsequent `git remote update --prune`.
5. Fetch only the recorded baseline tag from `legacy_repository`, with `--no-tags` (bounded: no unrelated tag import).

`ensure_platform_tag_available()` (used by guarded-recopy's separate baseline-equivalence comparison, which clones `PLATFORM_ROOT` as a local path rather than through Copier's mirror cache) gets the same optional fallback: try the real canonical `origin` first (existing behavior, unchanged for anyone not configuring this), then the legacy repository.

Both changes take the same new optional `legacy_repository: str | None = None` parameter, defaulting to today's exact behavior when unset -- no behavior change for a checkout that does not configure it.

## Configuration

`DEV_PLATFORM_LEGACY_REPOSITORY`: non-secret repository variable, `owner/name`, generic (never hardcoded in workflow or Python source, exactly like `DEV_PLATFORM_OPERATOR_REPOSITORY`). `rollout.yml`'s rollout job reads it and passes `--legacy-repository` only when set; unset behaves exactly as before this change (rollout still works for any project already on a post-cutover baseline, and still fails with today's plain error for one that is not).

## Explicitly out of scope

- Any change to `.copier-answers.yml` schema or content, or to `scripts/managed_projects.py`/the private operator registry.
- A general "multi-source template" framework: this is one bounded fallback, gated behind one optional flag, reusing Copier's own existing cache mechanism rather than building a parallel one.
- Adopt Project's onboarding path: it never invokes `copier update` for an already-adopted repository (confirmed by reading `scripts/adopt_project.py`), so it needs no change here.
- Restoring the mirror's `origin` fetch refspec after the bridge runs: the narrowed refspec is never widened back. This is safe today because `rollout.yml`'s matrix runs each fetch fresh `ubuntu-latest` runners with no persisted `~/.cache/copier` (verified: no `actions/cache` step targets it). If a future change adds caching across rollout runs for that same template source, this narrowing would need to be revisited first.

## Tests

`tests/test_rollout_recopy.py::LegacyBaselineBridgeTests`: no-op without configuration; no-op when the tag already resolves; correct refspec-narrowing and fetch commands when it does not (mocking `copier._vcs.get_repo`/`_get_or_create_mirror` and the module's own `run`/`subprocess.run`, matching this file's existing mocking style); `ensure_platform_tag_available`'s fallback and its combined-failure error message. `tests/test_managed_rollout.py`: workflow-content assertions that `rollout.yml` reads the new variable and threads the flag.
