# Design: CI safety hardening

## Safety invariants

1. **No hidden authoritative QA.** If a repository declares a product/application QA workflow as authoritative, its publication mode must route changes through a gate that runs that QA before `main` changes. `direct` publication is only safe when local/platform checks are themselves authoritative for the repository.
2. **One stable required gate per dynamic selector.** Branch protection should require a stable aggregate/gate job whose result reflects every dynamically selected job, rather than requiring a subset of conditional jobs directly.
3. **Manual full runs are durable.** A manually requested full suite must not be cancelled by an unrelated PR/main lightweight run.
4. **Unknown/high-impact files fail conservatively.** Dependency manifests, lockfiles, build configuration, schema/migration configuration, and workflow/check configuration must trigger appropriate tests/builds rather than `git diff --check` only.
5. **Required check names are unambiguous.** Two workflows in the same repository must not publish the same required check context.
6. **Rollout engine and template version agree.** A rollout targeting immutable release `vX.Y.Z` must execute rollout tooling from that same immutable release, not from whatever happens to be on current `main`.
7. **Project-owned harnesses remain project-owned.** The platform must not silently overwrite repository-specific Git/QA lifecycle files, but project-owned repositories must expose an explicit compatibility contract that central safety audits can validate.
8. **Remote merge truth outranks client cleanup.** Once GitHub reports a PR as `MERGED`, local client-side cleanup failures must not turn the completed remote merge into a reported publication failure. Remote branch deletion and local worktree cleanup are separate reconciliation steps.

## Generated workflow concurrency

Use a concurrency group that includes the event name:

`<workflow>-<event>-<PR number or ref>`

This preserves cancellation of superseded runs within the same event/ref while preventing a `push main` health run from cancelling a manual `workflow_dispatch` full run.

## Platform-owned selected checks

Extend the generic selector contract with explicit config/dependency patterns. For standard Python/Node projects, dependency/build/schema metadata must select full or language-specific commands from `checks.toml`. The template selector remains data-driven; the default generated `checks.toml` becomes conservative for common manifests.

## Stable downstream aggregate gate

For repositories with conditional jobs (for example Jara_Fin), add a final always-running gate job such as `ci-gate`. It depends on all conditional jobs and fails if any required selected job failed/cancelled. Branch protection should require that stable gate instead of trying to enumerate optional jobs directly.

## Project-owned direct publication

Planner Agent Lab demonstrates that `harness_mode=project + publish_mode=direct` is unsafe when repository docs say a cloud workflow is authoritative QA. Correct it to PR publication so the authoritative `demo-quality` workflow runs before merge. Keep heavy QA off post-merge pushes.

## Worktree-safe protected PR merge reconciliation

Platform-owned `publish_mode=pr` must be safe for the `multi-agent` topology where the integration branch is permanently checked out in one worktree and task branches live in sibling worktrees.

`gh pr merge --delete-branch` is not suitable for this topology because the GitHub CLI may attempt local checkout/deletion convenience after the server-side merge. That local action can fail with `main is already checked out at <integration worktree>` while the PR is already merged remotely.

The canonical sequence is therefore:

1. invoke `gh pr merge` without `--delete-branch`;
2. independently poll `gh pr view ... --json state,mergedAt` for bounded retries and treat `state=MERGED` as the authoritative merge fact, even if the merge command exited non-zero;
3. delete the remote feature branch separately without any checkout; remote-branch cleanup failure is reported as a warning after merge, not as a failed publication;
4. return to `finish_task.py`, fast-forward the integration worktree from `origin/main`, finish the machine-local board entry, and only then perform optional local worktree/branch cleanup;
5. if local cleanup is requested, move the running process to the integration checkout before removing the feature worktree. Squash-merged local branches may require explicit local branch deletion because their original commits are not ancestors of the squash commit.

If GitHub cannot confirm `MERGED` after the bounded verification window, the lifecycle fails closed and does not claim that local reconciliation is complete.

## Immutable rollout execution

`rollout.yml` should resolve the requested version in the plan job, then checkout platform tooling at that exact tag for rollout jobs. Release dispatch continues to target the workflow definition on `main`, but the executable scripts and Copier source used by each rollout job come from the requested immutable tag.

## Downstream rollout strategy

After the platform change is verified and released, update managed repositories via reviewed rollout PRs. Repository-owned corrections (Planner publication mode / Jara stable gate / Cuby check mapping) remain explicit downstream changes and are not hidden inside Copier overwrites.
