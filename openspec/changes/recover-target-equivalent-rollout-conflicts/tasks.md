# Tasks

- [x] 1. Record the target-equivalent recovery safety rule and failure behavior.
- [x] 2. Extend managed rollout to pre-prove eligible platform-owned lifecycle files against the exact target release.
- [x] 3. Allow guarded recopy for platform harnesses only when every Copier reject is pre-proven target-equivalent.
- [x] 4. Preserve the existing project-owned harness recovery contract and post-recopy config validation.
- [x] 5. Add regression tests for target-equivalent platform recovery and real-divergence blocking.
- [x] 6. Run exact-head Platform CI and strict OpenSpec validation.
- [x] 7. Semantically verify the implemented recovery against the Cuby failure mode and fail-closed rollout contract.

## Post-release operational follow-up

After this verified change is archived, merged, and published as a new immutable Dev Platform release:

- roll the exact release out to managed projects;
- confirm Cuby uses the `guarded-recopy` strategy for the historical target-equivalent `scripts/project_publish.py` conflict;
- require normal downstream `platform-ci` / project-owned gates before merging rollout PRs;
- confirm Cuby's `.copier-answers.yml` and `.dev-platform.toml` advance to the released version with no `.rej` files or hand patch.
