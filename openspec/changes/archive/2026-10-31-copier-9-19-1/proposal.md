## Why

The platform tests Copier 9.18.2. The current upstream stable (PyPI and the upstream changelog, confirmed 2026-10-30) is 9.19.1: 9.19.0 fixes argument injection through `git` subprocess calls (security) and keeps symlink targets when a directory containing a symlink is renamed; 9.19.1 restores support for Git older than 2.43.1. No prerelease is involved.

## What Changes

- Every recorded copy of the tested version moves to 9.19.1, per the accepted requirement "Platform tests one explicit, current-stable Copier version": `copier.yml` `_min_copier_version`, `template/.dev-platform.toml.jinja` `[tools.copier]`, the Copier installs in `.github/workflows/{ci,adopt-project,lifecycle-workers,publish-version,rollout}.yml`, `template/scripts/platform_doctor.py`'s default, docs (`docs/release-policy.md`, `docs/managed-rollout.md`, README) and the Explorer texts, and the template contract test.
- Spec: platform-config adds one scenario to the existing requirement: a new tested version is proven (render, update, rollback) before it is recorded.

## Impact

- Template-visible: `copier.yml` requires Copier 9.19.1 to update to this release; a new render records 9.19.1. Existing projects' `.dev-platform.toml` is skip-if-exists and keeps its `[tools.copier]` 9.18.2 values (still satisfied by 9.19.1).
- Operator steps outside the repository: install Copier 9.19.1 where the owner runs Copier locally, and update the untracked operator `.dev-platform.toml` `[tools.copier]` to 9.19.1 (machine-local, not changed by this change).
- Rollback: revert to a release pinning 9.18.2; answers written by 9.19.1 stay readable by 9.18.2 (checked).
