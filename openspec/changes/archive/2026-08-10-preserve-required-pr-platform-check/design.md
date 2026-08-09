# Design: preserve required PR platform check

## Approach

Treat pull-request status compatibility as a small exception to the v1.4.5 one-path optimization rather than introducing new configuration.

Generated trigger matrix:

- `publish_mode=pr`: `pull_request` to the configured main branch + `workflow_dispatch`.
- `publish_mode=direct`: `pull_request` to the configured main branch + `push` to main + `workflow_dispatch`.

The job body remains unchanged. On a PR, a platform-owned harness runs selected checks and a project-owned harness runs only platform/OpenSpec hygiene. On direct main push, platform-owned harnesses run full platform-managed checks. Existing concurrency grouping cancels superseded runs for the same PR/ref.

## Why not change branch protection

The platform cannot assume every private repository exposes branch-protection/ruleset administration through the current GitHub plan/API, and removing a required check would weaken repository safety. The generated workflow should remain capable of producing its stable check name wherever a reviewed PR is used.

## Ownership boundary

Dev Platform owns `.github/workflows/dev-platform.yml` and the generic workflow guidance. Product/application CI remains repository-owned, especially for `harness_mode=project`.

## Upgrade behavior

Existing projects receive the trigger fix through a reviewed Copier patch release. No project-specific code or data migration is required. Stale v1.4.5 rollout PRs are superseded by the next rollout release rather than force-updated.

## Rollback

If the compatibility trigger proves unexpectedly expensive, a later reviewed change can introduce explicit CI-trigger configuration. The safe rollback is not to remove required PR status production without first changing repository protection policy.

## Validation

- Template contract tests assert PR-only behavior for `publish_mode=pr` and PR+main compatibility behavior for `publish_mode=direct`.
- Existing central CI remains single-job PR validation with all profile smoke paths.
- A real managed direct-mode rollout must produce `platform-ci` on the rollout PR before merge.
