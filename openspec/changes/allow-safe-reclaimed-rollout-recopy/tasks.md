# Tasks

- [x] Add the platform-rollout delta requirement for proven reclaimed-file recovery.
- [x] Extend rollout classification so platform-owned harnesses may recopy only proven reclaimed conflicts.
- [x] Add `scripts/project_publish.py` to the narrow reclaimed-platform allowlist.
- [x] Add regression tests for exact-target recovery and real-divergence blocking in platform mode.
- [ ] Run platform CI/OpenSpec validation and semantic verification on the exact final implementation.
- [ ] Release the verified fix as a new immutable platform version and roll it through all managed projects.
- [ ] Verify Cuby no longer blocks on historical `project_publish.py` replay and all downstream required checks pass.
- [ ] Record `OpenSpec-Verify: PASS` plus verification method and archive the completed change.
