# Tasks

- [x] 1. Add a deterministic rollout-PR identity/SemVer classifier using reserved branch form, configured base branch, managed registry state, and expected automation context; test title lookalikes/unrelated branches/newer versions.
- [x] 2. Add downstream-base platform-version reading and stale/current/newer classification using coherent committed platform metadata; retain existing downgrade fail-closed behavior.
- [x] 3. Integrate supersession ordering into managed rollout: only after a validated target PR exists (or base already adopted a newer/equal version), close older eligible rollout PRs with a replacement/stale reason; never auto-merge or force-push.
- [x] 4. Implement post-close remote rollout-branch deletion as best-effort cleanup; preserve closed state and emit an exact warning if deletion fails.
- [x] 5. Add an explicit dry-run/apply maintenance mode restricted to `managed-projects.json` managed entries, reusing the rollout GitHub App/down-scoped credentials and the same identity rules.
- [x] 6. Add workflow/helper tests proving failed newer preparation closes nothing, newer PRs are never closed by older requests, candidate/excluded repos are never mutated, and dry-run produces zero writes.
- [x] 7. Run the maintenance command in dry-run against current managed repositories, review the exact plan, then apply it to close already-stale rollout PRs (including accumulated older Planner Agent Lab/Jara_Fin rollout PRs) while preserving the newest still-relevant pending target. Evidence: `maintenance-evidence.md`.
- [x] 8. Run platform validation, rollout workflow tests, and semantic OpenSpec verification; record `OpenSpec-Verify: PASS` with the real method in `verification.md`, archive via `python3 template/scripts/openspec_lifecycle.py archive supersede-stale-managed-rollouts`, then publish through protected main.

## Logical commit boundaries

1. Identity/version classifier + tests.
2. Rollout integration + maintenance command + tests.
3. One-time managed-repo cleanup evidence + verification/archive.
