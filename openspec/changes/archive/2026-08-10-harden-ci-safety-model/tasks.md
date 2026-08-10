# Tasks

- [x] Add CI safety invariants to the platform change spec.
- [x] Make generated workflow concurrency event-aware and cover it with tests.
- [x] Harden generic selected-check defaults for dependency/config/schema/workflow files and add tests.
- [x] Guard platform-owned direct publication so `project_publish --direct` and `--no-checks` cannot silently bypass the validated lifecycle.
- [x] Pin managed rollout execution tooling to the exact immutable release tag and add tests.
- [x] Prepare Cuby clean-environment/high-impact selected-check hardening.
- [x] Prepare Planner Agent Lab switch from direct publication to PR-gated authoritative QA and remove duplicate required check context ambiguity.
- [x] Prepare Jara_Fin stable aggregate CI gate for conditional backend/frontend/script jobs.
- [x] Make protected PR merge completion worktree-safe: remove `--delete-branch`, verify `MERGED` independently, separate remote branch deletion, and run optional local cleanup from the integration checkout.
- [x] Add regression coverage for a non-zero `gh pr merge` exit after a successful remote merge in multi-agent worktree topology.
- [x] Run platform unit/smoke/OpenSpec validation and semantic verification on the implementation head before archive.
- [x] Merge and verify the three downstream safety PRs against their real required status checks.

## Post-release rollout (operational follow-up, not an archive prerequisite)

After this central change is verified, archived, merged and published as a new immutable Dev Platform release:

- roll the exact release out to every `managed` repository;
- verify the Copier rollout PRs and their downstream required checks;
- merge the reviewed rollout PRs when green;
- confirm Cuby receives the worktree-safe platform-owned publication scripts through Copier rather than relying on its temporary downstream repair;
- preserve project-owned harness files in Planner Agent Lab and Jara_Fin while still advancing their shared platform assets/version metadata.
