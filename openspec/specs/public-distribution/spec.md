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

### Requirement: Public audit covers the exact public snapshot candidate set

The public-distribution lifecycle SHALL derive one deterministic candidate
file set from the Git-tracked files of the current checkout (for example via
`git ls-files`) and SHALL use that same set for sanitization and snapshot
packaging, after applying the existing exclusion policy
(`EXCLUDED_PARTS`/`EXCLUDED_PATHS`) and any supplied external cutover-policy
exclusions. A successful audit SHALL NOT permit a file into the fresh-history
snapshot that was outside the sanitization decision. Untracked local files
(for example scratch notes, generated output, or other working-tree state
never committed to Git) SHALL NOT enter the candidate set, SHALL NOT
influence the candidate digest, and SHALL NOT produce audit findings, because
they are not part of the repository source the fresh public history is built
from. The command SHALL fail closed with an actionable error when it cannot
enumerate Git-tracked files (for example when run outside a Git checkout or
when `git` itself fails), rather than silently falling back to a full
filesystem walk.

#### Scenario: Candidate file contains prohibited owner/project state
- **GIVEN** a file is part of the public snapshot candidate set
- **WHEN** it contains owner/project-specific state prohibited by the public boundary
- **THEN** public-distribution audit fails with the bounded path/reason
- **AND** snapshot preparation is blocked until the file is sanitized, excluded by explicit product policy, or replaced with synthetic/public-safe content.

#### Scenario: Snapshot succeeds after audit
- **WHEN** public-distribution snapshot completes successfully
- **THEN** every packaged file belonged to the exact audited candidate set
- **AND** the snapshot cannot contain a file that bypassed owner-state or secret checks.

#### Scenario: Untracked local file is not part of the candidate set
- **GIVEN** the working tree contains an untracked file (not committed and not staged) that contains a prohibited owner/project reference or cutover-policy marker
- **WHEN** public-distribution audit or snapshot runs
- **THEN** that file does not appear in `candidate_files`
- **AND** it does not affect `candidate_sha256`
- **AND** it produces no finding
- **AND** it is not packaged into the snapshot archive.

#### Scenario: Tracked file with the same material still blocks the snapshot
- **GIVEN** a Git-tracked file contains the same class of prohibited owner/project reference or cutover-policy marker
- **WHEN** public-distribution audit runs
- **THEN** the audit fails with the bounded path/reason exactly as before
- **AND** snapshot preparation remains blocked until the file is sanitized, excluded by explicit product policy, or replaced with synthetic/public-safe content.

#### Scenario: Command runs outside a Git checkout
- **WHEN** `git ls-files` cannot be run against the configured root (for example the root is not a Git repository, or Git itself fails)
- **THEN** the command exits non-zero with an actionable error identifying the missing Git source
- **AND** no candidate set, audit receipt, or snapshot is produced.

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

### Requirement: Fresh public snapshot is a self-contained canonical source repository

A successful public snapshot SHALL contain every repository path required by its own public README, CI workflows, platform validation commands, and accepted specification contract. Sanitization SHALL NOT achieve a clean result by removing source-of-truth or verification material that the packaged repository itself depends on.

#### Scenario: CI references tests and accepted specifications
- **GIVEN** the packaged CI invokes repository tests, OpenSpec validation, upgrade smoke, or other checked-in verification entrypoints
- **WHEN** the public snapshot is prepared
- **THEN** the corresponding required scripts, tests, OpenSpec configuration, and accepted `openspec/specs/` content are present in the snapshot
- **AND** the CI workflow does not reference paths deliberately excluded from the snapshot.

#### Scenario: README links to repository-owned source paths
- **WHEN** a packaged README or public doc links to a repository-owned path that is part of the documented product surface
- **THEN** that path exists in the extracted snapshot
- **OR** the documentation is deliberately updated so the link is not part of the public contract.

### Requirement: Historical evidence may be excluded only by explicit non-product policy

