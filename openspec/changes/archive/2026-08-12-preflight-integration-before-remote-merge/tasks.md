## 1. Reproduce current failure class

- [x] 1.1 Reproduce `dev-platform#154`: integration becomes dirty before merge, remote publication currently proceeds, reconciliation then fails.
- [x] 1.2 Reconcile the design with existing integration-lock and publication-recovery ordering; do not introduce a lock spanning long remote waits.
- [x] 1.3 Identify the narrow integration state/equivalence evidence already available or required for safe comparison.

## 2. Add last-safe-point pre-merge guard

- [x] 2.1 Re-observe integration state under existing serialization immediately before ordinary merge/auto-merge/queue mutation.
- [x] 2.2 Allow clean integration to proceed unchanged.
- [x] 2.3 Block divergent tracked/untracked state before remote mutation with exact path diagnostics and no destructive cleanup.
- [x] 2.4 Prove state that appears while checks are pending is detected at the merge boundary.

## 3. Harden already-merged recovery

- [x] 3.1 Preserve exact GitHub `MERGED` authority even when local reconciliation is dirty/blocked.
- [x] 3.2 Implement bounded content-equivalence classification for already-merged local state.
- [x] 3.3 Reconcile only proven-equivalent state; preserve and report divergent local content.
- [x] 3.4 Keep retry idempotent on the same exact merged PR and existing integration lock.

## 4. Regression and delivery

- [x] 4.1 Cover clean pre-merge, dirty-before-merge, dirty-during-check-wait, path-overlap-without-equivalence, merged+equivalent and merged+divergent scenarios.
- [x] 4.2 Run full lifecycle/publication, template/Copier and strict OpenSpec validation.
- [x] 4.3 Record truthful semantic verification, archive and publish through the normal protected-main/immutable release path if runtime/template behavior changes.
