# upstream-substitution Specification

## Purpose
Define how Dev Platform evaluates an external agent-infrastructure upstream as a substitute for overlapping parts of its own implementation, and the constraints any resulting adoption must preserve.

## Requirements

### Requirement: External agent-infrastructure upstreams are evaluated per overlapping capability

Dev Platform SHALL evaluate an external agent-infrastructure upstream (tooling other than an agent execution runtime) that overlaps its own implementation through a bounded substitution pilot. The pilot SHALL decide separately for each overlapping capability. Every evaluated capability SHALL end in exactly one current decision: `adopt-next-step`, `watch-only`, or `reject-for-now`.

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

A substitution pilot SHALL evaluate the exact current stable release of the upstream. Prerelease builds MAY inform roadmap evidence but SHALL NOT become the evaluated default.

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

An `adopt-next-step` SHALL name the concrete own code, workflow steps, tests and documentation that the adoption retires.

#### Scenario: Adoption names its retirement set

- **WHEN** a capability is recorded as `adopt-next-step`
- **THEN** the record lists the own implementation it retires and its measured size
- **AND** the record states the projected maintenance reduction

### Requirement: Adoption preserves pinned releases and a single source of truth

An `adopt-next-step` decision SHALL authorize only a separately authored managed change.

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

### Requirement: TeamAI substitution boundary is recorded

Dev Platform SHALL keep a committed TeamAI substitution decision record. The record SHALL identify the exact evaluated stable version and hold exactly one decision for each of these overlap areas:

- shared agent resources and their distribution;
- version-bound or on-demand skills and instructions;
- project and team learnings and recall;
- codebase knowledge or wiki;
- dashboard and session, usage and friction analytics;
- multi-project management, roles and namespaces;
- model profiles.

#### Scenario: Pilot completes without adoption

- **GIVEN** the TeamAI pilot recorded its decisions
- **WHEN** no adoption change has been delivered
- **THEN** every overlap area is Dev Platform-owned
- **AND** rendered managed projects neither install nor invoke TeamAI

#### Scenario: Area is decided adopt-next-step

- **GIVEN** an area is recorded as `adopt-next-step`
- **WHEN** the decision record is reviewed
- **THEN** it names the own implementation to retire and its measured size
- **AND** integration happens only through a separate change under the adoption requirement of this capability

### Requirement: Substitution decisions are not derived solely from claims or an own implementation

A substitution pilot decision for an evaluated capability SHALL NOT be derived solely from upstream feature claims, architecture similarity, or the existence of an own Dev Platform implementation.

#### Scenario: Decision rests only on claims, similarity or an own implementation

- **WHEN** a substitution pilot records a decision for an evaluated capability
- **THEN** the decision is not derived solely from upstream feature claims, architecture similarity, or the existence of an own Dev Platform implementation

### Requirement: Substitution pilots run in a disposable sandbox

A substitution pilot SHALL run in a disposable sandbox with isolated home and install locations and local disposable repositories.

#### Scenario: Pilot environment is prepared

- **WHEN** a substitution pilot runs
- **THEN** it runs in a disposable sandbox with isolated home and install locations
- **AND** it uses local disposable repositories

### Requirement: Upstream self-modifying and reporting behavior is disabled in a substitution pilot

During a substitution pilot, the upstream's self-update, shell-profile injection, automatically applied hooks or MCP servers, and outbound usage reporting SHALL be disabled unless a scenario explicitly measures them inside the pilot's disposable sandbox.

#### Scenario: Upstream behavior is not measured by any scenario

- **GIVEN** no pilot scenario explicitly measures the upstream's self-update, shell-profile injection, automatically applied hooks or MCP servers, or outbound usage reporting inside the pilot's disposable sandbox
- **WHEN** the substitution pilot runs
- **THEN** those upstream behaviors are disabled

### Requirement: Substitution pilots use no real credentials or real shared state

A substitution pilot SHALL NOT use real credentials, and SHALL NOT modify shared operator configuration, other agents' worktrees or real managed repositories.

#### Scenario: Pilot completes

- **WHEN** a substitution pilot completes
- **THEN** it used no real credentials
- **AND** shared operator configuration, other agents' worktrees and real managed repositories are unmodified

### Requirement: Substitution pilots include representative Dev Platform and managed-project scenarios

A substitution pilot SHALL include at least one representative Dev Platform workflow and at least one managed-project scenario freshly rendered from the current template with the agent surfaces in use.

#### Scenario: Pilot scenario set is defined

- **WHEN** a substitution pilot defines its scenarios
- **THEN** they include at least one representative Dev Platform workflow
- **AND** at least one managed-project scenario freshly rendered from the current template with the agent surfaces in use

### Requirement: Substitution capability decisions identify upstream, behavior and coupling evidence

