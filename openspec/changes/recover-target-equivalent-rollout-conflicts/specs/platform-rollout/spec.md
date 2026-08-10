## ADDED Requirements

### Requirement: Target-equivalent platform conflicts are recoverable without hand patches

Managed rollout MAY recover a Copier rejection in `harness_mode=platform` only when every rejected platform-owned target was proven byte-identical to the exact requested immutable release before the failed smart update. Real downstream divergence SHALL continue to fail closed.

#### Scenario: Previously repaired platform file matches the target release
- **GIVEN** a managed platform-owned repository has a lifecycle file already identical to the requested release
- **WHEN** Copier's historical-diff replay nevertheless leaves a rejection for that file
- **THEN** rollout MAY reset only its ephemeral rollout branch and use guarded exact-release recopy
- **AND** normal bootstrap, configuration validation, doctor, selected checks, and reviewed PR delivery still run

#### Scenario: One rejected platform file differs from the target release
- **WHEN** any rejected target was not proven byte-identical to the requested release before update
- **THEN** managed rollout fails closed
- **AND** no rollout branch is pushed and no PR is opened

#### Scenario: Guarded platform recopy changes project configuration unexpectedly
- **WHEN** target-equivalent recovery changes `.dev-platform.toml` beyond permitted release metadata
- **THEN** rollout fails before publication

#### Scenario: Project-owned harness has a Copier conflict
- **GIVEN** `harness_mode=project`
- **WHEN** Copier leaves a conflict
- **THEN** the existing project-owned/reclaimed-path recovery rules remain authoritative and are not broadened by platform-mode recovery
