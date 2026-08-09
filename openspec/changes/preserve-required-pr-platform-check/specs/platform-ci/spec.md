## MODIFIED Requirements

### Requirement: Downstream platform CI preserves the repository publish path and required PR compatibility

Generated Dev Platform CI SHALL derive its normal automatic validation from the repository's `publish_mode` while remaining capable of producing the stable platform check on reviewed pull requests that require it.

#### Scenario: PR-published repository validates before merge

- **GIVEN** `publish_mode=pr`
- **WHEN** generated Dev Platform CI is rendered
- **THEN** it listens to pull requests targeting the configured main branch
- **AND** it remains manually dispatchable
- **AND** it does not automatically rerun the same platform CI because that pull request was merged to main

#### Scenario: Direct-published repository validates published main

- **GIVEN** `publish_mode=direct`
- **WHEN** generated Dev Platform CI is rendered
- **THEN** it listens to pushes to the configured main branch
- **AND** it remains manually dispatchable
- **AND** normal direct publication therefore produces one automatic post-publish validation run

#### Scenario: Direct-published repository uses a reviewed maintenance PR

- **GIVEN** `publish_mode=direct`
- **AND** repository protection or rollout policy requires the stable `platform-ci` status on pull requests
- **WHEN** a pull request targets the configured main branch
- **THEN** generated Dev Platform CI runs on that pull request so the required platform status can be produced
- **AND** the pull-request run uses the existing PR/selected-check semantics rather than pretending it is a direct main publication

### Requirement: Local-heavy / cloud-final verification is documented

Platform operating guidance SHALL describe local agent verification as the place for required selected/full checks before publish, cloud CI as the clean-environment final gate for PR publication or post-direct-publish health signal, and the direct-mode pull-request trigger as a compatibility gate for explicitly reviewed PRs.

#### Scenario: Agent prepares a direct-published change

- **WHEN** the agent follows the normal direct lifecycle without opening a PR
- **THEN** it does not skip required local verification
- **AND** the published main state receives its automatic cloud validation

#### Scenario: Direct repository uses a maintenance PR

- **WHEN** a reviewed maintenance or rollout PR is used in a direct-publish repository
- **THEN** the generated platform workflow can satisfy the stable required PR check
- **AND** documentation does not describe that compatibility run as a reason to duplicate expensive project-owned full suites
