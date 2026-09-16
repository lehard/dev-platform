## ADDED Requirements

### Requirement: Agent instructions expose the thin-CI ownership boundary

Dev Platform SHALL make the CI ownership boundary discoverable from applicable root/rendered agent instructions without duplicating detailed provider policy across tool-specific instruction surfaces.

#### Scenario: Agent is about to add CI/CD implementation logic
- **WHEN** an agent task reaches test, build, verification, release or deploy workflow implementation
- **THEN** the applicable agent-facing contract tells the agent to prefer a repository-owned executable entrypoint for portable behavior
- **AND** points to the canonical CI/release guidance for the detailed ownership boundary
- **AND** the agent does not treat GitHub Actions YAML as the default implementation surface solely because the repository is hosted on GitHub

#### Scenario: Task only needs GitHub-native orchestration
- **WHEN** the task changes only triggers, permissions, concurrency, check/status integration or other provider-native control-plane behavior
- **THEN** the instruction does not force creation of an unnecessary repository abstraction or wrapper
