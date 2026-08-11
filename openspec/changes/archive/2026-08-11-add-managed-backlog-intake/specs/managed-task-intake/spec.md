## ADDED Requirements

### Requirement: Managed tasks use a versioned central intake package

A managed task SHALL be represented by a human-readable issue in the configured Development Backlog plus exactly one supported managed OpenSpec package. The package SHALL identify its format version, source issue, target repository, OpenSpec change name, preparation commit for the target repository, and the complete set of planning artifacts required for implementation.

#### Scenario: ChatGPT prepares a managed task

- **WHEN** a non-trivial change is explicitly fixed into the Development Backlog
- **THEN** the issue contains the human task description and OpenSpec change name
- **AND** a `managed-openspec:v1` package contains the source issue, target repository, preparation commit and OpenSpec artifacts
- **AND** no implementation is started merely because the package exists

#### Scenario: Multiple supported packages are present

- **WHEN** intake finds zero packages, more than one current package, an unsupported version, or an incomplete manifest
- **THEN** import fails closed with an actionable error
- **AND** no OpenSpec files are partially materialized

### Requirement: Managed-task import is deterministic and target-safe

The platform SHALL provide a dependency-light import entrypoint that reads a managed task using existing authenticated GitHub access, verifies that the package target matches the current repository, constrains every supplied artifact to the new OpenSpec change root, and never executes package text as shell or code.

#### Scenario: Correct task is imported from the target repository

- **GIVEN** the current checkout resolves to the package target repository
- **AND** the package is structurally valid
- **WHEN** the managed-task import entrypoint is invoked
- **THEN** it creates the change scaffold using the installed OpenSpec CLI and repository schema
- **AND** writes only the declared OpenSpec artifacts under that change
- **AND** records provenance sufficient to identify the source issue and imported package revision
- **AND** does not start apply or edit application/platform implementation files

#### Scenario: Task targets a different repository

- **WHEN** the package target repository does not equal the normalized current `origin` repository identity
- **THEN** import aborts before creating or changing the OpenSpec change

#### Scenario: Package declares an unsafe artifact path

- **WHEN** an artifact path is absolute, traverses outside the change root, targets `.git`, or otherwise escapes the allowed planning area
- **THEN** import rejects the package before writing any artifact

### Requirement: Import uses the repository's current OpenSpec contract

Managed-task import SHALL use the installed OpenSpec CLI to create/inspect the change under the repository's current configured schema instead of assuming a fixed directory layout from the transport package alone. The transport package SHALL supply planning content, not replace OpenSpec schema discovery.

#### Scenario: Repository schema has evolved since package preparation

- **WHEN** the current OpenSpec CLI/schema requires a different scaffold or artifact contract than the package assumed
- **THEN** import/preflight reports the incompatibility
- **AND** does not silently invent or discard product semantics merely to force the package through validation

#### Scenario: Structural validation succeeds

- **WHEN** all package artifacts are materialized into a compatible scaffold
- **THEN** the importer runs the repository-supported structural OpenSpec preflight
- **AND** reports that semantic preflight is still required before implementation

### Requirement: Package freshness is explicit and semantic preflight is mandatory when needed

A managed package SHALL record the target repository commit used during preparation. Import SHALL compare that evidence with current synchronized target state. A changed target commit SHALL not automatically invalidate unrelated planning, but it SHALL be surfaced so an agent cannot blindly apply an old contract.

#### Scenario: Target main is unchanged

- **WHEN** the synchronized target commit equals `prepared_against`
- **THEN** import reports the package as freshness-aligned
- **AND** the normal semantic OpenSpec review still applies before implementation

#### Scenario: Target main advanced after preparation

- **WHEN** synchronized target main differs from `prepared_against`
- **THEN** import reports the package as stale relative to repository state
- **AND** the agent reviews relevant current specs and active changes before implementation
- **AND** a material product-contract conflict requires user resolution rather than silent rewriting

### Requirement: Re-import is idempotent and never silently overwrites divergent work

The importer SHALL compute and persist provenance for the imported package so retrying the same task is safe. It SHALL distinguish an unchanged imported package from a package that changed after local materialization or from an unrelated same-name OpenSpec change.

#### Scenario: Same unchanged package is imported again

- **GIVEN** the existing local change was imported from the same source issue and package revision
- **WHEN** import is repeated
- **THEN** it verifies/reuses the existing change without duplicating artifacts or destroying edits

#### Scenario: Backlog package changed after materialization

- **GIVEN** the local change already records an earlier package revision
- **WHEN** the source issue now contains a different package revision
- **THEN** the importer stops and requires explicit reconciliation
- **AND** does not overwrite the repository-local OpenSpec automatically

#### Scenario: Same change name belongs to another source

- **WHEN** a local active change with the requested name exists but its provenance does not match the source issue
- **THEN** import fails closed and reports the naming conflict

### Requirement: Intake authentication adds no new secret boundary

Managed-task intake SHALL reuse existing validated GitHub CLI/API credentials and the installed OpenSpec CLI. It SHALL NOT require a new daemon, cloud service, API key, or committed credential.

#### Scenario: GitHub issue cannot be read

- **WHEN** existing GitHub authentication is unavailable or insufficient for the private backlog repository
- **THEN** import fails with an authentication/setup message
- **AND** does not partially create the OpenSpec change

### Requirement: Intake does not own dispatch or Project workflow state

The v1 importer SHALL prepare planning state only. It SHALL NOT poll GitHub Project `Ready`, launch Codex/Claude, change Project status, merge code, or replace the existing dev-platform execution/publication lifecycle.

#### Scenario: Managed task is imported successfully

- **WHEN** import and structural preflight complete
- **THEN** the task is ready for the existing agent/OpenSpec execution flow
- **AND** no background execution or Project-status mutation is triggered by the importer

