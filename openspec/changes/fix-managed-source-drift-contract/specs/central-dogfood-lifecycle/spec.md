## ADDED Requirements

### Requirement: Dogfood source-drift diagnostics are executable through their advertised entrypoint

When central dogfood status reports source-Issue drift and recommends machine-readable JSON recovery, the emitted command SHALL be supported by the entrypoint named in the diagnostic. The machine-readable result SHALL expose bounded recorded/current revision evidence without changing the materialized OpenSpec.

#### Scenario: Status asks for JSON drift evidence

- **GIVEN** a managed task has source-Issue drift evidence
- **WHEN** `dogfood_task.py status` prints a JSON recovery instruction
- **THEN** executing that exact instruction succeeds as a read-only status operation
- **AND** it returns the bounded recorded/current revision evidence.
