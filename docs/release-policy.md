# Platform release policy

Downstream repositories must not execute reusable CI from `dev-platform@main` because that bypasses reviewed Copier upgrades.

## Release identity

Copier's update lifecycle is based on stable Git version tags. Platform releases therefore use normal SemVer tags such as `v1.0.0`.

A release tag is append-only: once published it must never be moved or reused. If GitHub immutable releases are available for the repository, enable them; otherwise the repository policy still forbids moving or deleting published platform version tags.

The old `release-v1.0.0` branch is not a Copier release and must not be used as a version source. It may remain only as a legacy navigation ref until it can be safely removed.

### Current v1 release

- Copier template tag: `v1.0.0`.
- Release commit: `ba03435a0c11da928807e2487506d1d24d8cfc39`.
- Generated reusable-CI pin: `dab74494c9a6ad9a77d99e73bb36774a6d42350d`.
- A matching GitHub Release `v1.0.0` is published.

## Downstream execution pin

A downstream project records a concrete `platform_ci_ref` in `.dev-platform.toml`. Reusable CI uses the full commit SHA, not `main` and not a movable major tag.

This deliberately separates:

- **Copier template version** — SemVer Git tag, for example `v1.0.0`;
- **executed reusable CI** — full immutable commit SHA stored in the generated project.

## Upgrade safety

The supported upgrade path is:

`stable platform tag -> generated project with project-owned customizations -> candidate Copier update -> conflict guard -> doctor/checks -> reviewed project PR`

Platform CI must exercise this path before a platform change is released. New-project rendering alone is not sufficient.

## Copier version

The platform currently tests Copier `9.17.0`. CI installs that exact version. The template declares it as the minimum compatible Copier version; moving the tested version is an explicit platform change, not an implicit dependency update.

## Version publication

`VERSION` is changed only in an explicit release commit/PR. When it changes on `main`, `.github/workflows/publish-version.yml` creates `v<VERSION>` at that exact commit and refuses to move an existing tag. It then creates the matching GitHub Release if one does not exist.

## Upgrade

`dev-platform release -> reviewed Copier update PR -> downstream CI on new immutable SHA -> merge`

There is no silent remote workflow upgrade channel.
