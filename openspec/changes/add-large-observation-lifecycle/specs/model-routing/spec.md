## ADDED Requirements

### Requirement: Large observations can become cold while exact evidence remains recallable

Dev Platform SHALL support a provider-neutral lifecycle for eligible large tool/runtime observations in which the exact original payload is preserved for the supported run/session lifetime and the active context MAY replace that payload with a bounded reference. The bounded reference SHALL identify the original through a stable handle and SHALL NOT become a semantic replacement for the exact evidence.

Eligibility SHALL remain configurable or evidence-driven in the initial capability; the platform SHALL NOT treat a research-specific size threshold as a universal invariant.

#### Scenario: Large observation is cooled

- **GIVEN** a supported runtime returns an eligible large observation
- **WHEN** the observation lifecycle cools that result
- **THEN** the exact original payload remains recoverable
- **AND** the active representation contains a stable handle plus bounded metadata/excerpt
- **AND** later turns do not require the full original payload to remain hot by default

#### Scenario: Small observation does not need cooling

- **GIVEN** a returned observation is below the configured/evidenced eligibility boundary
- **WHEN** the observation lifecycle evaluates it
- **THEN** the existing direct representation remains usable
- **AND** no unnecessary archive/recall ceremony is required

#### Scenario: Cooling is unsupported or fails

- **GIVEN** the current runtime cannot safely provide the observation lifecycle or preservation fails
- **WHEN** the result would otherwise be cooled
- **THEN** the platform keeps or restores the current full-evidence path
- **AND** does not claim that the observation was safely archived

### Requirement: Cold observations support exact targeted recall

A cold observation SHALL support exact bounded recall against the preserved original. Recall SHALL allow the caller to retrieve a requested range or other deterministic bounded subset without reinjecting the entire original by default.

#### Scenario: Agent needs one exact failure region

- **GIVEN** a cold observation has a valid handle
- **AND** later reasoning needs one bounded exact region
- **WHEN** targeted recall is requested
- **THEN** the returned content matches the preserved original exactly for that requested region
- **AND** unrelated portions are not returned by default

#### Scenario: Handle is stale or unknown

- **WHEN** recall references a handle that cannot be resolved in the current supported lifetime
- **THEN** the platform reports the missing/stale evidence explicitly
- **AND** does not fabricate recalled content

### Requirement: Observation-efficiency evidence remains truthful and bounded

The platform SHALL reuse existing execution-efficiency provenance for observation lifecycle evidence rather than create a parallel transcript store. Deterministic payload fields MAY include source bytes/lines, hot bytes/lines, recall bytes/lines, trigger count/rate and trigger intensity. Token/cache/request fields SHALL be populated only from authoritative supported runtime evidence; deterministic payload reduction SHALL NOT be labelled as measured token savings.

#### Scenario: Runtime exposes no canonical token breakdown

- **GIVEN** deterministic source and hot payload sizes are known
- **BUT** the runtime exposes no supported exact token/cache usage
- **WHEN** observation evidence is recorded
- **THEN** payload reduction is retained as deterministic evidence
- **AND** token/cache savings remain unknown rather than inferred
