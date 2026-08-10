# Design

## Decision summary

Protected integration branches use PR-based remote integration. The agent still runs one finish command; the implementation detail changes from local-main-first direct push to remote-PR-first merge.

Three configuration dimensions are explicit:

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

1. Run publication preflight, including protection-policy and GitHub API credential checks.
2. Run OpenSpec hygiene.
3. Require a clean task branch.
4. Fetch current `origin/main` and reject stale/divergent task branches.
5. Run required local selected/full checks.
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
- Creating, inspecting, waiting on, and merging the PR requires authenticated GitHub API access through `gh`.
- Explicit `GH_TOKEN` / `GITHUB_TOKEN` or an existing `gh` login are preferred.
- If `gh` itself is unauthenticated but the machine already has a reusable HTTPS credential for `github.com` that is sufficient for normal git operations, the platform may obtain it non-interactively through `git credential fill`, pass it only to the `gh` subprocess as `GH_TOKEN`, validate it, and never print or persist it. This avoids forcing a redundant second login on a machine that already has an appropriate GitHub token stored in its credential helper.
- SSH-only git credentials cannot be converted into GitHub REST credentials. Those hosts still need a one-time `gh auth login` or token environment setup.
- `agent_doctor.py` fails early for platform-owned PR publication when no usable GitHub API credential can be resolved.
- `project_publish.py` keeps branch push independent from PR API work. Normal `finish_task.py` preflight catches missing API auth before any push; direct `project_publish.py --mode pr` invocation may safely push the validated branch first and then report that PR creation/merge is incomplete.

This preserves work while making autonomous completion requirements explicit without storing additional secrets in the repository.

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
- platform-owned PR mode has usable GitHub API authentication;
- current integration and remote state are safe as before.

When GitHub API authentication is available, doctor also queries the GitHub branch endpoint and warns if the recorded `protected_main` expectation disagrees with GitHub. It additionally fails if GitHub reports the branch protected while direct publication is configured. The remote verification complements the explicit local contract and catches legacy configs that predate `protected_main`.

## Project-owned harnesses

`harness_mode=project` remains owned by each repository. Dev Platform rollout updates shared generated assets, but project-specific publication scripts must satisfy the same observable contract:

- no direct protected-main push;
- no local-main mutation before remote merge;
- required checks before merge;
- early auth/preflight failure.

Planner Agent Lab and Jara_Fin therefore receive separate small reviewed harness/config updates after the platform release.

## Migration and release sequencing

The active platform change defines and implements the reusable contract first. It is verified, archived, merged, and published as a new immutable Dev Platform release. Downstream migration is then an operational rollout of that released contract; it is intentionally not a prerequisite for archiving the central change because the immutable release must exist before managed Copier rollout can target it.

After the release:

- Cuby: platform-owned harness; explicitly set protected PR + auto merge because `.dev-platform.toml` is project-owned/preserved, and receive template scripts through Copier rollout.
- Planner Agent Lab: project-owned harness; switch config from direct to protected PR/auto and adapt its project publication flow.
- Jara_Fin: already PR-published; mark protected main and auto task merge while preserving its repository-owned selected checks.
- Etsy: candidate, not managed; do not mutate it through managed rollout. Handle separately if/when adopted or explicitly requested.

`.dev-platform.toml` is deliberately preserved on existing projects, so rollout automation must not assume the new keys appear automatically. Existing managed repositories require explicit reviewed config changes.

## Failure behavior

- Missing auth: fail doctor/preflight before integration or normal finish-task branch publication.
- Failed local checks: no branch push or local-main mutation.
- Failed cloud checks: PR stays open; local main unchanged.
- Merge rejected: PR stays open; local main unchanged.
- Remote main advances after merge: fetch and fast-forward to the actual merged remote state; never force.

## Security

The design deliberately avoids branch-protection bypass. GitHub credentials need normal contents/pull-request rights sufficient to push task branches and merge eligible PRs, but required status checks remain enforced by GitHub. Tokens recovered through a configured git credential helper are process-local only and are never logged, written to project files, or promoted as friction evidence.