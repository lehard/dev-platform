# Change: Allow safe recopy for historical platform rollout conflicts

## Why

The v1.4.13 managed rollout exposed a second-order Copier migration problem in Cuby. Cuby had temporarily carried a downstream `scripts/project_publish.py` override for a bug that is now fixed upstream. After Cuby was reconciled to the exact v1.4.13 template bytes, `copier update` still replayed the historical downstream diff and emitted `scripts/project_publish.py.rej`.

v1.4.14 added narrow recovery for that exact-target reclaimed file, but the real Cuby rollout exposed the broader safe case that Copier replay can also conflict on paths which have **not diverged at all** from the repository's recorded old platform template. The v1.4.14 attempt produced `scripts/finish_task.py.rej` even though Cuby's committed `finish_task.py` is byte-identical to the recorded v1.4.12 template, plus `tests/test_git_lifecycle.py.rej` where both Cuby and the v1.4.12 consumer template have no such path.

Those conflicts are also historical replay artifacts, not present downstream customizations. Leaving them unrecoverable means a platform-owned consumer can remain stuck even though the rollout can prove from immutable Git state that recopy would overwrite no independent downstream work.

## What changes

- Keep exact-target reclaimed-file recovery for migration cases such as `scripts/project_publish.py`.
- Additionally permit guarded recopy in `harness_mode=platform` when a conflicted downstream path is proven identical to that repository's **recorded current platform template** at committed `HEAD`.
- Treat missing/missing as valid baseline equivalence: no downstream file existed and the recorded consumer template also contained none.
- Fetch/read the recorded immutable platform tag when necessary and derive proof from Git trees rather than the already-mutated Copier worktree.
- After guarded recopy, require every baseline-equivalent conflict path to match the new target template state, including target-missing paths.
- Continue to fail closed for any current downstream divergence, mixed unproven conflict, config-contract drift, or project-owned snapshot change.
- Add regression coverage matching the actual Cuby v1.4.14 reject set.

## Scope

This affects existing-project managed updates only. Fresh project rendering is unchanged. The behavior is generic: it is based on immutable old-template/consumer equality, not repository names or Cuby-specific path exceptions.

## Success criteria

A platform-owned managed repository can recover from historical Copier replay when every conflict is either already target-equivalent through the reclaimed migration rule or provably unchanged from its recorded old platform template. Real downstream divergence still blocks before push/PR creation.
