# Project Factory Specification

## Purpose

The Project Factory SHALL define the reusable, versioned contract for creating and safely updating agent-first repositories without taking ownership of application-domain behavior.
## Requirements
### Requirement: Central versioned project factory

The platform SHALL provide a central Copier-based factory for creating new agent-first repositories and delivering reviewed updates to existing managed repositories.

#### Scenario: New project creation

- **WHEN** a new repository is rendered from a stable platform release
- **THEN** it receives the selected workflow profile, shared agent rules, OpenSpec policy, local workflow scripts, check configuration and self-contained CI scaffolding

### Requirement: Human-facing onboarding is one operation

The platform SHALL expose one first-time onboarding operation that accepts a repository and chooses the safe adoption process from repository state rather than requiring the human to select workflow internals.

#### Scenario: Human starts onboarding

- **WHEN** the human supplies an eligible `owner/name` repository to the onboarding workflow
- **THEN** the platform selects fresh, existing or already-adopted handling without asking for Copier profile, harness mode, publish mode or OpenSpec bootstrap steps

### Requirement: Fresh repositories use a validated fast path

A repository SHALL be eligible for automatic fresh adoption only when it has no existing Dev Platform metadata, no known project-process markers and remains below conservative repository-size thresholds. Fresh adoption SHALL use platform-selected defaults, validate the rendered result, retain an auditable PR, and MAY auto-merge only after required validation passes.

#### Scenario: Nearly empty repository is onboarded

- **GIVEN** a repository has no process markers and is below fresh thresholds
- **WHEN** onboarding renders the exact stable platform release
- **THEN** it initializes the platform OpenSpec workflow set, runs platform/OpenSpec/project validation, merges the adoption PR automatically, and promotes the repository to `managed`

#### Scenario: Fresh validation fails

- **WHEN** Copier conflicts, platform doctor, OpenSpec validation or selected project checks fail
- **THEN** onboarding stops without merging the target default branch or promoting the repository to `managed`

### Requirement: Existing repositories use cautious reviewed migration

Repositories that already contain project process contracts or exceed fresh thresholds SHALL NOT use automatic merge. Existing project OpenSpec/tool state and proven project-owned lifecycle components SHALL NOT be destructively initialized or replaced during first-time migration. Adoption SHALL derive a safe harness/profile plan before rendering.

#### Scenario: Existing project is detected

- **WHEN** onboarding finds an existing agent/OpenSpec/CI process marker or repository-size threshold is exceeded
- **THEN** it derives repository kind and harness ownership separately
- **AND** creates a reviewable adoption PR
- **AND** stops before merge or managed promotion

#### Scenario: Existing adoption has been reviewed and merged

- **GIVEN** the project default branch now contains Dev Platform ownership metadata
- **WHEN** the same onboarding operation is run again
- **THEN** it skips recopy and performs the mechanical central `managed` promotion

### Requirement: Local readiness has one entrypoint

Generated repositories SHALL provide one idempotent developer readiness entrypoint that safely synchronizes the integration branch when applicable, restores configured OpenSpec agent integrations using the platform workflow set, and runs platform/agent health checks.

#### Scenario: Developer opens an adopted clone

- **WHEN** the developer or agent runs `python3 scripts/dev.py ready`
- **THEN** local readiness is established without requiring the human to remember separate sync, OpenSpec init/update, platform doctor and agent doctor commands

### Requirement: Project and platform ownership remain separate

The platform SHALL own reusable engineering process only. Application/domain rules and project-specific architecture SHALL remain project-owned and SHALL NOT be promoted into the shared template unless they are demonstrably reusable.

#### Scenario: Project-specific rule is encountered

- **WHEN** an application-specific invariant is needed by only one downstream repository
- **THEN** the rule remains in that repository instead of becoming a platform default

### Requirement: Runtime workflow is self-contained

Generated repositories SHALL contain the platform-managed scripts needed for normal agent workflow and SHALL NOT require runtime access to the central `dev-platform` repository.

#### Scenario: Downstream repository runs normal workflow

- **WHEN** an agent starts, validates or publishes work in a generated repository
- **THEN** the required platform workflow executes from files present in that repository

### Requirement: OpenSpec remains an external tool

The platform SHALL define OpenSpec policy and compatibility expectations but SHALL NOT vendor OpenSpec-generated Claude/Codex skills as platform-owned source. Automated initialization SHALL be limited to the fresh adoption path or an explicit local readiness action; arbitrary mature-repository migration SHALL remain reviewed.

