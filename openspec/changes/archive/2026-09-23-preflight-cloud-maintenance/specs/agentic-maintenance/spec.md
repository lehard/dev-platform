# agentic-maintenance Specification Delta

## ADDED Requirements

### Requirement: Enabled cloud maintenance has a setup preflight

The platform SHALL provide an operator-invoked preflight for enabled cloud maintenance workflows that reports missing Actions secret configuration before normal use and verifies provider authentication in GitHub Actions without printing secret material. An unavailable cloud maintenance setup SHALL NOT block deterministic CI, release or rollout.

#### Scenario: Required secret is absent

- **GIVEN** a cloud maintenance workflow is enabled
- **WHEN** the operator invokes the setup preflight
- **THEN** it reports the missing `OPENAI_API_KEY` name and the action needed to configure it
- **AND** it does not attempt a routine agentic workflow run

#### Scenario: Secret is present but invalid

- **WHEN** the provider probe authenticates with the configured Actions secret and receives an authentication rejection
- **THEN** the preflight reports an invalid credential category without exposing the secret or provider response body

#### Scenario: Agentic workflow is disabled

- **WHEN** the workflow is intentionally disabled
- **THEN** the preflight identifies the disabled state and does not treat it as a missing-secret failure for deterministic platform work
