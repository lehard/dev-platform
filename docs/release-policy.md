# Platform release policy

Downstream repositories must not execute reusable CI from `dev-platform@main` because that bypasses reviewed Copier upgrades.

## Rule

A downstream project records a concrete `platform_ci_ref` in `.dev-platform.toml`. Prefer a full commit SHA because it is immutable. Human-readable release refs exist for navigation and release identity, but are not required for downstream execution.

For v1.0.0:

- release alias: `release-v1.0.0`;
- validated release commit: `b4a95a26c7caf14dd5b0d44da0237dcd70bf8715`;
- generated-project default: the exact commit SHA above.

Release aliases are append-only and must never move after publication.

## Upgrade

`dev-platform new release -> reviewed Copier update PR -> downstream CI on new immutable SHA -> merge`

There is no silent remote workflow upgrade channel.
