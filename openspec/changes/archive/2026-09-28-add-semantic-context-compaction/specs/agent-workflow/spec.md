## ADDED Requirements

### Requirement: Same-context compaction is considered at semantic work boundaries

Dev Platform SHALL support bounded same-context compaction opportunities at semantic transitions in live work rather than treating context-window fullness as the sole trigger. The initial capability SHALL keep the opportunity set small and inspectable, such as completion of a bounded plan/subtask or transition into a distinct verification phase.

#### Scenario: Subtask completes with substantial work remaining

- **GIVEN** a live managed run completes a bounded subtask
- **AND** meaningful downstream work remains in the same context
- **WHEN** the workflow reaches a configured semantic compaction opportunity
- **THEN** the platform may evaluate whether compaction is beneficial
- **AND** it does not compact merely because the opportunity exists

#### Scenario: No semantic boundary is reached

- **WHEN** a live run is still in the middle of one bounded reasoning/implementation step
- **THEN** the platform does not force semantic compaction solely from a fixed context-percentage threshold

### Requirement: Same-context compaction uses an inspectable economic gate

At a semantic compaction opportunity, the platform SHALL use a simple inspectable gate that considers available evidence about expected future replay avoided and compaction/rebuild overhead or risk. Compaction SHALL occur only when the gate passes. V1 SHALL NOT require a learned optimizer.

Before evaluating compaction benefit, the advisory workflow SHALL check whether safely reducible repeated instructions, eager loading of rarely needed tool/capability definitions, or prompt-boundary instability account for the hot payload. It SHALL evaluate compaction against the remaining live-history cost and SHALL NOT grow this check into a general prompt optimizer.

#### Scenario: Cheaper static reduction explains the payload

- **GIVEN** a semantic opportunity is reached
- **AND** repeated instructions or unneeded eager capability definitions account for the apparent replay cost
- **WHEN** the advisory gate evaluates the opportunity
- **THEN** it records the cheaper reduction opportunity and evaluates only residual compaction benefit
- **AND** it may keep the current context when that benefit is no longer material

#### Scenario: Expected replay benefit is not material

- **GIVEN** a semantic opportunity is reached
- **BUT** little future replay is expected or compact overhead is not justified
- **WHEN** the economic gate evaluates the opportunity
- **THEN** the workflow keeps the current context
- **AND** records an inspectable no-compact reason where dogfood evidence is enabled

#### Scenario: Expected replay benefit materially exceeds overhead

- **GIVEN** a semantic opportunity is reached
- **AND** available evidence indicates substantial future replay would otherwise continue
- **WHEN** the economic gate passes
- **THEN** the runtime may compact the same live context
- **AND** the decision remains distinguishable from a durable handoff

### Requirement: Same-context compaction preserves continuation truth

A compacted continuation SHALL preserve the exact managed task/OpenSpec identity, verified facts with canonical evidence references, unresolved assumptions, blockers and next intent needed to continue safely. Large exact evidence MAY remain cold through valid observation handles. Compact prose SHALL NOT override repository, OpenSpec, test or other canonical evidence.

#### Scenario: Compacted continuation resumes safely

- **GIVEN** same-context compaction succeeded
- **WHEN** work resumes
- **THEN** the agent can identify the same managed task and canonical contract
- **AND** verified facts remain distinguishable from unresolved assumptions
- **AND** referenced cold evidence can be recalled exactly when needed

#### Scenario: Referenced evidence is stale or missing

- **GIVEN** a compact continuation references evidence that can no longer be resolved or whose identity changed
- **WHEN** the continuation attempts to rely on that evidence
- **THEN** the missing/stale reference is surfaced
- **AND** the compact prose is not treated as proof of the unavailable evidence

### Requirement: Same-context compaction dogfood evidence is truthful

Initial compaction rollout SHALL remain advisory/dogfood and SHALL record bounded opportunity/decision evidence without inventing token savings. Deterministic before/after payload measures and observed replay MAY be recorded; token/cache/request savings SHALL be claimed only from exact supported runtime evidence.

#### Scenario: Runtime provides no exact cache-token evidence

- **WHEN** compaction reduces deterministic active payload size but the runtime exposes no canonical cache-token measurement
- **THEN** the deterministic reduction is recorded
- **AND** token/cache savings remain unknown rather than estimated
