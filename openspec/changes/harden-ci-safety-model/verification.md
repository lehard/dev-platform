# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic OpenSpec review plus exact implementation-head Platform CI and downstream protected-PR evidence

## Scope reviewed

Reviewed proposal, design, delta requirements, tasks, generated platform publication scripts, workflow documentation, lifecycle tests, rollout behavior, and the three repository-specific safety migrations for completeness, correctness, and coherence.

## Platform evidence

Implementation head `972c37d588d80dd01baf5f16740cfa5bff374e70` passed Platform CI run `31376791529`.

That run completed:

- shared-script compilation;
- managed-project registry validation;
- the full platform unit suite;
- OpenSpec lifecycle hygiene;
- strict OpenSpec validation;
- Copier/profile rendering and upgrade smoke coverage;
- mature/project-owned harness adoption smoke coverage.

The unit suite includes `test_multi_agent_pr_finish_reconciles_remote_merge_after_nonzero_gh_exit`, which reproduces the reported steady-state topology: `main` remains checked out in the integration worktree, the feature task runs in a sibling worktree, the simulated GitHub merge succeeds remotely while the merge client returns non-zero, and the lifecycle still confirms `MERGED`, synchronizes local main, deletes the remote task branch separately, and safely removes the completed local worktree/branch from the integration checkout.

## Worktree-safe merge review

The protected PR path now satisfies the new invariant:

- `gh pr merge` no longer requests `--delete-branch`;
- merge success is confirmed independently with bounded `gh pr view ... state,mergedAt` polling;
- a non-zero merge-command exit is not treated as authoritative when GitHub confirms `MERGED`;
- inability to confirm `MERGED` still fails closed before local reconciliation is claimed;
- remote feature-branch deletion is a separate no-checkout operation and cleanup failure is post-merge warning/debt rather than a false publication failure;
- optional multi-agent local cleanup changes cwd to the integration checkout before removing the feature worktree, then deletes the exact completed local branch;
- local main and board state are reconciled only after remote merge confirmation.

This is coherent with the accepted protected-main zero-hand-off contract: remote merge remains authoritative and local `main` is never advanced ahead of GitHub as part of PR publication.

## Existing CI-safety requirements

The active change's other safety requirements remain represented in implementation/tests: event-aware workflow concurrency, conservative high-impact check selection, guarded direct publication/no-checks, rendered workflow/publication-mode consistency, exact-version rollout execution, downstream aggregate gates, authoritative QA compatibility, and unambiguous required contexts.

## Downstream evidence

The three repository-specific safety PRs were merged after their real cloud gates passed:

- Cuby PR #18, head `3baccd150e387cad5cc09c58143ed59e8a749c6c`: Dev Platform run `31365421068` succeeded.
- Planner Agent Lab PR #19, head `f758caf9689881de82bfcdd03a35bc33774c5fa9`: Dev Platform run `31364823095` and authoritative `quality` run `31364823062` succeeded.
- Jara_Fin PR #12, head `6b1c9932e257dcb99e0abf04e421a452c61b0672`: Dev Platform run `31364806674` and repository CI run `31364806649` succeeded.

Their completed OpenSpec lifecycle debt was subsequently archived in each repository. Cuby also independently reproduced the post-merge worktree bug in normal use, providing live evidence for the additional platform fix covered by this verification.

## Findings

No material semantic divergence remains between the active change and the reviewed implementation. The release/managed rollout is intentionally operational follow-up after central archive/publication, not an archive prerequisite.
