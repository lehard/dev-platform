## ADDED Requirements

### Requirement: Synthetic friction tests do not mutate live GitHub
Automated tests that intentionally generate synthetic friction or containment violations SHALL preserve fixture-local evidence while preventing live GitHub issue/comment mutations caused by host authentication.

#### Scenario: Authenticated host runs containment regression
- **GIVEN** a regression test intentionally creates a containment violation
- **AND** GitHub CLI is available and authenticated on the host
- **WHEN** the synthetic friction event is recorded
- **THEN** fixture-local friction evidence remains available for assertions
- **AND** no live GitHub process record is created or updated by that test

#### Scenario: Real runtime friction
- **GIVEN** a real runtime friction event outside the hermetic test fixture
- **WHEN** normal routing prerequisites are satisfied
- **THEN** existing production friction routing remains in effect
