## ADDED Requirements

### Requirement: Affected-group precheck precedes full validation

When a project opts in, for changed Python paths that trigger full validation the lifecycle SHALL first execute, within their canonical groups, the test modules that directly reference those paths according to a tested static mapping, and SHALL stop before the full set when the precheck fails. Precheck results SHALL be recorded separately from the executed validation commands as feedback evidence and SHALL NOT replace or shorten the full or protected validation set. Paths without a mapping SHALL proceed directly to full validation.

#### Scenario: Precheck fails
- **GIVEN** a change to a template script referenced by test modules in two canonical groups
- **WHEN** archive or finish runs full validation and one mapped test module fails
- **THEN** validation stops before the full set with a failure descriptor marking the precheck phase

#### Scenario: Precheck passes
- **WHEN** the mapped test modules pass
- **THEN** the full validation set still runs completely
- **AND** evidence distinguishes precheck feedback from full validation results

#### Scenario: Unmapped control-plane path
- **WHEN** a changed path has no mapping, such as the selector configuration or a CI workflow
- **THEN** no precheck is claimed and full validation runs directly
