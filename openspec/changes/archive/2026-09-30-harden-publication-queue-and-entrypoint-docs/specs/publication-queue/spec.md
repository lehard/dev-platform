# publication-queue Specification Delta

## ADDED Requirements

### Requirement: Queue coordinator runs trusted code with a least-privilege token

The publication queue workflow SHALL execute only code from the protected default branch for every trigger, including the `publication:queued` label event, and SHALL NOT check out or execute pull-request-controlled content while holding the Dev Platform GitHub App token. The App token SHALL be scoped to the current repository and to only the permissions the coordinator uses (contents write and pull requests write). Protected publication, required checks, the expected-head merge guard and the absence of bypass or force semantics SHALL be unchanged.

#### Scenario: Pull request is labeled for the queue

- **WHEN** a pull request receives the `publication:queued` label
- **THEN** the coordinator runs the workflow and worker from the default branch
- **AND** no pull-request-controlled file is executed with the App token

#### Scenario: Token is created for the coordinator

- **WHEN** the workflow creates the GitHub App token
- **THEN** the token is limited to the current repository and to contents write and pull requests write
- **AND** no workflows, administration or other permission is requested
