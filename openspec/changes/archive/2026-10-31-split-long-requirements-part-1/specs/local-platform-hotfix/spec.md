## MODIFIED Requirements

### Requirement: Local hotfix is declared, traceable and temporary

The platform SHALL allow a downstream project to repair a reproducible defect in a hotfixable platform-owned script only through its ordinary PR, CI and independent review.

#### Scenario: Valid hotfix

- **GIVEN** a hotfixable script is patched and a complete record exists
- **WHEN** the divergence check runs
- **THEN** it passes and reports the hotfix, its source version and its patched paths.

### Requirement: Divergence check fails explicitly on undeclared or unsafe divergence

The divergence check SHALL fail with a message naming the class and path when a record touches a protected or unknown path, a protected file, including the protected surface, the divergence check and the blocking-gate catalog, differs from the manifest, or a record's platform version differs from the installed version.

#### Scenario: Patch to a protected file

- **GIVEN** a record names a protected path
- **WHEN** the check runs
- **THEN** it fails as a protected touch.

#### Scenario: Update after a hotfix

- **GIVEN** the platform version changed after the record was written
- **WHEN** the check runs
- **THEN** it fails as a stale hotfix and does not modify the record.

## ADDED Requirements

### Requirement: Local hotfix requires a complete project-owned hotfix record

The platform SHALL allow a downstream project to repair a reproducible defect in a hotfixable platform-owned script only with a project-owned hotfix record naming the patched paths, the source platform version, the patched digests, a regression test that exposes the defect, the friction event id together with a committed, sanitized copy of that friction event bound by digest, and an explicit statement that the divergence is temporary and not an official release.

#### Scenario: Hotfix without a complete record

- **WHEN** a downstream project repairs a defect in a hotfixable platform-owned script
- **THEN** the repair is allowed only with a project-owned hotfix record naming the patched paths, the source platform version, the patched digests, a regression test that exposes the defect, the friction event id with a committed, sanitized copy of that friction event bound by digest
- **AND** the record states explicitly that the divergence is temporary and not an official release

### Requirement: Divergence check fails on an undeclared platform-owned divergence

The divergence check SHALL fail with a message naming the class and path when a platform-owned file differs from the manifest without a valid record.

#### Scenario: Undeclared divergence

- **WHEN** a platform-owned file differs from the manifest without a valid record
- **THEN** the divergence check fails with a message naming the class and path

### Requirement: Divergence check fails on invalid hotfix digests or evidence

The divergence check SHALL fail with a message naming the class and path when a patched digest does not match, or the regression test or the committed friction evidence is missing, invalid or does not match its recorded digest.

#### Scenario: Digest or evidence mismatch

- **WHEN** a patched digest does not match, or the regression test or the committed friction evidence is missing, invalid or does not match its recorded digest
- **THEN** the divergence check fails with a message naming the class and path

### Requirement: Divergence check never reports a failure as a pass

The divergence check SHALL NOT report a failed condition as a passed check and SHALL NOT substitute a default.

#### Scenario: Condition fails

- **WHEN** a divergence check condition fails
- **THEN** the check does not report it as passed
- **AND** no default is substituted
