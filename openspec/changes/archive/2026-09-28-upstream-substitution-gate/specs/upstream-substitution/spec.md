# upstream-substitution Specification Delta

## ADDED Requirements

### Requirement: External agent-infrastructure upstreams are evaluated per overlapping capability

Dev Platform SHALL evaluate an external agent-infrastructure upstream (tooling other than an agent execution runtime) that overlaps its own implementation through a bounded substitution pilot. The pilot SHALL decide separately for each overlapping capability. Every evaluated capability SHALL end in exactly one current decision: `adopt-next-step`, `watch-only`, or `reject-for-now`. A decision SHALL NOT be derived solely from upstream feature claims, architecture similarity, or the existence of an own Dev Platform implementation.

#### Scenario: Upstream overlaps several capabilities

- **GIVEN** an upstream overlaps several Dev Platform capabilities
- **WHEN** the substitution pilot completes
- **THEN** each overlapping capability carries exactly one decision with its own evidence
- **AND** an adoption for one capability does not authorize any other capability

#### Scenario: Retention justified only by existing code

- **GIVEN** a decision keeps the Dev Platform implementation
- **WHEN** its only rationale is that Dev Platform already has an implementation
- **THEN** the decision record is invalid until compatibility evidence supports the retention

### Requirement: Substitution pilots use a pinned stable release in an isolated sandbox

A substitution pilot SHALL evaluate the exact current stable release of the upstream. Prerelease builds MAY inform roadmap evidence but SHALL NOT become the evaluated default. The pilot SHALL run in a disposable sandbox with isolated home and install locations and local disposable repositories. The upstream's self-update, shell-profile injection, automatically applied hooks or MCP servers, and outbound usage reporting SHALL be disabled unless a scenario explicitly measures them inside that sandbox. The pilot SHALL NOT use real credentials, SHALL NOT modify shared operator configuration, other agents' worktrees or real managed repositories, and SHALL include at least one representative Dev Platform workflow and at least one managed-project scenario freshly rendered from the current template with the agent surfaces in use.

#### Scenario: Upstream mutates home configuration by default

- **GIVEN** the upstream writes agent settings or shell profiles in the user's home directory by default
- **WHEN** the pilot runs
- **THEN** those writes land only in the sandbox home
- **AND** the operator's real home configuration is unchanged after the pilot

#### Scenario: Only a prerelease offers a capability

- **GIVEN** a capability exists only in a prerelease
- **WHEN** the pilot records its decision
- **THEN** that capability is not recorded as `adopt-next-step` on prerelease evidence
- **AND** the prerelease observation is recorded as roadmap evidence only

### Requirement: Substitution decisions carry maintenance and risk evidence

Each capability decision SHALL identify:

- the exact upstream version and scenarios;
- observed behavior and the Dev Platform acceptance outcome;
- lifecycle coupling, migration cost, and release cadence and churn;
- security and privacy effects;
- failure and rollback behavior;
- Codex and Claude compatibility;
- the ownership classification: taken directly, taken through a thin Dev Platform adapter, or Dev Platform-owned;
- a measured maintenance-surface baseline of the affected own source, tests and documentation.

An `adopt-next-step` SHALL name the concrete own code, workflow steps, tests and documentation that the adoption retires. A retention SHALL name the evidence that prevents substitution. Unavailable measurements SHALL remain unknown rather than inferred.

#### Scenario: Adoption names its retirement set

- **WHEN** a capability is recorded as `adopt-next-step`
- **THEN** the record lists the own implementation it retires and its measured size
- **AND** the record states the projected maintenance reduction

### Requirement: Adoption preserves pinned releases and a single source of truth

An `adopt-next-step` decision SHALL authorize only a separately authored managed change. That change SHALL integrate the upstream capability as an opt-in Dev Platform capability or thin adapter. It SHALL pin the exact upstream version and the exact reviewed revision of any upstream-distributed resources, and it SHALL disable or prove containment of the upstream's self-update and mutable default-branch pulls. It SHALL deliver the capability to managed projects only through an immutable Dev Platform release and controlled rollout, with rollback to the prior release. In the same delivery, it SHALL retire the superseded own mechanism, or record a bounded transitional exit criterion. Two mechanisms with the same responsibility SHALL NOT remain without such a criterion.

#### Scenario: Upstream updates itself

- **GIVEN** an adopted upstream capability supports automatic self-update
- **WHEN** the upstream publishes a new release
- **THEN** managed-project behavior does not change until a new immutable Dev Platform release pins the new version

#### Scenario: Superseded mechanism is left in place

- **GIVEN** an adoption change integrates an upstream capability
- **WHEN** the superseded own mechanism remains active without a transitional exit criterion
- **THEN** the change is not complete

### Requirement: Substitution cannot transfer the lifecycle ownership core

A substitution decision SHALL NOT transfer ownership of the requirement-first and OpenSpec lifecycle, managed task identity, writer and worktree containment, verification and publication, or immutable release and controlled rollout. An upstream concept that must become authoritative for any of these to function SHALL be recorded as negative coupling evidence. After any adoption, these lifecycle guarantees SHALL be re-verified.

#### Scenario: Upstream requires owning the task lifecycle

- **GIVEN** an upstream capability works only if its own task or specification state becomes authoritative
- **WHEN** the capability is evaluated
- **THEN** the coupling is recorded as negative evidence
- **AND** the capability is not recorded as `adopt-next-step`
