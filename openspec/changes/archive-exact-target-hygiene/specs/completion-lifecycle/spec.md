## ADDED Requirements

### Requirement: Archive hygiene exempts only its exact target

While `openspec_lifecycle.py archive <change>` runs the selected or protected validation checks, the OpenSpec lifecycle hygiene check SHALL exempt only that exact completed active archive target. The exemption SHALL exist only for the validation subprocess of that archive invocation, SHALL fail closed when the target is missing, malformed, absent or not a completed active change, and SHALL NOT alter ordinary hygiene outside that context. The hygiene check SHALL remain in the mandatory check groups.

#### Scenario: Verified change passes its own archive checks
- **GIVEN** a completed, verified active change and the standard check mapping that includes the hygiene check
- **WHEN** the agent invokes the platform archive entrypoint
- **THEN** the hygiene check inside the archive validation passes for that change
- **AND** the change is archived and the ordinary hygiene check then passes

#### Scenario: Ordinary hygiene still blocks a completed active change
- **GIVEN** a completed change that is still active
- **WHEN** the ordinary hygiene check runs outside an archive validation
- **THEN** it fails naming the change

#### Scenario: A second completed active change blocks archive
- **GIVEN** two completed active changes
- **WHEN** one of them is archived
- **THEN** hygiene inside archive validation fails naming the other change and nothing is archived

#### Scenario: Invalid archive target fails closed
- **GIVEN** an archive target that is nonexistent, malformed, ambiguous or not completed
- **WHEN** hygiene runs in the archive context
- **THEN** it fails with an explicit error before any canonical state is changed
- **AND** the archive entry point applies this target validation in every mode, including `--finalize`, before any canonical state changes, while `--finalize` still runs no checks and needs no exemption

#### Scenario: Failed archive leaves no bypass
- **GIVEN** archive validation fails after the exemption was applied
- **WHEN** the ordinary hygiene check runs afterwards
- **THEN** it blocks the still-active completed change
