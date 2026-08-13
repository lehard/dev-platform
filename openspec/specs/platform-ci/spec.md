# Platform CI Specification

## Purpose

Platform CI SHALL validate platform-managed behavior without requiring downstream repositories to execute mutable or inaccessible logic from the central private repository.
## Requirements
### Requirement: Downstream CI has no private repository access prerequisite

Generated project CI SHALL execute platform-managed check scripts from the checked-out downstream repository and SHALL NOT require access to a private reusable workflow in `dev-platform`.

#### Scenario: Private project adopts the platform

- **WHEN** the project runs its generated CI without any cross-repository Actions Access setting
- **THEN** GitHub executes the platform-managed checks from local Copier-managed files

### Requirement: CI updates remain reviewed and versioned

The downstream CI workflow and check scripts SHALL remain Copier-managed project files so platform changes arrive through reviewed template updates rather than mutable remote execution.

#### Scenario: Platform changes generated CI behavior

- **WHEN** a newer platform version changes the generated CI contract
- **THEN** an existing project receives that change through a reviewable Copier update instead of automatically executing central branch content

### Requirement: Generated guidance matches self-contained CI behavior

Generated documentation SHALL state that downstream platform CI runs from Copier-managed local files and SHALL NOT instruct agents that CI executes a pinned private reusable workflow.

#### Scenario: Agent reads platform release guidance

- **WHEN** a downstream repository is generated or updated
- **THEN** its guidance describes reviewed Copier updates as the CI propagation mechanism and identifies `platform_ci_ref` only as legacy compatibility metadata

### Requirement: Downstream platform CI respects harness ownership

Generated Dev Platform CI SHALL separate platform-owned hygiene from project-owned product verification according to `harness_mode`.

#### Scenario: Platform owns the project harness

- **GIVEN** `harness_mode=platform`
- **WHEN** generated Dev Platform CI runs
- **THEN** it MAY execute selected/full checks through the platform-managed selector contract in addition to platform/OpenSpec hygiene according to the triggering event

#### Scenario: Project owns the project harness

- **GIVEN** `harness_mode=project`
- **WHEN** generated Dev Platform CI runs
- **THEN** it executes only dependency-independent platform/OpenSpec hygiene owned by Dev Platform
- **AND** it does not invoke product checks through the repository-owned selector
- **AND** it does not assume the repository-owned selector accepts platform-specific CLI flags

### Requirement: Existing project CI remains authoritative for product dependency setup

Adoption of a project-owned harness SHALL preserve the repository's existing CI as the authority for installing application dependencies and executing product-specific tests unless an explicit reviewed project change replaces that CI.

#### Scenario: Mature project already has dependency-aware CI

- **GIVEN** a repository CI creates its Python environment, installs backend dependencies, installs frontend dependencies and performs project-specific tests
- **WHEN** Dev Platform is adopted with `harness_mode=project`
- **THEN** generated platform CI does not duplicate those steps merely to satisfy platform adoption
- **AND** the existing CI remains available on the adoption PR

### Requirement: Platform hygiene remains enforced for project-owned harnesses

Choosing `harness_mode=project` SHALL NOT disable shared Dev Platform/OpenSpec health checks that do not require application dependency knowledge.

#### Scenario: Project-owned harness has stale completed OpenSpec change

- **GIVEN** a downstream project uses `harness_mode=project`
- **WHEN** platform lifecycle hygiene detects an active OpenSpec change whose tasks are all complete but which is not archived
- **THEN** generated platform CI fails according to the shared completion-lifecycle contract

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

### Requirement: Superseded validation runs are cancelled

Ordinary CI validation workflows SHALL use concurrency grouping that keeps the newest run for the same PR/ref and cancels an older in-progress validation run when a newer commit supersedes it.

#### Scenario: New commit arrives while PR CI is still running

- **GIVEN** a validation run for a pull request is in progress
- **WHEN** a newer commit to the same pull request starts a new validation run
- **THEN** the older run is cancelled
- **AND** the newest run remains authoritative

#### Scenario: Release side-effect workflow runs

- **WHEN** a release publication or managed rollout workflow starts
- **THEN** it is not made cancel-in-progress merely by this cost-optimization policy

