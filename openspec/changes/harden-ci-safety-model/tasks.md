# Tasks

- [x] Add CI safety invariants to the platform change spec.
- [x] Make generated workflow concurrency event-aware and cover it with tests.
- [x] Harden generic selected-check defaults for dependency/config/schema/workflow files and add tests.
- [x] Guard platform-owned direct publication so `project_publish --direct` and `--no-checks` cannot silently bypass the validated lifecycle.
- [x] Pin managed rollout execution tooling to the exact immutable release tag and add tests.
- [x] Preserve repository-specific agent workflow guidance for `harness_mode=project` during managed rollout.
- [x] Prepare Cuby clean-environment/high-impact selected-check hardening.
- [x] Prepare Planner Agent Lab switch from direct publication to PR-gated authoritative QA and remove duplicate required check context ambiguity.
- [x] Prepare Jara_Fin stable aggregate CI gate for conditional backend/frontend/script jobs.
- [ ] Run platform unit/smoke/OpenSpec validation and semantic verification on the exact final commit.
- [ ] Merge and verify the three downstream safety PRs against their real required status checks.
- [ ] Archive the verified OpenSpec change and release a new immutable platform version.
- [ ] Roll the release out to managed projects and verify generated workflow changes after merge.
