# Design

## Ownership boundary

Smart Copier update remains the default. Recopy is a recovery mechanism, never the first path.

A conflict is eligible for platform-mode recovery only when its target path is in `RECLAIMED_PLATFORM_ROLLOUT_PATHS` and the downstream file matched the exact target template bytes before `copier update` ran. This proves the current repository no longer carries an independent customization at that path; the conflict comes from historical Copier replay rather than present-state divergence.

Project-owned harness recovery keeps its existing behavior: declared project-owned collision points may use guarded recopy while their fingerprints are preserved.

## Algorithm

1. Snapshot project-owned files and the non-version platform config contract.
2. Before smart update, compute which reclaimed allowlist paths already match the candidate template exactly.
3. Run `copier update --conflict rej`.
4. If no rejection exists, continue normally.
5. Classify conflict targets into project-owned, proven reclaimed, and unexpected.
6. For `harness_mode=platform`, permit recovery only if every conflict is proven reclaimed. For `harness_mode=project`, retain existing project-owned + proven-reclaimed recovery.
7. Reset only the ephemeral rollout branch, verify snapshots, run `copier recopy --overwrite --skip-tasks`, then candidate bootstrap.
8. Re-verify protected snapshots, reclaimed template equality, platform config contract, and harness mode.
9. Any unproven conflict remains fail-closed.

## Compatibility and rollback

No downstream format changes are introduced. If recovery cannot prove safety, behavior stays identical to today: rollout stops without pushing a branch. Removing an entry from the reclaimed allowlist restores the stricter behavior for that path.

## Validation

Unit tests cover platform-mode successful recovery for exact-target `project_publish.py`, blocking when that file differs, and continued blocking for unrelated conflicts. Existing project-harness guarded-recopy tests remain green. The final immutable release is then exercised against real Cuby rollout before archive.
