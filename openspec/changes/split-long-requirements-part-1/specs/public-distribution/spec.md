## MODIFIED Requirements

### Requirement: Public audit covers the exact public snapshot candidate set

The public-distribution lifecycle SHALL derive one deterministic candidate file set from the Git-tracked files of the current checkout (for example via `git ls-files`) and SHALL use that same set for sanitization and snapshot packaging, after applying the existing exclusion policy (`EXCLUDED_PARTS`/`EXCLUDED_PATHS`) and any supplied external cutover-policy exclusions.

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

## ADDED Requirements

### Requirement: A successful public audit admits no file outside the sanitization decision

A successful public-distribution audit SHALL NOT permit a file into the fresh-history snapshot that was outside the sanitization decision.

#### Scenario: File outside the sanitization decision

- **GIVEN** a file that was outside the sanitization decision
- **WHEN** the public-distribution audit succeeds
- **THEN** that file is not permitted into the fresh-history snapshot

### Requirement: Untracked local files stay out of the public candidate set

Untracked local files (for example scratch notes, generated output, or other working-tree state never committed to Git) SHALL NOT enter the candidate set, SHALL NOT influence the candidate digest, and SHALL NOT produce audit findings, because they are not part of the repository source the fresh public history is built from.

#### Scenario: Untracked local file is ignored

- **GIVEN** an untracked local file, such as scratch notes, generated output, or other working-tree state never committed to Git
- **WHEN** the public-distribution candidate set is derived
- **THEN** the file does not enter the candidate set
- **AND** it does not influence the candidate digest
- **AND** it produces no audit finding

### Requirement: The public-distribution command fails closed without Git-tracked files

The public-distribution command SHALL fail closed with an actionable error when it cannot enumerate Git-tracked files (for example when run outside a Git checkout or when `git` itself fails), rather than silently falling back to a full filesystem walk.

#### Scenario: Git-tracked files cannot be enumerated

- **WHEN** the public-distribution command cannot enumerate Git-tracked files, for example outside a Git checkout or when `git` itself fails
- **THEN** it fails closed with an actionable error
- **AND** it does not silently fall back to a full filesystem walk
