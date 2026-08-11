# Tasks

- [x] Add the platform-rollout delta requirement for proven historical-conflict recovery.
- [x] Keep narrow exact-target recovery for reclaimed migration paths such as `scripts/project_publish.py`.
- [x] Add immutable recorded-baseline equivalence for platform-mode conflicts using downstream committed `HEAD` plus the old platform SemVer tag.
- [x] Treat missing/missing as safe baseline equivalence and verify recovered paths against the new target template after recopy.
- [x] Add regression tests for exact-target recovery, old-baseline recovery, the actual mixed Cuby reject set, and real-divergence blocking.
- [x] Surface failed prepare blockers without weakening fail-closed behavior; richer machine-readable diagnostics are owned by the archived `harden-rollout-diagnostics` change.
- [x] Match managed-rollout Node runtime to the platform-generated downstream CI baseline and keep parity regression coverage.
- [ ] After `harden-pr-reconciliation-concurrency`, `wire-runtime-delegation-containment`, and `supersede-stale-managed-rollouts` are merged/verified, rerun the full platform validation suite on the cumulative exact release candidate and perform semantic review of this recovery change against current implementation.
- [ ] Publish the next normal cumulative immutable platform release (do not cut a throwaway acceptance-only version) and confirm release orchestration dispatches managed rollout for all current `managed` projects.
- [ ] Verify Cuby's managed rollout preparation completes automatically with no manual `copier update/recopy`, no manual `.rej` deletion/file copying, and no hand-synchronization of platform version metadata; if it fails, keep this change active and use the canonical diagnostic as evidence before changing design.
- [ ] Verify the resulting Cuby rollout PR's required downstream CI passes (or the project is correctly reported already-current) and record the exact release/run/PR evidence.
- [ ] Confirm the same immutable release produces a normal managed-rollout result for Planner Agent Lab and Jara_Fin; stale older rollout PR cleanup is handled through the dedicated supersession change rather than ad-hoc steps here.
- [ ] Record `OpenSpec-Verify: PASS` plus `Verification-Method: <actual method/evidence>` in `verification.md`, then archive through `python3 template/scripts/openspec_lifecycle.py archive allow-safe-reclaimed-rollout-recopy` and publish the archive/current-spec result.

## Closure rule

Manual downstream reconciliation is incident recovery, not acceptance evidence. Do not check the Cuby acceptance task merely because a manually repaired PR merged.