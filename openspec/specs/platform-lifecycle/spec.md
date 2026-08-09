# Platform Lifecycle Specification

## Purpose

The platform lifecycle SHALL define safe, agent-driven task execution from synchronization through publication while preserving OpenSpec contract coherence and avoiding routine human Git hand-offs.
## Requirements
### Requirement: GitHub-aware task lifecycle

The platform SHALL fetch and compare the configured remote integration branch before starting work and again immediately before publication. It SHALL abort rather than auto-resolve divergent histories and SHALL never force-push.

#### Scenario: Remote main advances before start

- **WHEN** local main is clean and behind origin/main
- **THEN** the platform fast-forwards local main before creating task work

#### Scenario: Remote main diverges before publication

- **WHEN** local and remote integration history are not in a safe ancestor relationship
- **THEN** publication aborts and requires explicit reconciliation

### Requirement: Configurable publication modes

The platform SHALL support `pr` and `direct` publication modes. PR mode SHALL publish a feature branch and create or reuse a GitHub PR without auto-merging it. Direct mode SHALL publish only a safe fast-forward of the integration branch.

#### Scenario: Project uses PR publication

- **WHEN** `publish_mode=pr` and validated feature work is completed
- **THEN** the platform pushes the feature branch and creates or reuses a PR without merging it automatically

#### Scenario: Project uses direct publication

- **WHEN** `publish_mode=direct` and the integration branch safely descends from current origin/main
- **THEN** the platform may push the fast-forward update and SHALL abort on divergence

### Requirement: Composable workflow profiles

The platform SHALL provide `light`, `standard`, and `multi-agent` profiles from one template. Worktrees and the agent board SHALL only be mandatory for `multi-agent`.

#### Scenario: Single-agent project uses light profile

- **WHEN** a project selects `light`
- **THEN** it can use OpenSpec, checks and GitHub lifecycle without mandatory worktrees or agent-board coordination

#### Scenario: Concurrent agents use multi-agent profile

- **WHEN** a project selects `multi-agent`
- **THEN** isolated worktrees and machine-local scope coordination are part of the workflow

### Requirement: OpenSpec contract coherence

For non-trivial OpenSpec work, agents SHALL update planning artifacts before knowingly implementing changed intent, observable behavior, technical design, or execution order. Semantic OpenSpec verification and project-specific checks SHALL be completed before archive.

#### Scenario: Implementation discovers a different solution is required

- **WHEN** the intended behavior or implementation direction changes during an active OpenSpec change
- **THEN** the corresponding proposal, delta spec, design or tasks artifact is updated before implementation knowingly diverges

#### Scenario: Non-trivial OpenSpec change is completed

- **WHEN** implementation tasks are finished
- **THEN** project checks and semantic OpenSpec verification occur before the change is archived

### Requirement: Deliberate learning promotion

Platform friction SHALL remain local unless explicitly promoted. Promotion SHALL omit raw evidence by default, sanitize obvious credential-like content, and require an explicit authenticated action.

#### Scenario: Reusable friction is promoted

- **WHEN** an agent identifies a recurring platform-level problem and an authenticated promotion is explicitly requested
- **THEN** only sanitized structured evidence is sent to the central platform inbox

### Requirement: Workflow profile and harness ownership are composable

The platform SHALL treat workflow profile and lifecycle implementation ownership as independent configuration dimensions. `multi-agent` SHALL describe required capabilities, while `harness_mode=project` SHALL allow a downstream repository to satisfy those capabilities through its own reviewed implementation.

#### Scenario: Mature project provides its own multi-agent lifecycle

- **GIVEN** `workflow_profile=multi-agent` and `harness_mode=project`
- **WHEN** an agent starts or finishes work
- **THEN** platform-owned start/finish wrappers SHALL direct the agent to the repository-owned lifecycle described by project rules instead of requiring platform worktree/board implementations
- **AND** platform doctor SHALL validate only the project-required lifecycle files declared by the reviewed project contract plus common platform files

#### Scenario: Platform provides multi-agent lifecycle

- **GIVEN** `workflow_profile=multi-agent` and `harness_mode=platform`
- **WHEN** platform doctor validates the repository
- **THEN** the platform-managed worktree, board and Git-hook files remain mandatory