#### Scenario: OpenSpec integration is refreshed locally

- **WHEN** an adopted repository needs its configured OpenSpec agent integrations restored or updated
- **THEN** the external OpenSpec CLI generates them using the platform-selected workflow profile without modifying the developer's persistent global OpenSpec profile

### Requirement: Ordinary updates are reviewed

Copier upgrades to already managed repositories SHALL be applied as reviewable repository changes. The platform SHALL NOT remotely overwrite downstream project content or silently resolve update conflicts.

#### Scenario: Existing managed repository receives a platform update

- **WHEN** Copier produces changes or conflicts in a managed repository
- **THEN** the resulting diff is reviewed and unresolved conflicts block completion rather than being silently overwritten

### Requirement: Existing-project adoption preserves proven project-owned harnesses

The platform SHALL treat repository state and harness ownership as separate adoption decisions. An existing repository that already owns a coherent Git/task/worktree/check lifecycle SHALL be adoptable with `harness_mode=project` without replacing that lifecycle with platform-owned implementations.

#### Scenario: Mature multi-agent repository is detected

- **GIVEN** an existing repository owns worktree coordination, agent-board state, merge/publish helpers and project-specific check selection
- **WHEN** first-time adoption is planned
- **THEN** the derived plan selects `harness_mode=project`
- **AND** selects `workflow_profile=multi-agent` when isolated worktrees and agent/scope coordination are both detected
- **AND** keeps `publish_mode=pr` for the reviewed existing-project migration

#### Scenario: Existing repository has no coherent project harness

- **GIVEN** an existing repository contains code or process markers but does not own a coherent lifecycle that would conflict with the platform harness
- **WHEN** first-time adoption is planned
- **THEN** the platform MAY retain `harness_mode=platform` using conservative compatible defaults

#### Scenario: Harness ownership is ambiguous

- **WHEN** adoption finds conflicting lifecycle paths but cannot safely determine ownership
- **THEN** it fails closed or leaves an explicit review blocker
- **AND** does not silently overwrite the existing lifecycle files

### Requirement: Adoption plan is auditable without exposing routine internals to the human

The normal onboarding interface SHALL continue to accept only the repository identifier while the adoption output records the derived repository kind, workflow profile, harness mode, publish mode and evidence for non-default ownership decisions.

#### Scenario: Human starts mature repository onboarding

- **WHEN** the human runs `Adopt Project` for an eligible mature repository
- **THEN** no routine workflow-profile or harness-mode question is required
- **AND** the workflow summary or adoption PR explains why project-owned harness behavior was selected

### Requirement: Mature migration validates platform health separately from product health

For `harness_mode=project`, first-time adoption SHALL validate platform/OpenSpec integration without requiring the repository-owned project check selector to implement the platform selector CLI contract. Product/application verification SHALL remain the responsibility of the repository-owned CI and engineering rules.

#### Scenario: Project selector uses a different CLI

- **GIVEN** an existing project has its own `scripts/select_checks.py` that does not support `--execute` or `--full`
- **WHEN** adoption prepares a `harness_mode=project` migration
- **THEN** platform preparation does not invoke those unsupported flags
- **AND** still validates platform metadata, conflict hygiene and OpenSpec lifecycle/structure

#### Scenario: Adoption PR enters project CI

- **WHEN** the reviewed mature-project adoption PR is opened
- **THEN** the repository's existing CI may run its application checks in the dependency environment it already owns
- **AND** the platform does not require duplicate pre-PR product execution to consider migration preparation successful

### Requirement: Existing-project path collisions preserve explicit ownership

First-time adoption SHALL treat existing path collisions as ownership decisions. Project-owned files SHALL be preserved, new platform-managed files SHALL be installed when non-colliding, and unresolved ownership ambiguity SHALL remain reviewable or blocking rather than being silently overwritten.

#### Scenario: Existing project owns lifecycle documentation

- **GIVEN** a mature repository already has project-specific engineering/OpenSpec guidance at a path that would otherwise collide with generic platform guidance
- **WHEN** adoption renders the platform
- **THEN** the existing guidance is not destructively replaced
- **AND** required platform guidance is installed through an explicit ownership-safe mechanism

### Requirement: Project configuration records main protection and PR merge policy

Generated project configuration SHALL explicitly record whether the integration branch is expected to be protected and how ordinary task PRs are completed.

#### Scenario: Standard project is generated for protected delivery

- **WHEN** a standard or multi-agent platform-owned project is generated with normal safe defaults
- **THEN** configuration records `protected_main=true`, `publish_mode=pr`, and `pr_merge_mode=auto`