### Requirement: Central platform CI does not duplicate profile-independent work

The central `dev-platform` CI SHALL retain coverage for every supported workflow profile while avoiding repeated execution of shared setup and profile-independent validation solely because multiple profiles are exercised.

#### Scenario: Platform PR runs factory coverage

- **WHEN** central Platform CI validates a pull request
- **THEN** shared script compilation, managed-project validation, unit tests, OpenSpec validation and common dependency setup execute once per workflow run
- **AND** light, standard and multi-agent render/update behavior is still exercised

### Requirement: Cost optimization does not weaken repository verification ownership

Generated platform CI SHALL continue to respect `harness_mode` and SHALL NOT replace project-owned application CI or local required checks merely to reduce GitHub Actions usage.

#### Scenario: Project-owned harness is optimized

- **GIVEN** `harness_mode=project`
- **WHEN** the generated Dev Platform workflow is updated
- **THEN** only platform/OpenSpec hygiene behavior owned by Dev Platform is changed
- **AND** the repository's product/application workflow remains project-owned
- **AND** any cost optimization of that product workflow requires a separate reviewed project change

### Requirement: Local-heavy / cloud-final verification is documented

Platform operating guidance SHALL describe local agent verification as the place for required selected/full checks before publish, pull-request cloud CI as the clean-environment merge gate, direct main cloud CI as a lightweight platform/OpenSpec health signal, and manual dispatch as the optional full cloud diagnostic path.

#### Scenario: Agent prepares a direct-published change

- **WHEN** the agent follows the normal direct lifecycle
- **THEN** it does not skip required local verification
- **AND** the published main state receives lightweight platform/OpenSpec validation without repeating the full project check set

#### Scenario: Maintainer wants a cloud full run

- **WHEN** a clean cloud rerun of the configured full platform-managed checks is intentionally needed
- **THEN** the maintainer can use manual workflow dispatch rather than relying on every direct main push to run the full suite

### Requirement: Platform validation subprocesses are isolated from parent repository overrides

Platform-owned validation/check commands SHALL NOT inherit parent Git environment overrides that bind the subprocess to a specific repository, worktree, index, common directory or object store unless that exact validation operation explicitly requires and scopes the override.

#### Scenario: Validation command creates an independent temporary repository

- **GIVEN** the parent lifecycle process contains repository-scoped Git environment overrides
- **WHEN** a selected platform validation command creates or operates on a temporary Git repository
- **THEN** the temporary repository uses its own worktree/index/object-store context
- **AND** its Git objects are not redirected into the parent repository solely because of inherited environment variables

#### Scenario: Validation command needs ordinary process environment

- **WHEN** a platform validation command runs under normal conditions
- **THEN** unrelated environment such as `PATH`, active tool/runtime environment and other required non-repository process context remains available
- **AND** isolation does not become a blanket environment reset

#### Scenario: One Git operation requires a scoped override

- **GIVEN** a specific platform-owned Git operation requires a repository-scoped environment override
- **WHEN** that operation completes
- **THEN** the override is limited to that operation
- **AND** subsequent validation subprocesses do not inherit it by default

### Requirement: Concurrent validation tests do not depend on fragile startup timing

Platform-owned concurrency/lock tests SHALL synchronize on explicit readiness where process startup order is part of the assertion and SHALL use bounded deadlines tolerant of normal concurrent test-group scheduling. The test contract SHALL continue to fail a genuinely hung subprocess and SHALL NOT rely on automatic retry to hide timing flakiness.

#### Scenario: Concurrent suite delays a helper process

- **GIVEN** multiple supported test groups run concurrently under normal host contention
- **WHEN** a lock-holder or capability-probe helper starts more slowly than in isolated execution
- **THEN** the test waits for its explicit supported readiness condition within a bounded deadline
- **AND** does not change the semantic test result solely because scheduler latency exceeded an unrealistically short startup assumption

#### Scenario: Helper genuinely hangs

- **WHEN** the controlled helper never reaches its required readiness/completion condition
- **THEN** the bounded deadline expires
- **AND** the test fails with a useful diagnostic
- **AND** no retry loop converts the hang into success
