# Platform CI Specification Delta

## ADDED Requirements

### Requirement: Release candidates prove installed harness compatibility

Central platform CI and release publication SHALL run the same bounded installation validation before an immutable release is created. The validation SHALL use real Copier fresh installation and upgrade of representative officially supported configurations, including both GitHub harness ownership modes and the documented alternative SCM scope. It SHALL apply rollout-equivalent platform-owned hygiene and integrity checks to the resulting installations, including reject detection, diff hygiene, rendered platform doctor, and required platform surfaces. It SHALL NOT run downstream product or application tests.

#### Scenario: Release candidate has invalid generated whitespace

- **WHEN** an installed or upgraded candidate contains a diff hygiene failure
- **THEN** release installation validation fails before an immutable tag is published

#### Scenario: Required configuration or capability surface is missing

- **WHEN** a supported installation lacks a required rendered input or a selected capability surface
- **THEN** release installation validation fails before publication

#### Scenario: Harness ownership differs

- **WHEN** both supported GitHub harness ownership modes are validated
- **THEN** each mode receives platform-owned installation checks
- **AND** neither mode executes downstream product/application tests
