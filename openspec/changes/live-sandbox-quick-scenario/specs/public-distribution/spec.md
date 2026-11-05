## ADDED Requirements

### Requirement: Live sandbox identity stays outside public snapshots

The public distribution candidate set SHALL exclude `dev-platform/live-sandbox/sandbox.toml`, because it names the operator's private sandbox repository and App rather than reusable platform source. The exclusion SHALL apply equally to audit, digest and archive construction and SHALL NOT exempt other product files, including the sandbox fixture overlay, from operator-reference or secret findings.

#### Scenario: Sandbox identity is present

- **GIVEN** a tracked sandbox identity file and otherwise valid product files
- **WHEN** a public snapshot is audited and built
- **THEN** the file is absent from the candidate set and archive
- **AND** other product files remain subject to the existing findings policy
