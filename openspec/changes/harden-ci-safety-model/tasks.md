# Tasks

- [ ] Add CI safety invariants to platform specs and documentation.
- [ ] Make generated workflow concurrency event-aware and cover it with tests.
- [ ] Harden generic selected-check defaults for dependency/config/schema/workflow files and add tests.
- [ ] Pin managed rollout execution tooling to the exact immutable release tag and add tests.
- [ ] Add validation that flags unsafe project-owned direct publication when authoritative cloud QA is declared.
- [ ] Add/extend downstream compatibility metadata so safety audits can distinguish authoritative local vs cloud QA.
- [ ] Prepare and validate Cuby check-selection hardening.
- [ ] Prepare and validate Planner Agent Lab switch from direct publication to PR-gated authoritative QA and remove duplicate required check context ambiguity.
- [ ] Prepare and validate Jara_Fin stable aggregate CI gate for conditional backend/frontend/script jobs.
- [ ] Run platform unit/smoke/OpenSpec validation and semantic verification.
- [ ] Archive the verified OpenSpec change and release a new immutable platform version.
- [ ] Roll the release out to managed projects and verify downstream gates after merge.
