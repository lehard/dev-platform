# platform-rollout Specification Delta

## ADDED Requirements

### Requirement: A pre-cutover baseline tag can be bridged from a configured legacy repository

Managed upgrades SHALL support an optional, generically-configured legacy repository that supplies a project's recorded Copier baseline tag when a fresh-history canonical repository no longer contains it, without hardcoding that repository's identity in public workflow or Python source.

#### Scenario: Project's recorded baseline predates the canonical history

- **GIVEN** a managed project's `.copier-answers.yml` records a baseline tag the canonical repository does not contain
- **AND** a legacy repository preserving that history is configured
- **WHEN** rollout runs `copier update`
- **THEN** the baseline tag is fetched from the configured legacy repository into Copier's own template-source cache before the update runs
- **AND** no tag or history is pushed to, or rewritten in, the canonical repository

#### Scenario: Project is already on a post-cutover baseline

- **WHEN** a managed project's recorded baseline tag already resolves in Copier's cache
- **THEN** no fetch from the legacy repository occurs

#### Scenario: Legacy repository is not configured

- **WHEN** the legacy repository variable is unset
- **THEN** rollout behaves exactly as it did before this capability existed

#### Scenario: Guarded-recopy's own baseline comparison needs the same pre-cutover tag

- **GIVEN** guarded-recopy compares the currently-checked-out platform baseline against a pre-cutover tag not present in the platform checkout's own git history
- **AND** a legacy repository is configured
- **WHEN** that baseline tag cannot be fetched from the canonical `origin`
- **THEN** it is fetched from the configured legacy repository directly into the platform checkout before the comparison runs

#### Scenario: A malformed legacy repository is rejected

- **WHEN** the configured legacy repository value is not a plain `owner/name` reference
- **THEN** rollout fails closed with a clear error before constructing any fetch URL from it
