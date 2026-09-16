## ADDED Requirements

### Requirement: CI providers orchestrate repository-owned portable execution

Dev Platform SHALL keep portable test, build, verification, release and deploy implementation logic in repository-owned executable entrypoints when that behavior can reasonably execute outside a CI provider. CI-provider workflows SHALL primarily orchestrate those entrypoints and SHALL NOT become the sole implementation surface for portable behavior merely because the repository currently uses that provider.

#### Scenario: Agent adds a portable verification capability
- **WHEN** an agent needs to add verification logic that can run from a checked-out repository
- **THEN** the capability is implemented behind a repository-owned command or script
- **AND** the GitHub Actions workflow invokes that entrypoint rather than owning the only implementation
- **AND** the same entrypoint can be used locally without requiring a GitHub Actions runtime

#### Scenario: Workflow needs GitHub-native orchestration
- **WHEN** a workflow defines GitHub event triggers, permissions, concurrency, checkout/bootstrap, secrets or environment wiring, artifacts, checks or status integration
- **THEN** that provider-specific orchestration MAY remain directly in GitHub Actions
- **AND** the platform SHALL NOT extract it into a generic provider abstraction solely for theoretical portability

#### Scenario: Existing central workflow contains inline shell
- **GIVEN** a central workflow has working inline shell or YAML logic
- **WHEN** the thin-CI invariant is applied
- **THEN** line count or provider specificity alone SHALL NOT require refactoring
- **AND** extraction is required only when the block represents a portable/reusable capability whose repository-owned entrypoint materially improves reproducibility, reuse or ownership clarity

#### Scenario: Execution placement changes
- **WHEN** a repository later chooses a self-hosted runner or another supported execution environment
- **THEN** repository-owned portable entrypoints remain the execution contract
- **AND** the platform does not require a provider abstraction to preserve that portability