#### Scenario: Intentionally simple unprotected project uses direct publication

- **WHEN** a project deliberately uses direct publication
- **THEN** configuration records `protected_main=false`
- **AND** doctor can distinguish that choice from an accidental protected-main mismatch

### Requirement: Invalid protected-main publication combinations are rejected during configuration

The project factory SHALL reject or clearly fail validation for combinations that cannot satisfy the protected-main lifecycle.

#### Scenario: Protected light project requests direct publication

- **GIVEN** the light profile has no mandatory feature branch
- **WHEN** protected main is enabled with direct publication
- **THEN** generation/doctor rejects the combination
- **AND** instructs the project to use a feature-capable profile or a reviewed project-owned harness

### Requirement: Project-owned harness workflow guidance is preserved during upgrades

For `harness_mode=project`, Copier SHALL preserve an existing repository-owned `docs/engineering/agent-workflow.md` rather than replacing it with the generic platform harness guide.

#### Scenario: Mature project owns workflow guidance

- **GIVEN** `harness_mode=project`
- **AND** `docs/engineering/agent-workflow.md` already exists
- **WHEN** a reviewed Copier upgrade is applied
- **THEN** that file is preserved without conflict
- **AND** repository-specific publication and CI guidance remains authoritative

#### Scenario: Platform owns workflow guidance

- **GIVEN** `harness_mode=platform`
- **WHEN** a Copier upgrade changes generic workflow guidance
- **THEN** the platform-managed `docs/engineering/agent-workflow.md` remains eligible for update

### Requirement: Generated repositories carry managed-task authoring configuration

The Project Factory SHALL render the configuration required for a participating repository to create managed tasks in the shared Development Backlog without embedding per-agent or machine-specific instructions. At minimum the rendered contract SHALL identify the backlog repository, project label and default priority.

#### Scenario: New managed repository is rendered

- **WHEN** a repository is generated/adopted with Development Backlog participation
- **THEN** its platform configuration contains the configured backlog repository, project label and default priority
- **AND** the repository's GitHub origin remains the authoritative target-repository identity used during authoring

#### Scenario: Existing managed repository receives authoring support

- **WHEN** the platform release containing managed-task authoring is applied through the normal Copier update path
- **THEN** the configuration/helper/guidance changes are presented as a reviewable update
- **AND** existing project-owned content is not silently overwritten to install the feature

### Requirement: Authoring runtime is self-contained in generated repositories

The managed-task authoring entrypoint SHALL be delivered as part of the self-contained generated repository workflow and SHALL not require runtime access to the central `dev-platform` checkout.

#### Scenario: Agent authors a task in a downstream managed repository

- **WHEN** it invokes the standard managed-task authoring command
- **THEN** all platform-owned helper code needed for validation and GitHub publication is present in that repository
- **AND** the command uses configured GitHub/OpenSpec dependencies rather than importing mutable runtime code from `dev-platform@main`

### Requirement: Generated managed repositories can address Development Backlog workflow state

A repository participating in managed-task execution SHALL carry validated
configuration sufficient to resolve the intended Development Backlog GitHub
Project and its workflow `Status` field through supported authenticated GitHub
interfaces. The configuration SHALL use a stable Project locator and SHALL NOT
depend on UI scraping or a mutable display title alone.

#### Scenario: Managed repository receives Project-status support

- **WHEN** the platform release containing status synchronization is rendered or applied
- **THEN** the repository has the self-contained helper/runtime and reviewed configuration needed to resolve its managed Issue Project item
- **AND** the expected workflow options include `Backlog`, `Ready`, `In progress`, `In review`, `Blocked`, and `Done`

#### Scenario: Project workflow configuration is unavailable

- **WHEN** a managed execution requires status synchronization but the Project locator, field mapping or mutation permission is missing/invalid
- **THEN** platform validation/lifecycle reports an actionable setup failure
- **AND** it does not silently claim that central workflow state is synchronized

### Requirement: Project-status synchronization preserves execution-plane boundaries

The Project Factory SHALL keep Development Backlog workflow projection separate
from machine-local multi-agent coordination and from quick tasks without a
managed source Issue.

#### Scenario: Multi-agent task starts

- **WHEN** a managed multi-agent task is claimed
- **THEN** the local board continues to own worktree/scope coordination
- **AND** Development Backlog `Status` represents the human lifecycle stage rather than mirroring local board records

#### Scenario: Quick task runs

