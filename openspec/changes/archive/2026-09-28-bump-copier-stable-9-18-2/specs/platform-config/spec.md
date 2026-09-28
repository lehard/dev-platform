# platform-config Specification Delta

## ADDED Requirements

### Requirement: Platform tests one explicit, current-stable Copier version

The platform SHALL record one explicit tested Copier version and SHALL keep every recorded copy of it -- `.dev-platform.toml`, `template/.dev-platform.toml.jinja`, `copier.yml`'s `_min_copier_version`, every CI workflow that installs Copier, and `template/scripts/platform_doctor.py`'s fallback default -- in agreement. Changing the tested version SHALL be an explicit platform change, made only after confirming the target version against the primary upstream release source, not adopted merely because a newer number exists or via a prerelease.

#### Scenario: Tested Copier version is bumped

- **GIVEN** a platform change raises the tested Copier version
- **WHEN** the change is applied
- **THEN** `.dev-platform.toml`, `template/.dev-platform.toml.jinja`, `copier.yml`, every Copier-installing CI workflow, and the doctor's fallback default all reference the same new version
- **AND** regression coverage asserts that agreement so no copy is left stale

#### Scenario: Doctor validates an unconfigured project

- **GIVEN** a downstream project has no explicit `[tools.copier]` table
- **WHEN** the platform doctor checks the installed Copier version
- **THEN** it falls back to the platform's currently tested version, not an earlier one left over from a prior bump
