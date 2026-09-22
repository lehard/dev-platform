# engineering-capabilities Specification Delta

## ADDED Requirements

### Requirement: Generated CI materializes derived capability surfaces before platform validation

Every generated project's CI SHALL materialize its selected capabilities' derived provider surfaces before running platform validation, since those surfaces are deliberately gitignored and therefore absent on any fresh checkout.

#### Scenario: A fresh checkout has capabilities enabled

- **GIVEN** a project's `dev-platform/capabilities.toml` has one or more capabilities enabled
- **AND** the checkout is fresh, so the gitignored derived provider surfaces for those capabilities do not yet exist
- **WHEN** generated CI runs
- **THEN** it runs `capability_manager.py sync` before `platform_doctor.py`
- **AND** platform validation's capability audit passes

#### Scenario: Materialized surfaces are never committed

- **WHEN** generated CI materializes selected capability surfaces
- **THEN** those files remain matched by the project's own gitignore patterns
- **AND** no generated CI step stages or commits them