- **WHEN** an immediate quick task has no managed Development Backlog source
- **THEN** the Project-status helper performs no central workflow mutation solely because local task execution occurs

### Requirement: Managed projects preserve a shared-workspace permission contract

The Project Factory SHALL render a portable shared-workspace permission
primitive into every workflow profile. On POSIX filesystems, platform-owned
shared directories SHALL preserve group write plus setgid inheritance and
platform-owned shared files/locks SHALL preserve group read/write, including
after atomic replacement. The intended group SHALL be derived from the reviewed
checkout or a machine-local override and SHALL NOT be hardcoded to a particular
user, gid or deployment group.

#### Scenario: Fresh managed project is used by a second group member

- **GIVEN** a fresh rendered project whose integration root is owned by a shared
  POSIX group
- **WHEN** one group member creates platform state, Git metadata and a task
  worktree through supported entry points
- **THEN** another member of that group can read and update the shared lifecycle
  state and perform normal Git object/ref/worktree operations
- **AND** no world-write permission is required

#### Scenario: Atomic shared state is replaced

- **WHEN** a platform writer atomically replaces board, friction, cleanup or
  publication state
- **THEN** the replacement file is group-readable and group-writable before it
  becomes visible at the final path
- **AND** repeated writes by alternating group members remain valid

#### Scenario: Platform cannot represent POSIX group modes

- **WHEN** the project filesystem does not support the POSIX permission contract
- **THEN** the platform reports that enforcement is unavailable using a defined
  non-mutating compatibility path
- **AND** it does not attempt unsafe permission emulation

### Requirement: Existing projects receive bounded permission migration

Copier update SHALL add the shared-workspace primitive and lifecycle wiring to
existing managed projects without overwriting project-owned content or widening
permissions outside the registered project and Git common directory.

#### Scenario: Existing project already has local permission tooling

- **GIVEN** an existing managed project has a project-owned permission audit or
  wrappers such as the proven `Jara_Fin` pattern
- **WHEN** the platform update is applied
- **THEN** platform-owned writers adopt the shared primitive
- **AND** project-owned tooling/content is preserved
- **AND** automation does not create two competing repair loops for the same
  platform-owned paths

#### Scenario: Existing checkout contains unrepairable foreign-owned paths

- **WHEN** migration finds a required shared path that the current user cannot
  safely repair
- **THEN** it reports the exact bounded path, current ownership/mode and owner
  action required
- **AND** it does not use sudo, traverse outside the registered roots or continue
  into a remote-mutating lifecycle step

### Requirement: Platform-owned check mappings do not silently collapse applicable coverage to zero commands

For `harness_mode=platform`, the rendered check-selection contract SHALL make the selected command set observable. When an affected scope is configured as requiring platform-managed checks, resolving that applicable scope to zero executable commands SHALL be treated as invalid check configuration rather than a successful validation result.

#### Scenario: Applicable configured scope resolves to no commands

- **GIVEN** a platform-owned harness and a changed scope matched by the project check configuration
- **WHEN** the matching check group contains no executable command
- **THEN** platform validation/doctor SHALL report a blocking configuration error
- **AND** SHALL NOT represent that group as passed

#### Scenario: Applicable configured scope resolves to commands

- **WHEN** the selected platform-owned check group resolves to one or more commands
- **THEN** the platform executes the selected commands according to the existing check policy
- **AND** reports the commands/results as executed evidence

#### Scenario: Project owns product verification

- **GIVEN** `harness_mode=project`
- **WHEN** Dev Platform validates common platform/OpenSpec health
- **THEN** it SHALL NOT require the repository-owned product harness to implement the platform selector contract
- **AND** SHALL NOT invent replacement product checks merely because platform-owned selection is absent

### Requirement: Platform-owned verification distinguishes syntax checks from product-test coverage

The platform SHALL report the type of configured check evidence truthfully and SHALL NOT imply that syntax/byte-compilation alone proves product-test coverage when the reviewed platform-owned check contract declares or detects a separate product test surface.

#### Scenario: Only compilation runs for a stack with configured test coverage

- **GIVEN** platform-owned configuration indicates an application/test surface beyond compilation
- **WHEN** verification executes only compile/syntax checks and no configured product test command
- **THEN** the platform SHALL report product-test coverage as unconfirmed
- **AND** SHALL fail closed when that missing command is an applicable required platform-managed check

### Requirement: Generated agent guidance exposes one compact cross-agent task protocol

