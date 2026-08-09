# Proposal: respect project harness during managed rollout validation

## Why

The v1.4.6 managed rollout exposed a mismatch between the established `harness_mode=project` ownership contract and the central rollout helper. `run_project_validation()` always invoked downstream `scripts/select_checks.py --execute`, even when that selector is explicitly project-owned. Jara_Fin correctly preserves a project-owned selector whose CLI does not accept `--execute`, so the rollout failed after Copier update and platform doctor despite the project harness itself being healthy.

This behavior contradicts the mature-project adoption boundary: Dev Platform may validate platform/OpenSpec hygiene, but it must not assume or drive a project-owned selector contract during managed rollout.

## What Changes

- Managed rollout SHALL branch validation by `harness_mode`.
- `harness_mode=platform` keeps the existing platform-managed selected-check execution.
- `harness_mode=project` runs platform doctor and other platform-owned hygiene only, then delegates application/product checks to downstream repository CI.
- Add regression coverage proving a project-owned selector with no `--execute` support is not invoked by rollout validation.
- Keep rollout fail-closed behavior for platform doctor failures, Copier conflicts, diff errors, version mismatch and other platform-owned validation failures.

## Affected Projects and Updates

This changes only central rollout tooling and its tests/specification. No downstream template file needs to change. Existing immutable platform releases remain immutable; a patch release is still appropriate so the release-triggered rollout retries all managed repositories with the corrected central behavior.

## Compatibility Risks

Project-owned harness repositories will no longer run product/application checks inside the central rollout preparation job. That is intentional: their own PR CI remains the authoritative validation layer before merge. Platform-owned harness repositories retain the current selected-check validation.

## Non-goals

- Do not change Jara_Fin's selector CLI.
- Do not weaken downstream PR CI.
- Do not change Copier ownership or generated platform CI behavior.
- Do not auto-merge rollout PRs.

## Definition of Done

- Central rollout validation does not invoke project-owned `select_checks.py` for `harness_mode=project`.
- Platform-owned harness rollout still invokes selected checks.
- Unit tests cover both ownership modes.
- Platform CI and strict OpenSpec validation pass.
- The change is verified/archived and published as the next immutable patch release so managed rollout can complete for all registered projects.
