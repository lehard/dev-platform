# public-distribution Specification Delta

## ADDED Requirements

### Requirement: Shared integration operator provenance stays outside public snapshots

The public distribution candidate set SHALL exclude committed Requirement integration manifests under `dev-platform/requirement-integrations/`, because they carry operator-specific Backlog references needed for protected reconciliation rather than reusable platform source. The exclusion SHALL apply equally to audit, digest and archive construction, and SHALL NOT exempt other product files from operator-reference or secret checks.

#### Scenario: Shared candidate manifest is present

- **GIVEN** a tracked shared Requirement integration manifest and otherwise valid product files
- **WHEN** a public snapshot is audited and built
- **THEN** the manifest is absent from the candidate set and archive
- **AND** other product files remain subject to the existing findings policy
