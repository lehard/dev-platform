## ADDED Requirements

### Requirement: Verification receipt requirements are canonical and preflight-actionable

The canonical central OpenSpec workflow and the rendered downstream workflow SHALL describe the same platform-enforced verification receipt evidence requirements. Archive preflight SHALL detect a missing required automated-checks evidence marker before archive mutation and SHALL identify the canonical contract needed to repair it.

#### Scenario: Verification receipt omits automated-checks evidence

- **GIVEN** a change has a verification receipt without the platform-required automated-checks evidence marker
- **WHEN** archive preflight runs
- **THEN** archive mutation does not begin
- **AND** the diagnostic identifies the missing requirement and its canonical workflow location.
