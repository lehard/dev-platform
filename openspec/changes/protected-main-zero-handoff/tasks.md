# Tasks

- [x] 1. Add `protected_main` and `pr_merge_mode` to generated/project configuration and safe defaults.
- [x] 2. Add doctor/preflight validation for invalid protected-main/direct combinations and GitHub CLI/API authentication.
- [x] 3. Refactor `project_publish.py` so feature-branch push and PR API actions are separate, reusable steps.
- [x] 4. Extend `finish_task.py` PR lifecycle to create/reuse PR, wait required checks, merge automatically when configured, then sync local main.
- [x] 5. Ensure failed checks/auth/merge never mutate local main before remote merge success.
- [x] 6. Preserve `pr_merge_mode=manual` for explicit human-review task PRs and keep cross-repository rollout non-auto-merge.
- [x] 7. Update generated docs/agent guidance for protected-main zero-hand-off behavior and GitHub API authentication prerequisites.
- [x] 8. Add lifecycle regression tests for auto PR merge, failed checks, missing auth, invalid direct/protected config, and unchanged local main on remote failure.
- [x] 9. Update template-contract tests and generated workflow expectations without reintroducing duplicate Actions runs.
- [x] 10. Complete compile/unit/template/OpenSpec validation and semantic verification on the current safety-hardened baseline; record the truthful verification receipt.
- [ ] 11. Archive this verified change through `scripts/openspec_lifecycle.py archive protected-main-zero-handoff` from an environment with the OpenSpec CLI before marking the lifecycle fully complete.

## Post-release rollout (operational follow-up, not an archive prerequisite)

After this central change is merged and published as an immutable Dev Platform release:

- roll the release out to managed repositories;
- explicitly update preserved `.dev-platform.toml` policy in Cuby, Planner Agent Lab and Jara_Fin;
- adapt project-owned publication harnesses in Planner Agent Lab and Jara_Fin;
- verify an end-to-end protected-main task completion path in Cuby, Planner Agent Lab and Jara_Fin;
- keep candidate repositories such as Etsy outside managed mutation unless separately adopted or explicitly requested.
