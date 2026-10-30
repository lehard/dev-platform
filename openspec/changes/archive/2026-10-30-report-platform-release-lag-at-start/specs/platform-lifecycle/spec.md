## ADDED Requirements

### Requirement: Task start reports a project behind the latest platform release

When a task starts in a managed downstream project, the platform SHALL compare the project's installed platform version with the latest published release of its platform source after pending-rollout reconciliation. When the project is behind, task start SHALL print the project's version, the latest version and the exact Roll Out Platform command that opens the update pull request for this project, and SHALL continue the start (warn and continue). A project on the latest release SHALL start without the report. When the project version, the platform source, the project repository or the latest release cannot be determined, task start SHALL fail with the cause instead of skipping the comparison. The platform source repository itself is not applicable.

#### Scenario: Lagging project is reported and starts
- **GIVEN** a managed project on platform 2.0.0 whose platform source's latest release is v3.0.0
- **WHEN** a task starts
- **THEN** the start prints 2.0.0, v3.0.0 and `gh workflow run rollout.yml --repo <source> -f version=v3.0.0 -f repository=<project>`, and the task is created

#### Scenario: Current project starts silently
- **GIVEN** a managed project on the latest release
- **WHEN** a task starts
- **THEN** no lag report is printed

#### Scenario: Undeterminable latest release stops the start
- **GIVEN** the latest release of the platform source cannot be read
- **WHEN** a task starts
- **THEN** the start fails naming the cause and no task is created
