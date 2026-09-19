## ADDED Requirements

### Requirement: Public audit covers the exact public snapshot candidate set

The public-distribution lifecycle SHALL derive one deterministic candidate file set and SHALL use that same set for sanitization and snapshot packaging. A successful audit SHALL NOT permit a file into the fresh-history snapshot that was outside the sanitization decision.

#### Scenario: Candidate file contains prohibited owner/project state
- **GIVEN** a file is part of the public snapshot candidate set
- **WHEN** it contains owner/project-specific state prohibited by the public boundary
- **THEN** public-distribution audit fails with the bounded path/reason
- **AND** snapshot preparation is blocked until the file is sanitized, excluded by explicit product policy, or replaced with synthetic/public-safe content.

#### Scenario: Snapshot succeeds after audit
- **WHEN** public-distribution snapshot completes successfully
- **THEN** every packaged file belonged to the exact audited candidate set
- **AND** the snapshot cannot contain a file that bypassed owner-state or secret checks.

### Requirement: Public boundary distinguishes canonical product identity from private installation references

The public-distribution policy SHALL explicitly define which repository/owner references are legitimate public product identity and which are installation-specific references that must not enter the fresh-history product snapshot. Historical OpenSpec evidence, tests, docs, and rollout fixtures SHALL follow the same policy as source/template files.

#### Scenario: Canonical public repository reference is allowed
- **WHEN** a candidate file contains an explicitly allowed canonical public-product reference needed for installation or documentation
- **THEN** the audit may allow it under the documented allowlist/policy
- **AND** that allowance does not implicitly permit other repositories owned by the same account.

#### Scenario: Personal downstream repository reference remains
- **WHEN** a candidate file references a personal downstream project, private backlog, live fleet member, or installation-specific bot/account identity
- **THEN** the audit blocks the public snapshot unless the reference is replaced by synthetic/public-safe evidence or the file is explicitly excluded from the product distribution.

### Requirement: Current-tree sanitization and Git-history secret audit are separate truthful gates

The platform SHALL provide a bounded history audit for reachable Git history that looks for supported real-secret/credential classes and reports its examined scope and limitations. A clean current-tree audit SHALL NOT be described as a clean-history verdict.

#### Scenario: History audit finds a possible credential
- **WHEN** the bounded history audit finds a supported secret pattern in reachable history
- **THEN** it reports the commit/blob/path evidence in a bounded secret-safe form
- **AND** public cutover is blocked pending rotation/revocation and explicit remediation
- **AND** no automatic destructive history rewrite is performed.

#### Scenario: History audit is clean
- **WHEN** the supported history audit completes without findings
- **THEN** the receipt records the refs/range or object scope examined and supported pattern classes
- **AND** documentation states remaining limitations rather than claiming universal proof that no secret ever existed.

### Requirement: Public cutover evidence is generated from the final sanitized candidate

The cutover runbook SHALL require the final current-tree audit, bounded history audit, clean generic render, GitLab sandbox verification, and deterministic snapshot against the exact source revision intended for fresh-history initialization.

#### Scenario: Source changes after evidence was collected
- **WHEN** the source revision changes after one of the required cutover gates was recorded
- **THEN** the final snapshot is not considered cutover-ready until the affected gates are rerun against the new exact revision.
