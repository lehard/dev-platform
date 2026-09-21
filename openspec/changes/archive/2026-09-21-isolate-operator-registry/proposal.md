# Proposal: Isolate the managed registry into a private operator repository

## Why

`openspec/specs/platform-rollout/spec.md` already requires managed fleet rollout to use "a private managed-projects registry," but `adopt-project.yml`, `rollout.yml`, and `reconcile-stale-rollouts.yml` all resolve `managed-projects.json` inside the public `lehard/dev-platform` checkout itself. This is an implementation bug against an already-accepted contract, discovered when the first real post-cutover Adopt Project run failed (`registry not found: platform/managed-projects.json`) and, if patched by simply seeding that path, would permanently record every managed fleet member's real repository name in `lehard/dev-platform`'s public git history.

## What Changes

- Add a private operator-owned GitHub repository (data only, not a fork or a second platform) holding `managed-projects.json`.
- Name it generically via a new non-secret repository variable `DEV_PLATFORM_OPERATOR_REPOSITORY`, never hardcoded in workflow or Python source.
- Update `adopt-project.yml`'s promotion step and `rollout.yml`/`reconcile-stale-rollouts.yml`'s planning steps to check out that repository with a narrowly-scoped GitHub App token and read/write the registry only there.
- Document the mechanism and the one-time GitHub App installation it requires on the operator repository.

## Success Evidence

None of the three workflows ever reference `platform/managed-projects.json` or otherwise resolve the registry from the public checkout; each fails closed with a clear message when `DEV_PLATFORM_OPERATOR_REPOSITORY` is unset; a real Adopt Project run reaches the promotion step and commits only into the private operator repository. No real fleet repository name appears in public source, tests, or docs.

## Dependencies

None. `scripts/managed_projects.py` and `scripts/operator_doctor.py` already accept an arbitrary filesystem `--registry` path and need no change.
