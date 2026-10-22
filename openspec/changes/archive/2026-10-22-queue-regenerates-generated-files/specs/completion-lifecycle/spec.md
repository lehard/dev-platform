## ADDED Requirements

### Requirement: Declared generated files are not task-content identity

Task-content identity for review and for Requirement composition SHALL exclude files that the project declares generated in the committed check configuration at the main commit the candidate is based on (the merge base of the candidate head and the remote integration branch), never in the candidate. A declaration SHALL name the required check that verifies the file, and that check SHALL be part of the repository-owned protected full validation set; a declaration without such a check, a malformed declaration or a missing check configuration at that commit SHALL fail explicitly rather than exclude or include the file silently. Every other task path SHALL remain in identity.

#### Scenario: Only the generated manifest is regenerated on an archived candidate
- **GIVEN** an archived candidate whose gates are bound to its task-content identity
- **WHEN** the publication queue merges main and regenerates only the declared generated manifest
- **THEN** the task-content identity is unchanged and the gates are kept

#### Scenario: An ordinary task path changes together with the manifest
- **GIVEN** an archived candidate
- **WHEN** a task path that is not declared generated changes together with the manifest
- **THEN** the task-content identity changes

#### Scenario: A candidate declares its own file generated
- **GIVEN** a candidate that adds a generated-file declaration absent from the main commit it is based on
- **WHEN** its task-content identity is computed
- **THEN** that file stays in identity

#### Scenario: A declared file has no required check
- **WHEN** a declaration's check is not in the protected full validation set
- **THEN** reading the declaration fails explicitly, naming the file
