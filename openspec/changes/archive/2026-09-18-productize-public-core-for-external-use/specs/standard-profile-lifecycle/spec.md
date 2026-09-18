## ADDED Requirements

### Requirement: Standard publication core is provider-neutral

The standard profile SHALL express task publication in provider-neutral lifecycle terms: synchronize remote integration state, create/use a task branch, publish the branch, open or reuse the provider's change-review object, observe required checks, and reach a configured human or automatic merge terminal state. Provider-specific APIs and CLI commands SHALL remain behind adapters.

#### Scenario: Standard GitLab task reaches human acceptance
- **GIVEN** a standard project configured with the GitLab adapter
- **WHEN** a verified task branch is published
- **THEN** the adapter can open or reuse the exact GitLab merge request for that branch/head
- **AND** observe the GitLab CI result needed by the configured acceptance policy
- **AND** stop at human merge/acceptance for the client-pilot configuration
- **AND** the core lifecycle does not require GitHub CLI or GitHub Actions.

#### Scenario: Standard GitHub task uses the same core lifecycle
- **GIVEN** a standard project configured with the GitHub adapter
- **WHEN** a verified task branch is published
- **THEN** the existing GitHub PR/check semantics are invoked through the provider boundary
- **AND** existing publication safety remains authoritative.

### Requirement: CI provider workflows remain thin orchestration

Provider-specific CI configuration SHALL invoke repository-owned build, test and verification entrypoints rather than duplicating portable engineering logic in GitHub Actions or GitLab CI.

#### Scenario: Same repository checks run locally and in GitLab CI
- **WHEN** the client-like sandbox runs required checks locally and then through GitLab CI
- **THEN** both paths invoke the same repository-owned commands
- **AND** the GitLab workflow contains provider orchestration rather than a second implementation of test/verification policy.
