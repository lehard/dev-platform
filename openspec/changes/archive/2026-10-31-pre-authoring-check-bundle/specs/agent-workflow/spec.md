## ADDED Requirements

### Requirement: An authored bundle can be checked before advance

`orchestrate_pre_authoring.py check-bundle` SHALL run the bundle validation advance uses on every authored bundle of a complete pre-authoring state and SHALL fail naming the OpenSpec error. The check SHALL be optional: advance SHALL validate as before and SHALL NOT read or reuse any check result. status SHALL only name the command.

#### Scenario: A bundle lost a MODIFIED scenario

- **GIVEN** a complete pre-authoring state whose bundle MODIFIES a requirement without one of its scenarios
- **WHEN** `check-bundle` runs
- **THEN** it fails naming the requirement and the missing scenario
- **AND** no child Issue exists

#### Scenario: A correct bundle

- **WHEN** `check-bundle` runs on a valid bundle
- **THEN** it reports the bundle valid
- **AND** advance then materializes the child exactly as before
