# Tasks

- [x] 1. Harden `github_cli_env()` so invalid token environment variables fall back to validated persistent `gh` / Git HTTPS credentials without leaking or persisting tokens.
- [x] 2. Make required-check waiting tolerate bounded check-registration delay while still failing closed on actual failed checks or timeout.
- [x] 3. Make automatic PR merge negotiate ordinary merge vs GitHub auto-merge / merge-queue enrollment and treat remote PR state as authoritative.
- [x] 4. Make `finish_task` resume successfully when GitHub already merged the task PR but local main/board/worktree reconciliation did not finish.
- [x] 5. Add regression tests for stale-token fallback, delayed check registration, async merge-policy fallback, confirmed-merge cleanup semantics, and already-merged retry.
- [x] 6. Run platform validation (`compileall`, managed-project validation, unit suite, OpenSpec lifecycle check) and semantic OpenSpec verification; record the real verification receipt before archive.

## Post-release rollout (operational follow-up, not an archive prerequisite)

After this central change is archived, merged and published as the next immutable Dev Platform patch release:

- run reviewed managed rollout to Cuby and the other managed platform-harness projects;
- allow the common credential resolver update to reach Jara_Fin without replacing its project-owned harness;
- separately align Jara_Fin's project-owned `merge_to_main.py` with the released merge-state contract;
- verify one end-to-end protected-main task completion in Cuby and Jara_Fin without routine human Git hand-off;
- keep rollout fail-closed: no admin bypass, no force-push, and no automatic cross-repository merge merely because a rollout PR exists.
