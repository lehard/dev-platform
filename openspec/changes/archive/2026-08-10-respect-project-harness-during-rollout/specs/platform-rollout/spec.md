## ADDED Requirements

### Requirement: Managed rollout validation respects harness ownership

Central managed rollout SHALL execute only validation behavior owned by Dev Platform and SHALL NOT assume a project-owned selector CLI contract.

#### Scenario: Platform owns downstream harness

- **GIVEN** a managed repository records `harness_mode=platform`
- **WHEN** rollout validates a conflict-free exact-version update
- **THEN** it runs platform doctor
- **AND** it invokes the rendered platform-managed `scripts/select_checks.py` with the platform rollout execution contract

#### Scenario: Project owns downstream harness

- **GIVEN** a managed repository records `harness_mode=project`
- **WHEN** rollout validates a conflict-free exact-version update
- **THEN** it runs platform-owned diff and doctor validation
- **AND** it does not invoke the repository-owned `scripts/select_checks.py`
- **AND** product/application verification is left to the downstream pull request CI before merge

#### Scenario: Project-owned selector has a different CLI

- **GIVEN** `harness_mode=project`
- **AND** the repository-owned selector does not accept Dev Platform-specific execution flags
- **WHEN** managed rollout prepares an update
- **THEN** rollout does not fail merely because that project-owned CLI differs from the platform selector contract
