# Tasks

- [ ] 1. Add `protected_main` and `pr_merge_mode` to generated/project configuration and safe defaults.
- [ ] 2. Add doctor/preflight validation for invalid protected-main/direct combinations and GitHub CLI/API authentication.
- [ ] 3. Refactor `project_publish.py` so feature-branch push and PR API actions are separate, reusable steps.
- [ ] 4. Extend `finish_task.py` PR lifecycle to create/reuse PR, wait required checks, merge automatically when configured, then sync local main.
- [ ] 5. Ensure failed checks/auth/merge never mutate local main before remote merge success.
- [ ] 6. Preserve `pr_merge_mode=manual` for explicit human-review task PRs and keep cross-repository rollout non-auto-merge.
- [ ] 7. Update generated docs/agent guidance for protected-main zero-hand-off behavior and one-time GitHub auth prerequisites.
- [ ] 8. Add lifecycle regression tests for auto PR merge, failed checks, missing auth, invalid direct/protected config, and unchanged local main on remote failure.
- [ ] 9. Update template-contract tests and generated workflow expectations without reintroducing duplicate Actions runs.
- [ ] 10. Run compile/unit/template/OpenSpec validation and semantic verification; record verification receipt.
- [ ] 11. Archive the OpenSpec change and release a new immutable Dev Platform version.
- [ ] 12. Roll out the release to managed repositories.
- [ ] 13. Update project-owned harness/config in Planner Agent Lab and Jara_Fin to satisfy the protected-main contract.
- [ ] 14. Verify end-to-end protected-main task completion paths in Cuby, Planner Agent Lab, and Jara_Fin.