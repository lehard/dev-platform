# Design: Private operator registry repository

## Root cause

`managed_projects.py load_registry()`/`save_registry()` already treat `--registry` as an arbitrary filesystem path and were never the problem. Only the three workflow YAML files hardcoded a path (`platform/managed-projects.json`) inside the checked-out public `lehard/dev-platform` repository itself, and `adopt-project.yml`'s promotion step committed and pushed directly to that repo's `main`. `docs/managed-rollout.md` and `docs/operator-config.example.toml` already correctly describe the registry as external/operator-owned; only the CI implementation diverged from that already-documented contract.

## Mechanism

A GitHub Actions runner has no access to an operator's local filesystem, so CI resolves the registry from a second, private GitHub repository instead of a local path:

1. `DEV_PLATFORM_OPERATOR_REPOSITORY` (repository variable, `owner/name`, non-secret) names the private repository generically.
2. Each workflow's first step fails closed with an explicit message (matching the existing `DEV_PLATFORM_APP_CLIENT_ID`/`DEV_PLATFORM_APP_PRIVATE_KEY` check's style) if the variable is unset.
3. A GitHub App token is minted scoped only to that repository (`contents: read` for `rollout.yml`/`reconcile-stale-rollouts.yml`'s read-only matrix planning; `contents: write` for `adopt-project.yml`'s promotion).
4. The repository is checked out to a local `operator/` path.
5. `--registry operator/managed-projects.json` is passed to every `scripts/managed_projects.py` invocation. No Python code changes.
6. `adopt-project.yml`'s promotion step commits/pushes inside the `operator/` checkout to the operator repository's own `main`, exactly as it previously did against `platform/` -- only the target repository changed.

A local operator checkout resolves the identical registry by cloning the private repository once and pointing the external operator TOML's `rollout.registry_path` at the clone's `managed-projects.json`; `--registry`/`registry_path` already accept any filesystem path, so no local-side code change is needed either.

## Explicitly out of scope

- The registry schema (`schema_version`, `managed`/`candidate`/`excluded`) is unchanged.
- `managed_projects.py`, `operator_doctor.py`: unchanged.
- Any new Python-level "remote registry" resolution mode (e.g. fetching via `gh api` without a checkout): the plain-checkout approach reuses the exact same `actions/checkout` + App-token pattern every other cross-repository step in these workflows already uses, so it introduces no new mechanism.
- Populating the operator repository with real fleet data: this change ships only an empty seed (`{"schema_version": 1, "projects": []}`); onboarding real repositories happens through the normal, already-existing Adopt Project flow afterward.

## Tests

Update the existing workflow-content contract tests (`tests/test_managed_rollout.py`, `tests/test_rollout_supersession.py`) to assert the new `operator/managed-projects.json` path and the added GitHub App token step, and assert the absence of `platform/managed-projects.json` in `rollout.yml`/`adopt-project.yml`. No fixture or Python-level test changes needed since the schema and CLI are unchanged.
