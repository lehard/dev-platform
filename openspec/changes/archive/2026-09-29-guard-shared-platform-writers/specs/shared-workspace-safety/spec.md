## ADDED Requirements

### Requirement: Platform-owned shared file writers verify their published output

A supported platform-owned writer targeting a registered shared-workspace path SHALL publish its own file with group read and write permissions and SHALL verify the published inode before reporting success. A cooperative shell umask alone SHALL NOT count as proof. New supported writer entrypoints SHALL carry regression evidence for restrictive creation modes. Verification or repair SHALL remain confined to that writer's declared output and SHALL NOT modify another agent's files.

#### Scenario: Report is published under a restrictive umask

- **GIVEN** a Process Health Review report is published through the supported report entrypoint
- **AND** the caller has a restrictive umask
- **WHEN** the report is published in the registered friction reports path
- **THEN** the published inode is group readable and writable before the command succeeds

#### Scenario: Writer produces a noncompliant file

- **GIVEN** a platform-owned writer creates its declared shared output with mode 0644
- **WHEN** the writer verifies the publication boundary
- **THEN** the operation fails before reporting success or repairs only that newly published output and verifies it
- **AND** no neighboring or foreign-owned file is changed

#### Scenario: External editor creates a report

- **GIVEN** an editor outside the supported writer creates a machine-local report
- **WHEN** the post-review shared-workspace check runs
- **THEN** any missing group write is reported before the review is considered complete
- **AND** only the file owner is instructed to repair it
