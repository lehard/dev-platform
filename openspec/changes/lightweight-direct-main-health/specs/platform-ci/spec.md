## MODIFIED Requirements

### Requirement: Downstream platform CI preserves the repository publish path and required PR compatibility

Generated Dev Platform CI SHALL derive its normal automatic validation from the repository's `publish_mode` while remaining capable of producing the stable platform check on reviewed pull requests that require it. Event-specific execution SHALL avoid repeating the full project check set on direct main publication.

#### Scenario: PR-published repository validates before merge

- **GIVEN** `publish_mode=pr`
- **WHEN** generated Dev Platform CI is rendered
- **THEN** it listens to pull requests targeting the configured main branch
- **AND** it remains manually dispatchable
- **AND** it does not automatically rerun the same platform CI because that pull request was merged to main

#### Scenario: Direct-published repository validates published main lightly

- **GIVEN** `publish_mode=direct`
- **WHEN** generated Dev Platform CI runs on a push to the configured main branch
- **THEN** it executes common platform/OpenSpec health validation
- **AND** it does not execute `scripts/select_checks.py --full --execute`
- **AND** normal direct publication therefore produces one lightweight automatic post-publish health run

#### Scenario: Direct-published repository uses a reviewed maintenance PR

- **GIVEN** `publish_mode=direct`
- **WHEN** a pull request targets the configured main branch
- **THEN** generated Dev Platform CI runs on that pull request so the stable platform status can be produced
- **AND** a platform-owned harness uses selected-check semantics for that pull request

#### Scenario: Full cloud validation is requested explicitly

- **GIVEN** `harness_mode=platform`
- **WHEN** a maintainer manually dispatches generated Dev Platform CI
- **THEN** it executes the configured full platform-managed check set
- **AND** manual dispatch is the cloud path for deliberately repeating full verification

### Requirement: Local-heavy / cloud-final verification is documented

Platform operating guidance SHALL describe local agent verification as the place for required selected/full checks before publish, pull-request cloud CI as the clean-environment merge gate, direct main cloud CI as a lightweight platform/OpenSpec health signal, and manual dispatch as the optional full cloud diagnostic path.

#### Scenario: Agent prepares a direct-published change

- **WHEN** the agent follows the normal direct lifecycle
- **THEN** it does not skip required local verification
- **AND** the published main state receives lightweight platform/OpenSpec validation without repeating the full project check set

#### Scenario: Maintainer wants a cloud full run

- **WHEN** a clean cloud rerun of the configured full platform-managed checks is intentionally needed
- **THEN** the maintainer can use manual workflow dispatch rather than relying on every direct main push to run the full suite