Each substitution capability decision SHALL identify:

- the exact upstream version and scenarios;
- observed behavior and the Dev Platform acceptance outcome;
- lifecycle coupling, migration cost, and release cadence and churn;
- security and privacy effects.

#### Scenario: Capability decision is recorded with upstream and coupling evidence

- **WHEN** a substitution capability decision is recorded
- **THEN** it identifies the exact upstream version and scenarios, observed behavior and the Dev Platform acceptance outcome
- **AND** it identifies lifecycle coupling, migration cost, release cadence and churn, and security and privacy effects

### Requirement: Substitution capability decisions identify failure, compatibility, ownership and maintenance evidence

Each substitution capability decision SHALL identify:

- failure and rollback behavior;
- Codex and Claude compatibility;
- the ownership classification: taken directly, taken through a thin Dev Platform adapter, or Dev Platform-owned;
- a measured maintenance-surface baseline of the affected own source, tests and documentation.

#### Scenario: Capability decision is recorded with ownership and maintenance evidence

- **WHEN** a substitution capability decision is recorded
- **THEN** it identifies failure and rollback behavior and Codex and Claude compatibility
- **AND** it identifies the ownership classification: taken directly, taken through a thin Dev Platform adapter, or Dev Platform-owned
- **AND** it identifies a measured maintenance-surface baseline of the affected own source, tests and documentation

### Requirement: A substitution retention names the evidence preventing substitution

A retention in a substitution capability decision SHALL name the evidence that prevents substitution.

#### Scenario: Retention is decided

- **WHEN** a substitution capability decision is a retention
- **THEN** it names the evidence that prevents substitution

### Requirement: Unavailable substitution measurements remain unknown

In a substitution capability decision, unavailable measurements SHALL remain unknown rather than inferred.

#### Scenario: A measurement is unavailable

- **WHEN** a measurement for a substitution capability decision is unavailable
- **THEN** the decision records it as unknown
- **AND** does not infer a value

### Requirement: Adoption changes integrate as an opt-in capability or thin adapter

The managed change authorized by an `adopt-next-step` decision SHALL integrate the upstream capability as an opt-in Dev Platform capability or thin adapter.

#### Scenario: Adoption change integrates the upstream capability

- **WHEN** the managed change authorized by an `adopt-next-step` decision integrates the upstream capability
- **THEN** the capability is integrated as an opt-in Dev Platform capability or thin adapter

### Requirement: Adoption changes pin upstream versions and contain self-update

The managed change authorized by an `adopt-next-step` decision SHALL pin the exact upstream version and the exact reviewed revision of any upstream-distributed resources, and it SHALL disable or prove containment of the upstream's self-update and mutable default-branch pulls.

#### Scenario: Adoption change references the upstream

- **WHEN** the managed change authorized by an `adopt-next-step` decision is delivered
- **THEN** it pins the exact upstream version and the exact reviewed revision of any upstream-distributed resources
- **AND** the upstream's self-update and mutable default-branch pulls are disabled or proven contained

### Requirement: Adoption changes deliver only through an immutable release with rollback

The managed change authorized by an `adopt-next-step` decision SHALL deliver the capability to managed projects only through an immutable Dev Platform release and controlled rollout, with rollback to the prior release.

#### Scenario: Adopted capability reaches managed projects

- **WHEN** the capability of an `adopt-next-step` adoption change reaches managed projects
- **THEN** it arrives only through an immutable Dev Platform release and controlled rollout
- **AND** rollback to the prior release is available

### Requirement: Adoption changes retire the superseded own mechanism

In the same delivery, the managed change authorized by an `adopt-next-step` decision SHALL retire the superseded own mechanism, or record a bounded transitional exit criterion. Two mechanisms with the same responsibility SHALL NOT remain without a bounded transitional exit criterion.

#### Scenario: Adoption change is delivered

- **WHEN** the managed change authorized by an `adopt-next-step` decision is delivered
- **THEN** the same delivery retires the superseded own mechanism or records a bounded transitional exit criterion
- **AND** two mechanisms with the same responsibility do not remain without such a criterion

### Requirement: TeamAI overlap areas remain Dev Platform-owned until integrated

Until a separately delivered adoption change integrates a TeamAI overlap area, that TeamAI overlap area SHALL remain Dev Platform-owned.

#### Scenario: TeamAI overlap area is not yet integrated

- **GIVEN** no separately delivered adoption change integrates a TeamAI overlap area
- **WHEN** ownership of that area is determined
- **THEN** the area is Dev Platform-owned

### Requirement: TeamAI is not a dependency

TeamAI SHALL NOT be a dependency of Dev Platform or of managed projects.

#### Scenario: Dependencies are inspected

- **WHEN** the dependencies of Dev Platform or of a managed project are inspected
- **THEN** TeamAI is not among them
