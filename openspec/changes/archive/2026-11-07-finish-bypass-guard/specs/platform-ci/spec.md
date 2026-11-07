## ADDED Requirements

### Requirement: The central required check refuses a head that bypassed finish

An early step of the central `validate` job SHALL, on `pull_request`, check the commit named by `github.event.pull_request.head.sha`, not the checked-out merge commit, through a repository-owned entrypoint that reads Git only. The head SHALL pass only with exactly one `Dev-Platform-Finish` trailer equal to the tree of that commit. There SHALL be no exception list, label or silent skip.

#### Scenario: Head delivered by finish

- **WHEN** the PR head carries a valid trace
- **THEN** the step passes

#### Scenario: PR opened around finish

- **WHEN** the PR head carries no trace
- **THEN** `validate` fails naming the reason and `python3 scripts/dogfood_task.py finish`

#### Scenario: Head changed after finish

- **GIVEN** a trace whose value differs from the tree of its commit
- **WHEN** the step checks that head
- **THEN** `validate` fails naming both trees and the same next command

#### Scenario: Rendered project

- **WHEN** a project is rendered from the template
- **THEN** its workflows contain no such step

#### Scenario: Guard refuses every PR by mistake

- **GIVEN** a defect makes the step refuse valid heads
- **WHEN** a PR repairs the guard or removes the step from its own `ci.yml`
- **THEN** the run of that PR uses the workflow and scripts of its own tree
- **AND** no GitHub protection setting changes
