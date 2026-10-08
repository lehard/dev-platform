## ADDED Requirements

### Requirement: Coordinator configuration preflight

The publication coordinator SHALL validate its required configuration through one repository-owned preflight entrypoint before it observes any candidate. The preflight SHALL be run in an explicit mode (CI or local) and phase (inputs, runtime or all), SHALL prove the coordinator App identity, trust configuration, token scope, write permission and runtime inputs, and SHALL stop at the first failed check with a non-zero exit and a diagnostic naming the missing or contradictory input. Its output SHALL NOT contain credential values, and a missing or invalid required input SHALL NOT be replaced by a default or alternate strategy. The `publication-queue` workflow SHALL run the inputs phase before minting the App token without passing secret values to the preflight, and the runtime phase before candidate work; the worker command SHALL run the full preflight itself.

#### Scenario: Valid configuration

- **WHEN** every required App, trust, permission and runtime input is proven
- **THEN** the preflight exits zero and the worker proceeds to observe candidates

#### Scenario: Missing input stops before candidate work

- **WHEN** a required variable or secret presence flag, run identifier, tool or App slug is missing
- **THEN** the preflight exits non-zero naming that input
- **AND** no pull request, comment or label is read or written

#### Scenario: Contradictory App identity

- **WHEN** the App slug exported by the workflow differs from the configured `[publication] coordinator_app`, or the trust configuration cannot be read as valid
- **THEN** startup fails naming the contradiction or the unreadable source
- **AND** no trusted set is silently narrowed or widened

#### Scenario: Insufficient token or permission

- **WHEN** the token is not an installation token for the current repository or the coordinator App lacks write permission
- **THEN** the preflight fails naming the check category

#### Scenario: Secret-safe diagnostics

- **WHEN** any preflight check fails
- **THEN** stdout, stderr and the JSON result identify only input names and fixed categories
- **AND** no token, private key or API response body appears

### Requirement: Coordinator friction evidence is durable on the candidate pull request

Meaningful lifecycle and friction events recorded by the coordinator SHALL be persisted as a trusted, versioned evidence comment on the candidate pull request through the existing authenticated lifecycle comment channel, before the transition that produced them is published. Each record SHALL bind the Requirement (or prove none), pull request number, exact head, lifecycle stage and the worker run identity, SHALL be idempotent per dedupe key, and SHALL be authenticated by the same trust rules as other lifecycle markers. A persistence failure SHALL fail the transition and the run visibly; the coordinator SHALL NOT proceed with machine-local-only evidence.

#### Scenario: Ephemeral runner ends

- **WHEN** a coordinator run on an ephemeral runner records friction for a candidate and the runner is discarded
- **THEN** a trusted evidence record bound to the Requirement, head, stage and worker remains on the pull request

#### Scenario: Retried transition

- **WHEN** an interrupted or scheduled run repeats the same transition for the same head and attempts
- **THEN** no second evidence record is posted

#### Scenario: Forged or malformed record

- **WHEN** an evidence comment is authored by an untrusted account
- **THEN** it is ignored
- **WHEN** a trusted evidence record is malformed or contradicts its pull request or head
- **THEN** reading it raises a named error and is not skipped

#### Scenario: Persistence fails

- **WHEN** the evidence comment cannot be posted or the Requirement lineage cannot be resolved
- **THEN** the handoff record for the transition is not published
- **AND** the worker exits non-zero stating the persistence failure