Maintenance/history-only material MAY be excluded from the fresh public source snapshot when it is not required by runtime, CI, accepted specifications, public documentation, or upgrade/release verification. Exclusion SHALL be narrow and documented.

#### Scenario: Archived historical OpenSpec changes contain private operator evidence
- **WHEN** old `openspec/changes/archive/` records contain project-specific historical references
- **AND** those archives are not required for the public repository's current CI, accepted specs, release tooling, or user documentation
- **THEN** the archive subtree may be explicitly excluded from the fresh-history product snapshot
- **AND** current accepted `openspec/specs/` and required OpenSpec configuration remain present.

### Requirement: Extracted snapshot proves source completeness

The platform SHALL run a bounded source-completeness smoke against the extracted public snapshot before cutover readiness is declared.

#### Scenario: Snapshot smoke succeeds
- **WHEN** the deterministic snapshot is extracted into a clean temporary directory
- **THEN** required README/internal links checked by the repository are resolvable
- **AND** every repository-owned path invoked by packaged CI exists
- **AND** the public test/spec/validation entrypoints selected for the product snapshot execute successfully or are proven by the same repository-owned checks used in CI
- **AND** the smoke records the exact source revision and snapshot digest.

#### Scenario: Packaged workflow references an excluded path
- **WHEN** the extracted snapshot contains a CI or public validation command that references a missing excluded repository path
- **THEN** snapshot readiness fails before canonical repository cutover.

### Requirement: Sanitization detects project-specific compatibility material

Public-distribution audit SHALL detect prohibited live compatibility material tied to the current operator's downstream projects even when the material is expressed as project names, project-specific constants, hash names, migration functions, messages, or code branches rather than an `owner/repo` reference.

#### Scenario: Public candidate contains project-specific rollout shim
- **WHEN** a packaged candidate contains a compatibility constant, function, message, branch, fixture, or migration payload whose semantics are specific to a real, named live personal downstream project
- **THEN** the audit blocks the snapshot until the material is removed, generalized with synthetic semantics, or relocated to an external operator-owned compatibility surface.

#### Scenario: Generic synthetic fixture remains
- **WHEN** a test or example uses synthetic project identities solely to verify generic rollout behavior
- **THEN** it may remain in the public product
- **AND** it does not encode private repository names, private migration hashes, or operator-specific production payloads.

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

### Requirement: Shared integration operator provenance stays outside public snapshots

The public distribution candidate set SHALL exclude committed Requirement integration manifests under `dev-platform/requirement-integrations/`, because they carry operator-specific Backlog references needed for protected reconciliation rather than reusable platform source. The exclusion SHALL apply equally to audit, digest and archive construction, and SHALL NOT exempt other product files from operator-reference or secret checks.

#### Scenario: Shared candidate manifest is present

- **GIVEN** a tracked shared Requirement integration manifest and otherwise valid product files
- **WHEN** a public snapshot is audited and built
- **THEN** the manifest is absent from the candidate set and archive
- **AND** other product files remain subject to the existing findings policy

### Requirement: Public source and output guard protects private managed task identifiers

The platform SHALL prevent supported references to private managed task Issues from entering current public source, report text, and publication artifacts. The check SHALL use bounded configured/private-provenance context and SHALL fail closed when a managed source could be private but cannot be classified. It SHALL not claim that a current-tree scan proves old Git history clean.

#### Scenario: Private task reference in tracked source

- **GIVEN** a tracked public candidate file contains a supported private task Issue reference
- **WHEN** public validation runs before publication
- **THEN** it fails with a bounded path and safe reason without reproducing private content

#### Scenario: Opaque managed lineage is present

- **GIVEN** a public managed archive stores only an opaque lineage handle
- **WHEN** current source is audited
- **THEN** that archive is permitted if its private mapping was verified through an authorized read

#### Scenario: Historical commits remain

- **WHEN** current public source and outputs pass the privacy guard
- **THEN** the receipt identifies the checked current surfaces and does not claim that old Git commits were erased

