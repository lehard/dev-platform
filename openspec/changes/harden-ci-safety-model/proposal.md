# Proposal: Harden CI safety model

## Why

The GitHub Actions cost reduction introduced in v1.4.8 removed redundant post-merge heavy runs, but a safety review found several cases where the remaining gates can be weaker or more ambiguous than intended:

- project-owned direct-publish repositories can skip their authoritative product QA;
- required status checks can omit dynamically selected backend/frontend jobs;
- platform-owned selected checks can miss dependency/configuration files;
- manual full checks can share a cancellation group with lightweight main-branch health runs;
- duplicate required check names can exist across workflows;
- managed rollout execution is not fully pinned to the release being rolled out.

These are correctness/safety issues, not merely CI-cost concerns.

## Goal

Make the reduced-cost CI model fail closed: a repository must not appear safely mergeable/publishable unless the checks that define its risk model have actually passed, while preserving the cost savings from avoiding redundant post-merge full suites.

## Scope

- Define explicit safety invariants for `publish_mode`, `harness_mode`, branch protection, and authoritative QA.
- Make generated Dev Platform workflow concurrency event-aware so manual full runs cannot be cancelled by ordinary main pushes.
- Strengthen platform-owned check selection for dependency/configuration/schema files.
- Make managed rollout tooling execute from the exact immutable release tag being rolled out.
- Add tests for the above invariants.
- Prepare downstream corrections for Cuby, Planner Agent Lab, and Jara_Fin.

## Non-goals

- Reintroduce full project suites on every push to `main`.
- Auto-merge rollout PRs.
- Replace repository-owned QA in `harness_mode=project` repositories.
- Change product/business behavior in downstream repositories.
