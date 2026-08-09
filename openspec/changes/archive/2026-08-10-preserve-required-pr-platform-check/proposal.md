# Proposal: preserve required PR platform check

## Why

Dev Platform v1.4.5 optimized generated CI so `publish_mode=direct` projects run automatic platform validation only on pushes to `main`. The first real rollout exposed an incompatibility with repositories whose branch protection still requires the `platform-ci` status on pull requests: Cuby rollout PR #12/#13 and Planner Agent Lab rollout PR #14 cannot become mergeable because the required check is expected but the generated direct-mode workflow no longer listens to pull requests.

The cost optimization remains valid, but it must not make reviewed maintenance/rollout PRs impossible to merge.

## What Changes

- Keep `publish_mode=pr` behavior unchanged: pull-request validation + manual dispatch, no duplicate main-push platform run.
- For `publish_mode=direct`, keep the normal main-push validation path and restore a pull-request compatibility trigger so required `platform-ci` checks can still be produced for reviewed maintenance/rollout PRs.
- Keep concurrency cancellation for superseded validation runs.
- Clarify generated documentation that normal direct publication still incurs one automatic main validation, while an explicitly used PR receives its own compatibility gate.
- Release the fix as a new immutable patch and roll managed projects forward through reviewed Copier PRs.

## Affected Projects and Updates

This affects both new project rendering and existing-project Copier updates. The generated `.github/workflows/dev-platform.yml` and workflow guidance change for `publish_mode=direct`. `publish_mode=pr` output remains semantically unchanged.

## Universal vs Profile-Specific Behavior

Universal behavior: platform/OpenSpec hygiene remains required, concurrency cancellation remains enabled, and release/rollout side-effect workflows remain non-cancellable.

Publish-mode-specific behavior: PR projects validate on PRs; direct projects validate published `main` and also expose the same named check on PRs used for reviewed maintenance compatibility.

## Compatibility Risks

The direct-mode compatibility PR trigger can add one extra lightweight platform validation when a direct-publish repository intentionally opens a PR. That is preferable to a permanently unmergeable protected PR and does not restore duplicate product full suites. Normal direct publication without a PR still runs only once on `main`.

## Non-goals

- Do not change project-owned product CI.
- Do not weaken or remove required status checks.
- Do not auto-merge rollout PRs.
- Do not reintroduce the central three-profile CI matrix.

## Definition of Done

- Direct-mode generated CI can satisfy a required `platform-ci` PR check while retaining main-push validation.
- PR-mode generated CI remains PR-only.
- Template contract tests cover both modes and concurrency behavior.
- Generated docs describe the compatibility exception accurately.
- Semantic verification passes, the change is archived, a patch release is published, and managed rollout PRs can run their required checks.
