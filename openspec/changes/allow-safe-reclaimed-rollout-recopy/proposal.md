# Change: Allow safe recopy for historical platform rollout conflicts

## Why

The v1.4.13 managed rollout exposed a second-order Copier migration problem in Cuby. Cuby had temporarily carried a downstream `scripts/project_publish.py` override for a bug that is now fixed upstream. After Cuby was reconciled to the exact v1.4.13 template bytes, `copier update` still replayed the historical downstream diff and emitted `scripts/project_publish.py.rej`.

v1.4.14 added narrow recovery for that exact-target reclaimed file, but the real Cuby rollout exposed the broader safe case that Copier replay can also conflict on paths which have **not diverged at all** from the repository's recorded old platform template. The v1.4.14 attempt produced `scripts/finish_task.py.rej` even though Cuby's committed `finish_task.py` is byte-identical to the recorded v1.4.12 template, plus `tests/test_git_lifecycle.py.rej` where both Cuby and the v1.4.12 consumer template have no such path.

Those conflicts are also historical replay artifacts, not present downstream customizations. Leaving them unrecoverable means a platform-owned consumer can remain stuck even though the rollout can prove from immutable Git state that recopy would overwrite no independent downstream work.

The v1.4.15 acceptance rollout still stopped inside Cuby's prepare step with exit code 2. Subsequent releases improved blocker visibility and runtime parity. The recovery implementation has been shipped in immutable platform releases through v1.4.20, but the v1.4.20 Cuby update still required manual reconciliation of a stale `.rej`/Copier state before the downstream PR could complete. Therefore this change is **implemented but not yet acceptance-complete**: a manual repair cannot be used as evidence that managed rollout itself is fixed.

## What changes

- Keep exact-target reclaimed-file recovery for migration cases such as `scripts/project_publish.py`.
- Additionally permit guarded recopy in `harness_mode=platform` when a conflicted downstream path is proven identical to that repository's **recorded current platform template** at committed `HEAD`.
- Treat missing/missing as valid baseline equivalence: no downstream file existed and the recorded consumer template also contained none.
- Fetch/read the recorded immutable platform tag when necessary and derive proof from Git trees rather than the already-mutated Copier worktree.
- After guarded recopy, require every baseline-equivalent conflict path to match the new target template state, including target-missing paths.
- Continue to fail closed for any current downstream divergence, mixed unproven conflict, config-contract drift, or project-owned snapshot change.
- Keep rollout service branches (`dev-platform/rollout-vX.Y.Z`) separate from interactive `agent/<task>` branches; do not weaken the ordinary task-branch contract to accommodate automation.
- Preserve clear managed-rollout blocker reporting while keeping diagnostics observational only. Machine-readable diagnostic-envelope work is now owned by the already-archived `harden-rollout-diagnostics` change rather than extending this recovery change further.
- Keep managed-rollout runtime parity with generated downstream CI where platform-owned baselines are required.
- Add/retain regression coverage matching the actual historical Cuby reject set and real-divergence refusal.

## Scope

This affects existing-project managed updates only. Fresh project rendering is unchanged. The recovery behavior is generic: it is based on immutable old-template/consumer equality, not repository names or Cuby-specific path exceptions. Diagnostic changes already delivered by separate archived changes are not a reason to expand this active change further.

## Current closure boundary

No additional recovery heuristic should be added merely to make the checkbox turn green. The remaining work is operational acceptance of the already-defined proof model.

Use the first cumulative immutable platform release after the current stability follow-ups are merged/verified rather than cutting a special throwaway release solely for this receipt. That release must run through the normal managed rollout path for every current `managed` project. Cuby is the critical historical acceptance consumer.

A successful Cuby acceptance means:

- the central release dispatches managed rollout normally;
- Cuby preparation completes without manual file edits, manual `.rej` deletion, manual `copier update/recopy`, or hand-synchronizing platform metadata;
- the rollout produces/reuses the expected reviewable downstream PR (or correctly reports already-current state);
- downstream required CI for the rollout PR passes before it is considered accepted;
- any old rollout PR debt is handled by the dedicated supersession contract, not by ad-hoc manual cleanup inside this recovery change.

If the automatic attempt fails, keep this change active, use the structured rollout diagnostic as evidence, update this proposal/design before changing recovery semantics, and do not substitute a manual downstream repair for acceptance.

## Success criteria

A platform-owned managed repository can recover from historical Copier replay when every conflict is either already target-equivalent through the reclaimed migration rule or provably unchanged from its recorded old platform template. Real downstream divergence still blocks before push/PR creation. Cuby must complete a later real immutable **automatic** managed rollout and pass downstream required checks with no manual reconciliation before this change receives `OpenSpec-Verify: PASS` and is archived.