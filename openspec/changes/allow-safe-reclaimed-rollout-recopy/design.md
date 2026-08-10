# Design

## Ownership boundary

Smart Copier update remains the default. Recopy is a recovery mechanism, never the first path.

A platform-mode conflict has two safe recovery proofs:

1. **Reclaimed target-equivalence.** A narrowly allowlisted migration path already matches the exact target template before update. This proves the downstream override has already been retired.
2. **Recorded baseline-equivalence.** The conflicted path in committed downstream `HEAD` is exactly identical to the same path in the immutable platform tag recorded by `.copier-answers.yml`. This proves there is no current downstream customization for recopy to erase. Missing/missing is equivalent for the same reason.

Any conflict that satisfies neither proof remains blocking. Project-owned harness recovery keeps its existing behavior: declared project-owned collision points may use guarded recopy while their fingerprints are preserved.

## Why the second proof is needed

The v1.4.14 Cuby rollout demonstrated that historical Copier replay can create rejects beyond the one downstream-hotfixed file. It emitted:

- `scripts/project_publish.py.rej` — already exact target, covered by reclaimed target-equivalence;
- `scripts/finish_task.py.rej` — committed Cuby file still exactly v1.4.12 baseline, so it is baseline-equivalent;
- `tests/test_git_lifecycle.py.rej` — absent in both Cuby and the recorded v1.4.12 consumer template, also baseline-equivalent.

Path allowlisting alone cannot model this safely without accumulating repository/history-specific exceptions. Comparing immutable old-template state to committed downstream state does.

## Algorithm

1. Snapshot project-owned files and the non-version platform config contract.
2. Before smart update, compute which reclaimed migration paths already match the candidate template exactly.
3. Run `copier update --conflict rej`.
4. If no rejection exists, continue normally.
5. Read the repository's recorded old platform tag from `.copier-answers.yml` and ensure that immutable tag is available in the exact-release platform checkout.
6. For every platform-mode conflict not already target-equivalent, compare downstream committed `HEAD:<path>` with `<recorded-tag>:template/<path>`. The comparison uses Git tree/blob fingerprints, never the Copier-mutated worktree.
7. Classify conflict targets into project-owned, proven reclaimed-target, proven baseline-equivalent, and unexpected.
8. For `harness_mode=platform`, permit recovery only if every conflict is proven reclaimed-target or baseline-equivalent. For `harness_mode=project`, retain the existing project-owned + reclaimed-target recovery contract.
9. Reset only the ephemeral rollout branch, re-prove baseline equivalence from committed Git state, verify snapshots, run `copier recopy --overwrite --skip-tasks`, then candidate bootstrap.
10. Re-verify protected snapshots, reclaimed target equality, every baseline-equivalent path against the **new** target template state, platform config contract, and harness mode.
11. Any unproven conflict remains fail-closed.

## Git/tag handling

Managed rollout already executes tooling from the exact immutable target release. If the older recorded tag is not present in that shallow checkout, rollout fetches only that exact old tag before computing template fingerprints. Failure to fetch or inspect it blocks recovery.

This proof remains reproducible because both sides are immutable Git objects: downstream rollout starts from a clean committed `HEAD`, and the old platform state is a stable SemVer tag.

## Compatibility and rollback

No downstream format changes are introduced. If recovery cannot prove safety, behavior stays fail-closed: rollout stops without pushing a branch. Removing baseline-equivalence recovery restores the stricter v1.4.14 behavior.

## Validation

Unit tests cover target-equivalent reclaimed recovery, exact old-baseline and missing/missing proof, the actual mixed Cuby reject set, and real-divergence blocking. Existing project-harness guarded-recopy tests remain green. The final immutable release is then exercised against real Cuby rollout before archive.
