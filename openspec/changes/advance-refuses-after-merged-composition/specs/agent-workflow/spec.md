## ADDED Requirements

### Requirement: Execute Requirement refuses advance after a merged composition

When a Requirement's composition pull request from its integration branch into `main` is already merged, `execute_requirement.py advance` SHALL stop before it creates, fetches or pushes the integration branch. The refusal SHALL name the merged pull request, state that advancing would recreate the integration branch and break the post-merge jobs, and name the supported next steps: the coordinator's post-merge jobs for that pull request and the read-only publication status. When the pull request inventory of the integration branch cannot be read, advance SHALL stop naming that instead of assuming no composition exists.

#### Scenario: Composition already merged

- **GIVEN** the composition PR #N of `requirement/BR-R` is merged and the branch was deleted
- **WHEN** `advance` runs for the Requirement
- **THEN** it fails naming PR #N and the post-merge job and status commands
- **AND** no `requirement/BR-R` branch is created or pushed

#### Scenario: Composition still open

- **WHEN** the composition PR is open or does not exist yet
- **THEN** advance proceeds as before

#### Scenario: Inventory unavailable

- **WHEN** the pull request list for the integration branch cannot be read
- **THEN** advance fails naming the unavailable inventory and touches no branch
