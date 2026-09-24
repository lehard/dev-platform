# platform-ci Specification Delta

## ADDED Requirements

### Requirement: Ready-child claim tests are portable

Ready-child claim unit tests SHALL verify claim identity and dirty-worktree behavior without depending on shared-workspace group ownership of the test runner's private temporary directory. Production shared-path enforcement SHALL remain active.

#### Scenario: Linux runner executes claim tests

- **GIVEN** a private temporary board fixture on a Linux CI runner
- **WHEN** the ready-child claim tests run
- **THEN** they exercise matching, removal and refusal behavior without requiring a group ownership change
