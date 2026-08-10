## ADDED Requirements

### Requirement: Managed rollout emits one machine-readable terminal diagnostic

For every failed managed-project rollout attempt, the workflow SHALL emit one canonical machine-readable diagnostic envelope derived from structured rollout state. The envelope SHALL be available without requiring arbitrary full-log scraping and SHALL NOT alter rollout safety or outcome.

The envelope SHALL include at least: schema version, terminal status, target project, target immutable release, failure stage, failure category, stable reason, exit code, selected command when known, same-input retry advisory, and structured evidence already known to rollout such as conflict paths. It SHALL exclude credentials, unrestricted environment dumps, tokens, and raw logs.

#### Scenario: Safety guard blocks rollout
- **WHEN** a managed safety invariant fails deterministically
- **THEN** the diagnostic category is `safety_guard` or another more specific stable safety category
- **AND** the stage identifies where the guard failed
- **AND** the reason contains the canonical managed-rollout blocker
- **AND** `retry_same_inputs` is `pointless` unless the platform can prove the failure may be transient
- **AND** the workflow remains failed

#### Scenario: Selected downstream check fails
- **GIVEN** rollout has emitted `DEV_PLATFORM_CHECK_COMMAND: <command>`
- **WHEN** that selected command exits non-zero
- **THEN** the diagnostic stage is `downstream_check`
- **AND** the command field contains exactly the reserved selected command
- **AND** arbitrary compiler, diff, or application output SHALL NOT replace the command
- **AND** the exit code is preserved

#### Scenario: Runtime/environment mismatch is known
- **WHEN** rollout can identify that a platform-owned runtime baseline differs from the required managed validation baseline
- **THEN** the diagnostic category is `runtime_environment`
- **AND** the reason identifies the required/observed baseline without exposing secrets
- **AND** a same-input retry SHALL NOT be labeled `safe` when no environment input can change between attempts

#### Scenario: Failure is not classifiable
- **WHEN** rollout fails without a known blocker, structured conflict, or selected-check marker
- **THEN** the diagnostic category is `unknown`
- **AND** the stage is the narrowest known stage or `unknown`
- **AND** `retry_same_inputs` is `unknown`
- **AND** the workflow does not infer a cause from arbitrary log text

#### Scenario: Diagnostic is published for agents and humans
- **WHEN** a rollout attempt reaches a terminal failed state
- **THEN** the canonical diagnostic JSON is written to a predictable path such as `rollout-diagnostic.json`
- **AND** a compact rendering is appended to the GitHub Actions step summary
- **AND** the workflow attempts to upload a predictably named diagnostic artifact
- **AND** the annotation, summary, and artifact represent the same canonical terminal failure

#### Scenario: Diagnostic artifact upload fails
- **GIVEN** the original rollout is already failed
- **WHEN** diagnostic artifact upload or summary presentation fails
- **THEN** that presentation failure SHALL NOT replace the original blocker
- **AND** SHALL NOT convert the rollout to success
- **AND** the workflow SHALL preserve the original non-zero result

#### Scenario: Consumer reads a future diagnostic schema
- **GIVEN** a consumer understands schema version 1
- **WHEN** later platform versions add optional diagnostic fields
- **THEN** the existing stable fields remain interpretable
- **AND** consumers can reject or explicitly handle an unsupported schema version rather than relying on exact JSON byte shape
