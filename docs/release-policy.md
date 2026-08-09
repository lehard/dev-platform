# Platform release policy

Platform updates reach downstream repositories through reviewed Copier updates, never by executing mutable `dev-platform@main` logic.

## Release identity

Copier releases use immutable SemVer Git tags such as `v1.0.0` and `v1.0.1`. Published tags must never move or be reused; GitHub Immutable Releases should remain enabled.

## Downstream CI ownership

Starting with `v1.0.1`, generated project CI is self-contained: the Copier-managed workflow runs the Copier-managed `scripts/select_checks.py` from the downstream checkout using SHA-pinned GitHub Actions. It does not require private cross-repository reusable-workflow access.

This keeps the same review boundary:

`dev-platform release -> exact-version Copier update PR -> downstream CI/review -> merge`

There is no silent remote workflow upgrade channel. `platform_ci_ref` remains in schema v2 for backward compatibility with v1.0.0 projects but is no longer required by the generated CI workflow.

## Managed rollout

`managed-projects.json` is the explicit downstream project inventory and cross-repository allowlist. Only entries in state `managed` are eligible for central rollout. `candidate` means reviewed first-time adoption is still expected; `excluded` records an intentional non-adoption decision. Neither non-managed state may be mutated by rollout.

After a version is published, the release workflow dispatches the rollout workflow for that exact immutable tag. Rollout uses a least-privilege GitHub App with separate read-only platform-source and target-write tokens. The target token includes Workflows write because platform-managed updates can include `.github/workflows/*`. Rollout performs Copier update/doctor/project checks on a deterministic automation branch and opens a downstream PR. It does not auto-merge by default.

A blocked project does not stop other matrix entries. Conflicts, wrong/missing Copier ownership metadata, downgrade attempts, validation failures or unexpected branch collisions fail closed without changing the downstream default branch.

See `docs/managed-rollout.md` for registry ownership, one-time App setup and recovery.

## Upgrade safety

Platform CI must test both fresh rendering and `copier update` from the previous stable tag while preserving project-owned changes and rejecting unresolved `*.rej`/Git conflict artifacts.

Managed rollout must target an actually published immutable release tag using Copier `--vcs-ref`; it must never consume mutable `main` as the downstream upgrade source.

## Copier version

The platform tests Copier `9.17.0` exactly. Changing the tested version is an explicit platform change.

## Version publication

`VERSION` changes only in an explicit release PR. After merge, `.github/workflows/publish-version.yml` creates `v<VERSION>` at that exact commit, refuses to move an existing tag, and dispatches managed rollout for the exact published tag.
