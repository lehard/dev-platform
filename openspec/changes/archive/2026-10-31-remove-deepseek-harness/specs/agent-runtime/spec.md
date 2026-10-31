## ADDED Requirements

### Requirement: An external runtime run keeps Dev Platform as the single lifecycle owner

For an external runtime run, Dev Platform SHALL supply the authorized task workspace and SHALL remain the authority for task status and completion. The runtime MAY own its internal session/tool/subagent lifecycle for the bounded run but SHALL NOT create a competing Backlog/OpenSpec/publication lifecycle.

#### Scenario: External runtime run reaches an internal terminal state

- **WHEN** an external runtime run returns a successful runtime result
- **THEN** the result is only execution evidence
- **AND** Dev Platform still performs its normal verification/publication lifecycle before the managed task can complete

### Requirement: External runtime write containment fails closed

A write-capable external runtime execution SHALL NOT be reported as safely contained unless the platform can prove the required writer/workspace boundary for the actual supported runtime mode. The adapter SHALL expose an actionable distinction between proven, partial/insufficient, and unavailable containment evidence as needed by the caller.

#### Scenario: External runtime write containment is not provable

- **GIVEN** an experimental external runtime is asked to run write-capable work
- **AND** the supported host/runtime cannot prove the required assigned-workspace boundary
- **WHEN** adapter preflight runs
- **THEN** the write-capable run is refused or retained on a safe existing path
- **AND** the platform does not claim a successful contained delegation

### Requirement: External runtime evidence maps into the common execution provenance

An external runtime adapter SHALL map bounded runtime identity/version, run identity where safe, timing, terminal result/cancellation/cleanup, usage evidence where authoritative, and required containment evidence into the platform's runtime-neutral execution provenance. It SHALL NOT require a parallel execution database or copy the full runtime session/transcript into Dev Platform by default.

Unavailable usage or runtime fields SHALL remain unknown rather than fabricated.

#### Scenario: External runtime exposes token usage

- **GIVEN** a supported pinned runtime version returns compatible structured usage
- **WHEN** the adapter finalizes execution evidence
- **THEN** the compatible normalized fields are recorded with truthful source/status
- **AND** runtime-specific event objects are not required by upper lifecycle layers

## REMOVED Requirements

### Requirement: DeepSeek Harness integration is pinned and isolated

**Reason**: DeepSeek Harness is removed from Dev Platform (owner decision 2026-10-28).
**Migration**: Delete `[experimental_runtime.deepseek_harness]` from `.dev-platform.toml`; a leftover section fails explicitly.

### Requirement: DeepSeek Harness upgrades are explicit compatibility events

**Reason**: DeepSeek Harness is removed from Dev Platform.
**Migration**: None.

### Requirement: Initial DSH adapter scope remains deliberately narrow

**Reason**: DeepSeek Harness is removed from Dev Platform.
**Migration**: None.

### Requirement: External runtime execution preserves one lifecycle owner

**Reason**: Replaced by "An external runtime run keeps Dev Platform as the single lifecycle owner" with a runtime-neutral scenario.
**Migration**: None.

### Requirement: External runtime containment fails closed

**Reason**: Replaced by "External runtime write containment fails closed" with a runtime-neutral scenario.
**Migration**: None.

### Requirement: External runtime evidence uses the common execution provenance

**Reason**: Replaced by "External runtime evidence maps into the common execution provenance" with a runtime-neutral scenario.
**Migration**: None.
