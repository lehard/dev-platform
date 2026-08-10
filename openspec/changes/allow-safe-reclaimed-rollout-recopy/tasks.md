# Tasks

- [x] Add the platform-rollout delta requirement for proven historical-conflict recovery.
- [x] Keep narrow exact-target recovery for reclaimed migration paths such as `scripts/project_publish.py`.
- [x] Add immutable recorded-baseline equivalence for platform-mode conflicts using downstream committed `HEAD` plus the old platform SemVer tag.
- [x] Treat missing/missing as safe baseline equivalence and verify recovered paths against the new target template after recopy.
- [x] Add regression tests for exact-target recovery, old-baseline recovery, the actual mixed Cuby reject set, and real-divergence blocking.
- [ ] Surface failed prepare blockers in Actions without weakening fail-closed behavior or the `agent/<task>` interactive branch contract.
- [ ] Re-run platform CI/OpenSpec validation and semantic verification on the exact final implementation.
- [ ] Release the verified fix as a new immutable platform version and roll it through all managed projects.
- [ ] Verify Cuby no longer blocks on the historical replay/prepare path and all downstream required checks pass.
- [ ] Record `OpenSpec-Verify: PASS` plus verification method and archive the completed change.
