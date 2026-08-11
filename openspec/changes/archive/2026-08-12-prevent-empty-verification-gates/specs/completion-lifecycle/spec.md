## ADDED Requirements

### Requirement: Verification evidence is truthful about executed automated coverage

A semantic verification receipt SHALL distinguish automated commands that actually executed from scopes with no applicable automated checks or invalid empty platform-owned coverage. The existence of a PASS receipt SHALL NOT convert an empty required platform-owned check set into successful automated verification.

#### Scenario: Required platform-owned coverage is empty

- **GIVEN** an active non-trivial change requires platform-owned project checks for an affected scope
- **AND** the applicable check mapping resolves to zero executable commands
- **WHEN** semantic verification/archive is attempted
- **THEN** completion is blocked on check-contract configuration
- **AND** an `OpenSpec-Verify: PASS` receipt alone SHALL NOT override that blocker

#### Scenario: Automated checks executed successfully

- **WHEN** applicable required platform-owned commands execute successfully
- **THEN** verification evidence may cite those exact executed checks
- **AND** archive proceeds only if all other existing semantic/strict-validation requirements are satisfied

#### Scenario: Project-owned harness supplies product verification

- **GIVEN** `harness_mode=project`
- **WHEN** semantic verification uses repository-owned CI/evidence for product behavior
- **THEN** Dev Platform SHALL preserve that ownership boundary
- **AND** SHALL not claim platform-managed product commands ran when they did not
