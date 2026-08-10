# Change: Allow safe recopy for historical platform rollout conflicts

## Why

The v1.4.13 managed rollout exposed a second-order Copier migration problem in Cuby. Cuby had temporarily carried a downstream `scripts/project_publish.py` override for a bug that is now fixed upstream. After Cuby was reconciled to the exact v1.4.13 template bytes, `copier update` still replayed the historical downstream diff and emitted `scripts/project_publish.py.rej`.

v1.4.14 added narrow recovery for that exact-target reclaimed file, but the real Cuby rollout exposed the broader safe case that Copier replay can also conflict on paths which have **not diverged at all** from the repository's recorded old platform template. The v1.4.14 attempt produced `scripts/finish_task.py.rej` even though Cuby's committed `finish_task.py` is byte-identical to the recorded v1.4.12 template, plus `tests/test_git_lifecycle.py.rej` where both Cuby and the v1.4.12 consumer template have no such path.

Those conflicts are also historical replay artifacts, not present downstream customizations. Leaving them unrecoverable means a platform-owned consumer can remain stuck even though the rollout can prove from immutable Git state that recopy would overwrite no independent downstream work.

The v1.4.15 acceptance rollout still stopped inside Cuby's prepare step with exit code 2. Because the Actions check annotation exposed only the generic exit code, changing recovery rules again without first exposing the exact blocking guard would be unsafe guesswork.

## What changes

- Keep exact-target reclaimed-file recovery for migration cases such as `scripts/project_publish.py`.
- Additionally permit guarded recopy in `harness_mode=platform` when a conflicted downstream path is proven identical to that repository's **recorded current platform template** at committed `HEAD`.
- Treat missing/missing as valid baseline equivalence: no downstream file existed and the recorded consumer template also contained none.
- Fetch/read the recorded immutable platform tag when necessary and derive proof from Git trees rather than the already-mutated Copier worktree.
- After guarded recopy, require every baseline-equivalent conflict path to match the new target template state, including target-missing paths.
- Continue to fail closed for any current downstream divergence, mixed unproven conflict, config-contract drift, or project-owned snapshot change.
- Keep rollout service branches (`dev-platform/rollout-vX.Y.Z`) separate from interactive `agent/<task>` branches; do not weaken the ordinary task-branch contract to accommodate automation.
- Surface the exact managed-rollout blocker as a GitHub Actions error annotation/summary while preserving the original non-zero exit and all fail-closed behavior.
- Add regression coverage matching the actual Cuby v1.4.14 reject set and the rollout diagnostic contract.

## Scope

This affects existing-project managed updates only. Fresh project rendering is unchanged. The recovery behavior is generic: it is based on immutable old-template/consumer equality, not repository names or Cuby-specific path exceptions. Diagnostic changes are limited to the managed rollout workflow and do not relax publication or branch protections.

## Success criteria

A platform-owned managed repository can recover from historical Copier replay when every conflict is either already target-equivalent through the reclaimed migration rule or provably unchanged from its recorded old platform template. Real downstream divergence still blocks before push/PR creation. When rollout blocks, the exact guard is visible without converting the run to success. Cuby must complete the real immutable rollout and pass downstream required checks before this change is archived.
