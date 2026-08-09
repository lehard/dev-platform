# Platform CI Delta

## MODIFIED Requirements

### Requirement: Downstream platform CI uses one cloud validation path per publish path

Generated Dev Platform CI SHALL derive its automatic trigger from the repository's existing `publish_mode` so an ordinary reviewed/published change is not validated automatically both before and after publication.

#### Scenario: PR-published repository validates before merge

- **GIVEN** `publish_mode=pr`
- **WHEN** generated Dev Platform CI is rendered
- **THEN** it listens to pull requests targeting the configured main branch
- **AND** it remains manually dispatchable
- **AND** it does not automatically rerun the same platform CI because that pull request was merged to main

#### Scenario: Direct-published repository validates the published main state

- **GIVEN** `publish_mode=direct`
- **WHEN** generated Dev Platform CI is rendered
- **THEN** it listens to pushes to the configured main branch
- **AND** it remains manually dispatchable
- **AND** it does not also automatically run on feature pull requests by default

### Requirement: Superseded validation runs are cancelled

Ordinary CI validation workflows SHALL use concurrency grouping that keeps the newest run for the same PR/ref and cancels an older in-progress validation run when a newer commit supersedes it.

#### Scenario: New commit arrives while PR CI is still running

- **GIVEN** a validation run for a pull request is in progress
- **WHEN** a newer commit to the same pull request starts a new validation run
- **THEN** the older run is cancelled
- **AND** the newest run remains authoritative

#### Scenario: Release side-effect workflow runs

- **WHEN** a release publication or managed rollout workflow starts
- **THEN** it is not made cancel-in-progress merely by this cost-optimization policy

### Requirement: Central platform CI does not duplicate profile-independent work

The central `dev-platform` CI SHALL retain coverage for every supported workflow profile while avoiding repeated execution of shared setup and profile-independent validation solely because multiple profiles are exercised.

#### Scenario: Platform PR runs factory coverage

- **WHEN** central Platform CI validates a pull request
- **THEN** shared script compilation, managed-project validation, unit tests, OpenSpec validation and common dependency setup execute once per workflow run
- **AND** light, standard and multi-agent render/update behavior is still exercised

### Requirement: Cost optimization does not weaken repository verification ownership

Generated platform CI SHALL continue to respect `harness_mode` and SHALL NOT replace project-owned application CI or local required checks merely to reduce GitHub Actions usage.

#### Scenario: Project-owned harness is optimized

- **GIVEN** `harness_mode=project`
- **WHEN** the generated Dev Platform workflow is updated
- **THEN** only platform/OpenSpec hygiene behavior owned by Dev Platform is changed
- **AND** the repository's product/application workflow remains project-owned
- **AND** any cost optimization of that product workflow requires a separate reviewed project change

### Requirement: Local-heavy / cloud-final verification is documented

Platform operating guidance SHALL describe local agent verification as the place for required selected/full checks before publish and cloud CI as the clean-environment final gate or post-direct-publish health signal, according to publish mode.

#### Scenario: Agent prepares a change for publication

- **WHEN** the agent follows the repository lifecycle
- **THEN** it does not skip required local verification because cloud CI is narrower
- **AND** cloud CI is not used as a reason to run the same expensive full suite twice without a reviewed repository-specific need
