# Tasks

- [ ] 1. Harden `github_cli_env()` so invalid token environment variables fall back to validated persistent `gh` / Git HTTPS credentials without leaking or persisting tokens.
- [ ] 2. Make required-check waiting tolerate bounded check-registration delay while still failing closed on actual failed checks or timeout.
- [ ] 3. Make automatic PR merge negotiate ordinary merge vs GitHub auto-merge / merge-queue enrollment and treat remote PR state as authoritative.
- [ ] 4. Make `finish_task` resume successfully when GitHub already merged the task PR but local main/board/worktree reconciliation did not finish.
- [ ] 5. Add regression tests for stale-token fallback, delayed check registration, async merge-policy fallback, confirmed-merge cleanup semantics, and already-merged retry.
- [ ] 6. Run platform validation (`compileall`, managed-project validation, unit suite, OpenSpec lifecycle check) and semantic OpenSpec verification; record the real verification receipt before archive.
- [ ] 7. Archive the change, bump an immutable platform release, merge through protected main, and confirm managed rollout PRs are created for platform-owned harness projects.
- [ ] 8. Align Jara_Fin's project-owned `merge_to_main.py` with the released merge-state contract without replacing its project-owned harness.
