## ADDED Requirements

### Requirement: OpenSpec archive performs deterministic readiness preflight before expensive validation or evidence mutation

For a platform-owned archive, the lifecycle SHALL validate static semantic-receipt prerequisites and applicable committed task state before executing expensive selected checks or writing authoritative automated-check evidence.

#### Scenario: Verification receipt is statically incomplete

- **GIVEN** `verification.md` lacks a required PASS, method or automated-evidence marker
- **WHEN** archive is requested
- **THEN** the lifecycle fails before running selected checks
- **AND** it does not create or overwrite authoritative `automated-checks.json`

#### Scenario: No applicable committed diff exists

- **GIVEN** the change is only uncommitted/untracked or otherwise has no applicable committed diff against the selected base
- **WHEN** archive is requested
- **THEN** the lifecycle fails with an actionable readiness diagnostic before running selected checks
- **AND** stale not-applicable automated evidence is not written

#### Scenario: Archive is ready

- **GIVEN** static readiness and committed applicable state are valid
- **WHEN** archive is requested
- **THEN** relevant checks run
- **AND** successful evidence is validated
- **AND** the existing strict archive sequence continues normally
