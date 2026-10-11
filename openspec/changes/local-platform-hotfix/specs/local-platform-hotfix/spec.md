# local-platform-hotfix Specification

## Purpose

Let an installed project repair a reproducible defect in a hotfixable platform-owned script without waiting for a release, through a declared, traceable and temporary hotfix whose divergence from the release manifest is checked explicitly.

## ADDED Requirements

### Requirement: Platform release carries a file manifest

Each platform release SHALL carry a manifest of the sha256 of every plain-copied platform-owned file. A platform test SHALL fail when the manifest does not match the template tree.

#### Scenario: Stale manifest

- **GIVEN** a template script changed without regenerating the manifest
- **WHEN** platform validation runs
- **THEN** it fails naming the mismatching path.

### Requirement: Local hotfix is declared, traceable and temporary

The platform SHALL allow a downstream project to repair a reproducible defect in a hotfixable platform-owned script only through its ordinary PR, CI and independent review, and only with a project-owned hotfix record naming the patched paths, the source platform version, the patched digests, a regression test that exposes the defect, the friction event id together with a committed, sanitized copy of that friction event bound by digest, and an explicit statement that the divergence is temporary and not an official release.

#### Scenario: Valid hotfix

- **GIVEN** a hotfixable script is patched and a complete record exists
- **WHEN** the divergence check runs
- **THEN** it passes and reports the hotfix, its source version and its patched paths.

### Requirement: Divergence check fails explicitly on undeclared or unsafe divergence

The divergence check SHALL fail with a message naming the class and path when a platform-owned file differs from the manifest without a valid record, a record touches a protected or unknown path, a protected file, including the protected surface, the divergence check and the blocking-gate catalog, differs from the manifest, a record's platform version differs from the installed version, a patched digest does not match, or the regression test or the committed friction evidence is missing, invalid or does not match its recorded digest. It SHALL NOT report a failed condition as a passed check and SHALL NOT substitute a default.

#### Scenario: Patch to a protected file

- **GIVEN** a record names a protected path
- **WHEN** the check runs
- **THEN** it fails as a protected touch.

#### Scenario: Update after a hotfix

- **GIVEN** the platform version changed after the record was written
- **WHEN** the check runs
- **THEN** it fails as a stale hotfix and does not modify the record.

### Requirement: The local divergence check states the limit of local self-attestation

The platform SHALL document that the divergence check compares files with a manifest that is itself a local file, so an edit that changes a protected file, the manifest and the check consistently cannot be detected locally; the check SHALL NOT claim to detect that edit. Such tampering SHALL remain covered by the Copier update diff against the released template and by the mandatory independent review of every PR.

#### Scenario: Consistent local forgery

- **GIVEN** an agent edits a protected file and regenerates the manifest consistently
- **WHEN** the divergence check runs
- **THEN** the check does not report it
- **AND** the documentation names the Copier update diff and independent review as the detection path.

### Requirement: Friction evidence is verifiable from committed data

The divergence check SHALL verify a hotfix's friction evidence only from data committed in the project, so that it behaves identically on a developer machine and on CI. It SHALL NOT read, require or silently skip the machine-local friction log in its default mode. Cross-checking the event against the machine-local friction log SHALL be an explicit, separately requested mode that fails when the log is absent or unreadable.

#### Scenario: Valid hotfix on CI

- **GIVEN** a valid hotfix whose sanitized friction evidence is committed and matches its recorded digest
- **AND** the runner has no machine-local friction log
- **WHEN** the divergence check runs in its default mode
- **THEN** it passes.

#### Scenario: Altered or missing evidence

- **GIVEN** the committed friction evidence is absent, malformed, names another event, is not platform scope, or was edited after the record was written
- **WHEN** the divergence check runs
- **THEN** it fails with the missing-friction-event class naming the cause.

#### Scenario: Explicit local mode

- **GIVEN** the explicit local-log mode is requested and the machine-local log is absent, unreadable or lacks the event
- **WHEN** the divergence check runs
- **THEN** it fails and never accepts the event silently.

### Requirement: Hotfix uses existing mechanisms only

The hotfix flow SHALL reuse the project's Git, PR, friction and release/Copier mechanisms and SHALL NOT introduce a service, orchestrator or parallel state registry. The record file SHALL survive Copier updates.

#### Scenario: Copier update preserves the record

- **WHEN** an existing project updates by Copier
- **THEN** `dev-platform/local-hotfixes.toml` is unchanged.
