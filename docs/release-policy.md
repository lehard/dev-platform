# Platform release policy

Downstream repositories must not execute reusable CI from `dev-platform@main` because that bypasses reviewed Copier upgrades.

## Rule

A downstream project records a versioned platform release and a concrete `platform_ci_ref` in `.dev-platform.toml`. The generated workflow uses that ref. Existing release refs are append-only: never move or rewrite them after publication.

For maximum immutability, downstream projects should ultimately pin reusable workflows to a full commit SHA. The v1 bootstrap uses the human-readable `release-v1.0.0` release ref while the first release is cut; once the validated v1 commit SHA exists, the factory default can be pinned to that SHA without changing the release contents.

## Upgrade

`dev-platform new release -> reviewed Copier update PR -> downstream CI on new ref -> merge`

There is no silent remote workflow upgrade channel.
