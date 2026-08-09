# Design: respect project harness during managed rollout validation

## Approach

Keep central rollout validation split into two layers:

1. Universal platform-owned validation for every managed repository:
   - no unresolved Copier rejection;
   - `git diff --check`;
   - rendered `platform_doctor.py`;
   - version/metadata coherence already enforced by rollout preparation.
2. Harness-owned validation:
   - `harness_mode=platform`: invoke rendered `scripts/select_checks.py --base origin/<main> --execute` as today;
   - `harness_mode=project`: do not invoke the downstream selector at all. The rollout PR's repository CI owns application/product verification.

This uses the already-recorded `.dev-platform.toml` `harness_mode`; no new configuration is introduced.

## Why not probe selector capabilities

A project-owned selector is an opaque project contract. Detecting whether it happens to support `--execute` would still make central rollout behavior depend on implementation details it does not own. Ownership, not capability probing, determines whether Dev Platform may invoke it.

## Failure semantics

Platform-owned failures remain blocking. For project harnesses, absence or behavior of the project-owned selector is not a central-rollout failure; downstream PR CI remains the merge gate.

## Tests

Patch `run()` in focused unit tests and create minimal `.dev-platform.toml` fixtures for both harness modes. Assert that:

- project mode runs diff + doctor but no selector command;
- platform mode continues to call selector with the existing `--execute` contract.

## Rollout

Because the release workflow dispatches rollout from the release commit, publish the next patch after this central-tool fix lands. The new rollout can upgrade directly from any older immutable version; stale v1.4.5/v1.4.6 rollout PRs can then be superseded.
