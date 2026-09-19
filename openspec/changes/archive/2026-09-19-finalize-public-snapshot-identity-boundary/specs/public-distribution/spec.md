## ADDED Requirements

### Requirement: Public product identity excludes operator integrations

The fresh public source snapshot SHALL distinguish the canonical Dev Platform source identity from optional operator integration identities. A Development Backlog repository, managed-project registry, bot account, GitHub Project, or downstream repository SHALL NOT be treated as canonical product identity merely because the current operator uses it.

#### Scenario: Generic source references optional Development Backlog behavior
- **WHEN** public tests, accepted specs, examples, or documentation describe Development Backlog integration
- **THEN** they use synthetic/example repository identity or configuration placeholders
- **AND** they do not require or allowlist the current operator's concrete backlog repository.

#### Scenario: Operator enables Development Backlog
- **WHEN** an installed project explicitly enables the operator layer
- **THEN** the concrete backlog repository/project identity is read from external operator configuration
- **AND** that concrete identity is not committed into the generic Dev Platform source snapshot.

### Requirement: One-shot cutover deny data is external to the shipped product

Private repository names, code names, compatibility markers, and other operator-history values needed only to sanitize the pre-cutover source SHALL be supplied through a bounded external cutover input or equivalent non-shipped mechanism. The public sanitizer implementation SHALL NOT encode those private values, including through split literals or other self-avoidance tricks.

#### Scenario: Old source requires private-name scanning before snapshot
- **GIVEN** the operator has a local cutover policy containing known private repository or compatibility markers
- **WHEN** public audit/snapshot runs with that explicit policy
- **THEN** findings from those markers block the snapshot
- **AND** the external policy file itself is not added to the candidate set or tar snapshot
- **AND** diagnostics identify the finding class/path without copying private values into generated public artifacts.

#### Scenario: Public repository runs audit after fresh cutover
- **WHEN** the fresh canonical public repository is audited without the old operator cutover policy
- **THEN** reusable product-level sanitization still checks secrets, prohibited operator state, source completeness, and non-canonical owner/repository references according to its generic policy
- **AND** the shipped source contains no private-name denylist from the old installation.

### Requirement: External cutover policy is explicit and fail-closed

If an external cutover policy is requested, its schema and source SHALL be explicit. Missing, unreadable, malformed, or ambiguous policy input SHALL fail before snapshot creation rather than silently dropping the additional deny rules.

#### Scenario: Explicit policy path is invalid
- **WHEN** the operator invokes audit/snapshot with an external cutover-policy path that cannot be read or validated
- **THEN** the command exits non-zero with an actionable policy error
- **AND** no snapshot is produced.

#### Scenario: Policy is valid
- **WHEN** the supplied policy passes schema validation
- **THEN** its bounded deny repositories/markers are applied in addition to reusable public checks
- **AND** the audit receipt records policy provenance in non-sensitive form (for example path basename/schema version/digest) without embedding the deny values themselves.

### Requirement: Final public snapshot contains no operator-history identity

On the exact cutover revision, the snapshot candidate SHALL contain no current-operator backlog repository identity and no named private downstream compatibility data. Synthetic fixtures SHALL remain allowed.

#### Scenario: Final external-policy audit is clean
- **WHEN** current-tree audit with the operator's cutover policy, bounded history-secret audit, and extracted snapshot smoke all succeed on the same exact source revision
- **THEN** the snapshot is eligible for the later owner/admin fresh-history cutover
- **AND** the reusable shipped sanitizer itself passes the same candidate audit without containing the private deny data it used during migration.
