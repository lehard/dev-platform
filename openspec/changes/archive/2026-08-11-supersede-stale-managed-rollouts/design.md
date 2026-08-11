# Design: managed rollout PR supersession

## Identity and trust boundary

A rollout PR is eligible for automatic supersession only when all of the following are true:

- target repository is currently `managed` in `managed-projects.json`;
- PR head branch matches the exact reserved form `dev-platform/rollout-vMAJOR.MINOR.PATCH`;
- the version parses as stable SemVer under the same platform version policy used by release/rollout;
- PR was created by the expected managed-rollout automation identity or otherwise carries a verifiable rollout marker produced by this workflow;
- PR base is the configured default branch for that managed repository.

Title/body text alone is never sufficient. Unrelated `dev-platform/*`, `agent/*`, human feature branches, and newer rollout targets are out of scope.

## Authoritative target

For one rollout job targeting `vN`, classify each eligible open rollout PR for the same repository as:

- `older`: PR target < `vN`;
- `same`: PR target == `vN`;
- `newer`: PR target > `vN`.

Also read the downstream default branch's recorded platform version (`.copier-answers.yml` and coherent `.dev-platform.toml` where present). If the default branch is already at version `vB`, any rollout PR with target <= `vB` is stale regardless of which job originally created it.

A downgrade request remains blocking under the existing rollout contract.

## Supersession ordering

### Normal newer rollout succeeds

1. Prepare and validate target `vN` using the existing fail-closed rollout path.
2. Push/create or reuse the deterministic `vN` rollout branch/PR.
3. Confirm the `vN` PR exists and represents the expected target head.
4. Only then close eligible open rollout PRs whose target is lower than `vN`.
5. Add a concise machine/human-visible supersession reason naming the replacement target/PR.
6. After close, attempt remote branch deletion as best-effort post-close cleanup. Never force-push.

This ordering guarantees that a failed newer rollout does not destroy the last valid pending update path.

### Downstream already advanced

If the default branch is already at `vB`, the maintenance path may close eligible rollout PRs with target <= `vB` even when no new PR is being created. This is pure stale-state cleanup based on committed downstream metadata.

### Newer PR already exists

If rollout `vN` discovers an open eligible rollout PR targeting `vM` where `vM > vN`, it must not close or mutate the newer PR. The `vN` attempt remains a downgrade/stale request and follows existing fail-closed behavior.

## Current-PR freshness classification

The rollout helper should expose a deterministic classification for a PR target relative to the current downstream base: `current`, `stale`, or `future/newer`. This classification feeds diagnostics and cleanup; it must not rely on PR title wording.

A stale PR remains closed once superseded. If a human manually reopens it later, the next rollout/maintenance reconciliation should close it again when the same stale proof still holds.

## One-time reconciliation

Add an explicit maintenance command/mode that iterates only the current managed registry, reads open eligible rollout PRs, and applies the same stale proof without creating a new release. It must support dry-run/report mode before mutation. This is used once after implementation to clean existing accumulated PRs in Planner Agent Lab and Jara_Fin and remains useful for future repair.

The maintenance path uses the same least-privilege GitHub App/down-scoped target credentials as managed rollout; it must not introduce a personal-token requirement.

## Failure behavior

- Failure to enumerate or classify PRs: fail closed for the cleanup operation and do not guess from titles.
- Failure to close one stale PR: surface a structured cleanup warning/error naming the repo/PR; do not close unrelated PRs to compensate.
- Failure to delete a remote branch after confirmed PR close: warning-only; the PR stays correctly closed.
- Failure preparing a newer target before its PR exists: do not supersede older pending PRs.

## Upgrade and rollback

This primarily changes central rollout orchestration/scripts, not application files. If a reusable helper is delivered through the template, fresh render and Copier update behavior must be tested. Rollback stops automatic supersession but does not reopen closed PRs; this is acceptable because each closed PR remains recoverable from Git history and its replacement/stale reason is recorded.

## Validation

Tests must cover:

- older/same/newer SemVer classification;
- downstream base already ahead of multiple open rollout PRs;
- successful vN PR creation closes only older eligible PRs;
- failed vN preparation closes nothing;
- newer open rollout PR is never closed by an older request;
- unrelated PR/title lookalike is untouched;
- unexpected automation identity/branch form is untouched;
- branch deletion failure after close is warning-only;
- dry-run maintenance reports exact planned closures with zero mutations;
- managed registry boundary: candidate/excluded repositories are never mutated.