The Project Factory SHALL render one canonical vendor-neutral repository-wide entrypoint in `AGENTS.md` for discovering and safely entering the shared cross-agent task protocol. Root `AGENTS.md` SHALL be a bounded always-on navigation and invariant layer rather than a complete duplicate of detailed workflow documentation. It SHALL contain the source-of-truth model, task-intent boundaries, safety/stop invariants required before further context can be loaded, canonical lifecycle entrypoints, platform/project ownership boundaries and stable repository-relative navigation to detailed guidance.

Detailed managed-task, OpenSpec, worktree/publication, provider-routing, release, friction and other specialized workflow instructions SHALL live in canonical thematic repository docs or executable mechanisms and be loaded when relevant. Moving detail out of root guidance SHALL NOT weaken or remove the underlying process, safety, verification or completion contracts.

Tool-specific instruction files SHALL reference/import the canonical repository-wide entrypoint rather than fork its semantics. The platform SHALL NOT require a Hermes-specific or other vendor-specific parallel process contract merely to support an additional agent shell.

Semantic-preserving compaction of this guidance SHALL be verified with focused structural, navigation, destination/link, render and semantic-preservation evidence. It SHALL NOT require an unrelated full software regression suite solely because instruction, documentation or template text changed. Where compaction intentionally changes directive meaning rather than only shortening or relocating it, the change SHALL be reconciled with OpenSpec first and SHALL carry targeted behavioral evidence for the affected surface.

#### Scenario: Repository supports Codex and Claude

- **WHEN** agent guidance is rendered for a repository supporting Codex, Claude or another compatible agent shell
- **THEN** `AGENTS.md` provides the same canonical repository-wide map and always-on invariants
- **AND** `CLAUDE.md` continues to import/reference `AGENTS.md`
- **AND** tool-specific platform-owned instruction files remain thin references/adapters instead of duplicate managed-task or lifecycle rule sets
- **AND** the repository does not require separate vendor-specific copies of the shared process contract

#### Scenario: Agent needs specialized workflow detail

- **WHEN** an agent reaches a managed-task, OpenSpec, worktree/publication, routing, friction or other specialized concern
- **THEN** root guidance provides a stable discoverable route to the canonical detailed repository guidance for that concern
- **AND** the detailed contract remains available without being embedded wholesale in the always-loaded root context

#### Scenario: Guidance is compacted

- **WHEN** platform guidance is reorganized to reduce root context
- **THEN** every meaningful process/safety directive is either retained as an always-on root invariant or moved to one canonical discoverable destination
- **AND** existing lifecycle, verification and completion semantics remain unchanged unless a separate approved OpenSpec delta explicitly changes them

#### Scenario: Desired behavior change is discovered

- **WHEN** directive meaning is intentionally changed rather than only shortened or relocated
- **THEN** the change is reconciled with OpenSpec before proceeding
- **AND** targeted behavioral evidence is required for the affected surface as applicable

#### Scenario: Instruction-only compaction is verified

- **WHEN** a change modifies only instruction, documentation or template text without changing executable behavior
- **THEN** verification uses focused structure, anchor, destination/link, render and semantic-preservation evidence
- **AND** an unrelated full software regression suite is not required solely because those file paths changed

### Requirement: Root agent guidance has a mechanically enforced context budget

The Project Factory SHALL enforce a bounded structural/size contract for platform-owned root agent guidance in central dogfood and rendered downstream output. The budget SHALL be small enough to prevent detailed specialized workflows from silently accumulating again and SHALL include required navigation/invariant anchors. A deliberate future increase SHALL require an explicit update to the contract or its tested configuration rather than incidental prose growth.

#### Scenario: Root guidance exceeds the approved budget

- **WHEN** a platform change makes central or rendered platform-owned root `AGENTS.md` exceed the configured hard budget
- **THEN** platform validation fails with an actionable indication that always-on context has grown beyond the approved boundary
- **AND** the change is not accepted merely because all moved text is individually valid guidance

#### Scenario: Required navigation anchor is removed

- **WHEN** root guidance no longer exposes a required source-of-truth, task-intent, safety/stop, lifecycle-entrypoint, ownership or detailed-guidance navigation category
- **THEN** the guidance contract test fails
- **AND** an agent is not expected to infer the missing contract from undocumented convention

#### Scenario: Platform renders supported profiles

- **WHEN** light, standard and multi-agent platform-owned profiles are rendered
- **THEN** each resulting root guidance file satisfies the bounded context contract
- **AND** profile-specific always-on safety requirements remain present without reintroducing full specialized workflow manuals

