# Design: Copier stable version bump (9.17.0 -> 9.18.2)

## Approach

Pure version-bump: update every literal occurrence of the tested Copier
version to `9.18.2` (config, template, CI, doctor fallback, docs, tests) and
prove the platform's existing render/update/rollout/doctor checks still pass
against the new version. No new abstraction, subsystem, or spec requirement
is introduced -- `openspec/specs/` does not encode a specific tool version
number today, only the general "min/tested CLI version" contract in
`docs/engineering/openspec-workflow.md`, so no spec delta is required for
this change; only the recorded literal values move.

## Risks and mitigations

- **CI/release lifecycle risk**: four `.github/workflows/*.yml` files install
  Copier for their own runs (`ci.yml`, `publish-version.yml`, `rollout.yml`,
  `adopt-project.yml`). Mitigation: change all four in the same commit so no
  workflow is left pinned to a version the rest of the contract no longer
  tests; full suite is already forced by `dev-platform/checks.toml`
  `full_trigger_patterns` (`.dev-platform.toml`, `.github/workflows/**`,
  `template/scripts/**`, `scripts/**`, `tests/**` all match this change).
- **Downstream managed-project rollout risk**: `docs/managed-rollout.md`
  documents that rollout runs Copier `9.17.0` against the exact release tag.
  Mitigation: update that prose alongside the version bump so operator
  documentation does not silently drift from the actual pinned version (`No
  silent divergence`), and rely on `test_template_contract.py` plus a real
  local render/update smoke (Copier is installable locally) rather than
  asserting behavior without exercising it.
- **Silent duplicate-literal drift**: `template/scripts/platform_doctor.py`
  hardcodes `{"min_version": "9.17.0", "tested_version": "9.17.0"}` as a
  fallback when `tools.copier` is absent from a project's config. Left
  unchanged, this fallback would silently keep validating against the old
  version for any project without an explicit `[tools.copier]` table.
  Mitigation: bump this literal in the same change.
- **Trust-boundary regression risk (the reason for the bump)**: verify the
  new version's advertised trusted-prefix/repository-URL fixes (9.18.0,
  9.18.2) are what upstream's own changelog attributes to those releases
  (confirmed via the GitHub releases page, the primary release channel,
  cross-checked against PyPI's version/date history) rather than trusting
  the version number alone.
- **In-house workaround duplication risk**: checked whether this repository
  carries a parallel workaround for Copier's prior trusted-URL matching gaps
  that the upstream fix would make redundant. `template/scripts/rollout_identity.py`
  and `scripts/rollout_supersession.py` both use the phrase "trust boundary"
  but implement this platform's own GitHub PR/rollout-ownership trust
  boundary (branch name, base branch, bot identity), unrelated to Copier's
  template-source repository-URL matching. No workaround exists to remove.

## Alternatives considered

- Waiting for a later stable release: rejected -- the issue explicitly asks
  to confirm and adopt the current stable release, and the exclusions
  disallow chasing a prerelease; `9.18.2` is the current stable head with no
  newer prerelease pending.
- Vendoring a stricter URL-trust check inside this platform ahead of Copier:
  rejected by the issue's own exclusions ("не добавлять собственный security
  subsystem поверх Copier, если достаточно upstream stable fix"), and
  unnecessary since the upstream fix already covers the described class of
  issue.
