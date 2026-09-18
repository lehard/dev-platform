# public-distribution Specification

## Purpose
Define the portable public distribution boundary, sanitization checks, and non-destructive cutover requirements for Dev Platform.
## Requirements
### Requirement: Public distribution is sanitized from operator-specific state

A canonical public Dev Platform release/source snapshot SHALL be validated to exclude live operator inventory, account-specific defaults and private installation state that are not part of the generic product. The validation SHALL distinguish ordinary owner/project references that require product cleanup from actual secrets or sensitive payload that require security remediation.

#### Scenario: Sanitized public snapshot is prepared
- **WHEN** a public snapshot is prepared for canonical distribution
- **THEN** current source and rendered default output are checked for operator-specific inventory/defaults prohibited by the public boundary
- **AND** test fixtures/examples use synthetic or explicitly public-safe values
- **AND** the snapshot is blocked until prohibited live operator state is removed.

#### Scenario: Audit finds a real credential or secret
- **WHEN** current tree or bounded history audit identifies a real credential, secret or sensitive payload
- **THEN** the finding is treated as a security incident
- **AND** rotation/revocation is required before repository-history cleanup is considered complete
- **AND** the process does not claim that deleting a Git reference alone invalidates an already exposed credential.

### Requirement: Clean public history is established without destructive rewrite for ordinary references

The ordinary productization path SHALL create the new canonical public repository history from a verified sanitized snapshot rather than rewriting the existing public repository history solely to remove non-sensitive operator/project names. The old repository SHALL remain a controlled migration source until cutover completes.

#### Scenario: Old history contains only non-sensitive operator references
- **GIVEN** the history audit finds project names, old operator defaults or process references but no unrotated secrets requiring emergency removal
- **WHEN** the canonical public repository is established
- **THEN** it starts from the verified sanitized snapshot with fresh history
- **AND** the old history is not destructively rewritten as a cosmetic step
- **AND** downstream/source cutover follows an explicit migration sequence.

#### Scenario: Public cutover is not yet proven
- **WHEN** the sanitized snapshot has not passed clean render and client-like sandbox verification
- **THEN** the new public repository is not declared canonical
- **AND** existing consumers are not silently redirected or migrated.
