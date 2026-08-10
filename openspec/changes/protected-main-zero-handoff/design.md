# Design

## Decision summary

Protected integration branches use PR-based remote integration. The agent still runs one finish command; the implementation detail changes from local-main-first direct push to remote-PR-first merge.

Two configuration dimensions are explicit:

```toml
protected_main = true
publish_mode = "pr"
pr_merge_mode = "auto"
```

- `protected_main` records the expected GitHub integration policy.
- `publish_mode` still selects `pr` or `direct`.
- `pr_merge_mode` selects `auto` or `manual` for ordinary task PRs.

`protected_main=true` with `publish_mode=direct` is invalid. `pr_merge_mode` has no effect in direct mode.

The template defaults standard/multi-agent projects to protected PR publication with automatic post-check merge. Light remains direct/unprotected because it has no mandatory feature branch; a light project that enables protected main must move to standard or provide a project-owned harness.

## Publication sequence

For `harness_mode=platform`, `publish_mode=pr`, `pr_merge_mode=auto`:

1. Run OpenSpec hygiene.
2. Require a clean task branch.
3. Fetch current `origin/main` and reject stale/divergent task branches.
4. Run required local selected/full checks.
5. Verify GitHub CLI/API authentication before remote PR operations.
6. Push the feature branch.
7. Create or reuse its PR.
8. Wait for required PR checks using GitHub CLI.
9. Merge the PR through GitHub using squash merge.
10. Fetch `origin/main` again.
11. Fast-forward the integration copy to the merged remote main.
12. Finish board state and optionally remove the task worktree/local branch.

The platform never merges the feature branch into local `main` before step 9.

## Authentication behavior

Git branch publication and GitHub PR API operations are separate concepts.

- A normal git credential may be sufficient to push the feature branch.
- Creating, inspecting, waiting on, and merging the PR requires authenticated `gh` (including credentials supplied through supported `GH_TOKEN`/`GITHUB_TOKEN` environment mechanisms).
- `agent_doctor.py` fails early for platform-owned PR publication when `gh` is absent or unauthenticated.
- `project_publish.py` pushes the feature branch first only after the caller has passed preflight; if invoked directly without API auth it reports that the branch is safely published but the PR API step is unavailable.

This preserves work while still making autonomous completion requirements explicit.

## Required-check waiting

The implementation uses `gh pr checks <branch> --watch --fail-fast` before `gh pr merge`. Branch protection remains the source of truth: even if the watcher races or a check is added later, the merge API is still rejected until GitHub considers requirements satisfied.

The platform does not bypass protection and does not grant agents bypass privileges.

## Manual PR mode

`pr_merge_mode=manual` preserves a review-stop workflow:

- push/create/reuse PR;
- print the PR URL;
- stop without merge.

This is useful for exceptional repositories or high-risk review policies. It is not the default for ordinary managed development projects that are intended to be zero-hand-off.

Cross-repository Dev Platform rollout is separate from task publication and remains non-auto-merge by default.

## Doctor / preflight

For platform-owned harnesses doctor validates:

- `protected_main=true` cannot use `publish_mode=direct`;
- PR mode requires a feature-capable profile (`standard` or `multi-agent`);
- `pr_merge_mode` is a supported value;
- platform-owned PR mode has authenticated GitHub CLI/API access;
- current integration and remote state are safe as before.

When authenticated `gh` is available, doctor also queries the GitHub branch endpoint and warns if the recorded `protected_main` expectation disagrees with GitHub. This verification is advisory because the explicit project config remains the deterministic local contract.

## Project-owned harnesses

`harness_mode=project` remains owned by each repository. Dev Platform rollout updates the shared config/guidance, but project-specific publication scripts must satisfy the same observable contract:

- no direct protected-main push;
- no local-main mutation before remote merge;
- required checks before merge;
- early auth/preflight failure.

Planner Agent Lab and Jara_Fin therefore receive small reviewed harness updates after the platform release.

## Migration

- Cuby: platform-owned harness; set protected PR + auto merge and receive template scripts through Copier rollout.
- Planner Agent Lab: project-owned harness; switch config from direct to protected PR/auto and adapt its project publication flow.
- Jara_Fin: already PR-published; mark protected main and auto task merge while preserving its repository-owned selected checks.
- Etsy: candidate, not managed; do not mutate it through managed rollout. Record/handle separately if/when adopted.

## Failure behavior

- Missing auth: fail doctor/preflight before integration.
- Failed local checks: no branch push or local-main mutation.
- Failed cloud checks: PR stays open; local main unchanged.
- Merge rejected: PR stays open; local main unchanged.
- Remote main advances after merge: fetch and fast-forward to the actual merged remote state; never force.

## Security

The design deliberately avoids branch-protection bypass. GitHub credentials need normal contents/pull-request rights sufficient to push task branches and merge eligible PRs, but required status checks remain enforced by GitHub.