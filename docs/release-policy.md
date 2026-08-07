# Platform release policy

Platform updates reach downstream repositories through reviewed Copier updates, never by executing mutable `dev-platform@main` logic.

## Release identity

Copier releases use immutable SemVer Git tags such as `v1.0.0` and `v1.0.1`. Published tags must never move or be reused; GitHub Immutable Releases should remain enabled.

## Downstream CI ownership

Starting with `v1.0.1`, generated project CI is self-contained: the Copier-managed workflow runs the Copier-managed `scripts/select_checks.py` from the downstream checkout using SHA-pinned GitHub Actions. It does not require private cross-repository reusable-workflow access.

This keeps the same review boundary:

`dev-platform release -> reviewed Copier update PR -> downstream CI -> merge`

There is no silent remote workflow upgrade channel. `platform_ci_ref` remains in schema v2 for backward compatibility with v1.0.0 projects but is no longer required by the generated CI workflow.

## Upgrade safety

Platform CI must test both fresh rendering and `copier update` from the previous stable tag while preserving project-owned changes and rejecting unresolved `*.rej`/Git conflict artifacts.

## Copier version

The platform tests Copier `9.17.0` exactly. Changing the tested version is an explicit platform change.

## Version publication

`VERSION` changes only in an explicit release PR. After merge, `.github/workflows/publish-version.yml` creates `v<VERSION>` at that exact commit and refuses to move an existing tag.
