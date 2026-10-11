## ADDED Requirements

### Requirement: Platform release carries a file manifest

Each platform release SHALL carry a manifest of the sha256 of every plain-copied platform-owned file. A platform test SHALL fail when the manifest does not match the template tree.

#### Scenario: Stale manifest

- **GIVEN** a template script changed without regenerating the manifest
- **WHEN** platform validation runs
- **THEN** it fails naming the mismatching path.

### Requirement: Local hotfix is declared, traceable and temporary

The platform SHALL allow a downstream project to repair a reproducible defect in a hotfixable platform-owned script only through its ordinary PR, CI and independent review, and only with a project-owned hotfix record naming the patched paths, the source platform version, the patched digests, a regression test that exposes the defect, the friction event id and an explicit statement that the divergence is temporary and not an official release.

#### Scenario: Valid hotfix

- **GIVEN** a hotfixable script is patched and a complete record exists
- **WHEN** the divergence check runs
- **THEN** it passes and reports the hotfix, its source version and its patched paths.

### Requirement: Divergence check fails explicitly on undeclared or unsafe divergence

The divergence check SHALL fail with a message naming the class and path when a platform-owned file differs from the manifest without a valid record, a record touches a protected or unknown path, the protected surface or manifest is modified, a record's platform version differs from the installed version, a patched digest does not match, or the regression test or friction reference is missing or unreadable. It SHALL NOT report a failed condition as a passed check and SHALL NOT substitute a default.

#### Scenario: Patch to a protected file

- **GIVEN** a record names a protected path
- **WHEN** the check runs
- **THEN** it fails as a protected touch.

#### Scenario: Update after a hotfix

- **GIVEN** the platform version changed after the record was written
- **WHEN** the check runs
- **THEN** it fails as a stale hotfix and does not modify the record.

### Requirement: Hotfix uses existing mechanisms only

The hotfix flow SHALL reuse the project's Git, PR, friction and release/Copier mechanisms and SHALL NOT introduce a service, orchestrator or parallel state registry. The record file SHALL survive Copier updates.

#### Scenario: Copier update preserves the record

- **WHEN** an existing project updates by Copier
- **THEN** `dev-platform/local-hotfixes.toml` is unchanged.
