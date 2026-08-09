# Proposal: Optimize GitHub Actions cost

## Why

The private-account GitHub Actions quota was exhausted after roughly one week of active development. The current repositories frequently run the same validation twice for one reviewed change: once on the pull request and again after merge to `main`. Some project-owned workflows also run expensive full suites on schedules or use expensive runners for informational checks.

This is now operationally material: when the included Actions quota is exhausted, required remote checks cannot start, which blocks reviewed adoption/rollout workflows even though local agent checks still work.

## What changes

Introduce a cost-aware CI contract whose default is:

- local agents perform the heavy/full verification before publish;
- GitHub Actions is the final remote gate, not a duplicate execution layer;
- a reviewed change should normally consume one cloud validation path, not both PR and post-merge validation;
- superseded runs for the same PR/ref are cancelled automatically;
- expensive scheduled/full/browser checks are opt-in rather than a default consequence of every push;
- informational checks do not use premium runners unless the check is genuinely OS-specific.

For generated Dev Platform CI, trigger choice is derived from the existing publish contract instead of adding another configuration axis:

- `publish_mode=pr`: run platform CI on pull requests and manual dispatch, not again on the resulting `main` push;
- `publish_mode=direct`: run platform CI on `main` pushes and manual dispatch, not also on feature-branch pull requests.

The central `dev-platform` repository also stops repeating shared validation three times through the profile matrix: shared checks run once, while profile-specific factory/update smoke coverage still exercises every supported profile.

## Scope

### Universal platform behavior

- generated Dev Platform CI trigger policy;
- concurrency/cancel-in-progress for superseded validation runs;
- central Platform CI de-duplication;
- tests that render both PR and direct publish variants;
- documentation for local-heavy / cloud-final verification.

### Existing-project updates

The generated workflow is platform-owned and reaches `managed` projects through the normal versioned Copier rollout. Existing historical runs and project-owned CI remain untouched.

### Project-owned follow-up

The platform must not silently rewrite project-owned workflows. After the platform change is published, the currently expensive project-owned workflows should receive separate reviewed optimizations, starting with:

- `lehard/Jara_Fin`: remove duplicate post-merge/full scheduled cloud execution; keep PR-selected checks and manual full suite;
- `lehard/planner-agent-lab`: make the heavy `quality.yml` PR/manual-only with concurrency; investigate/remove the duplicate legacy platform CI workflow only after required-check compatibility is confirmed;
- `lehard/etsy`: run CI on PR/manual only and move informational Ruff from macOS to Linux unless a real macOS-only invariant is identified.

Candidate repositories remain non-mutating under managed rollout until they are adopted according to the existing inventory contract.

## Managed files / compatibility risks

Likely platform-managed files affected:

- `template/.github/workflows/dev-platform.yml.jinja`;
- `.github/workflows/ci.yml` in the central platform;
- template/render tests and CI contract tests;
- CI/rollout operating documentation.

Compatibility risks:

- branch protection may currently require a status produced by a workflow that becomes non-triggering; implementation must verify expected required-check names before deleting or renaming workflows;
- direct-publish repositories rely more heavily on local pre-publish verification because their cloud run happens after the `main` update;
- project-owned CI cannot be rewritten by Copier and needs separate reviewed PRs.

## Non-goals

- buying a larger GitHub plan or Actions budget;
- introducing another CI vendor;
- weakening local test requirements or OpenSpec verification;
- auto-merging rollout/update PRs;
- mutating `candidate`/`excluded` repositories through managed rollout;
- replacing GitHub-hosted runners with self-hosted infrastructure in this change.

## Success criteria

- a normal PR-published change does not run the same generated platform CI again after merge;
- a direct-published project does not additionally burn a PR run by default;
- newer commits to the same active PR cancel older in-progress runs;
- central Platform CI performs shared validation once per run while retaining light/standard/multi-agent coverage;
- managed project rollout can propagate the generated workflow change without overwriting project-owned CI;
- project-owned top-cost workflows have an explicit, reviewable follow-up plan instead of being silently modified.