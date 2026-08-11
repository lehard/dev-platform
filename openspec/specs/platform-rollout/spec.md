# Platform Rollout Specification

## Purpose

Platform rollout SHALL keep shared workflow releases and downstream upgrades reproducible, reviewable and recoverable across new and existing repositories.
## Requirements
### Requirement: Copier upgrades are tested, not assumed

Before a platform release is published, CI SHALL exercise a real Copier update from the latest stable platform template or an explicit bootstrap baseline to the candidate template. The smoke project SHALL contain project-owned modifications before update and SHALL fail validation if those modifications are lost or unresolved conflicts remain.

#### Scenario: Candidate platform is tested against existing project state

- **WHEN** platform CI evaluates an update from the stable baseline
- **THEN** it performs a real Copier update on a smoke project containing project-owned customization and verifies that customization survives without unresolved conflicts

### Requirement: Unresolved template-update conflicts block completion

Generated project doctor SHALL report a blocking failure when a non-ignored `*.rej` file exists or Git reports leftover conflict markers in staged or working-tree changes.

#### Scenario: Copier leaves a rejected patch

- **WHEN** a generated repository contains a non-ignored `*.rej` file after an update
- **THEN** platform doctor fails until the conflict is resolved

### Requirement: Platform tool versions are deliberate

The Project Factory SHALL declare a minimum Copier version and the platform SHALL record the version it was tested with. Platform CI SHALL use the exact tested Copier version rather than a floating compatible range.

#### Scenario: Platform CI installs Copier

- **WHEN** platform validation runs
- **THEN** CI installs the exact tested Copier version recorded by platform policy

### Requirement: GitHub Actions references are immutable

GitHub-owned Actions used by platform-managed workflows SHALL use full commit SHAs rather than mutable major tags.

#### Scenario: Platform-managed workflow references an Action

- **WHEN** a workflow uses an `actions/*` dependency
- **THEN** the dependency reference is a full immutable commit SHA

### Requirement: Platform releases use stable immutable versions

Published Project Factory versions SHALL use stable SemVer Git tags. A published version tag SHALL NOT be moved or reused, and automated publication SHALL fail closed when an existing tag points elsewhere.

#### Scenario: Existing release tag points to another commit

- **WHEN** release automation finds that the requested SemVer tag already exists at a different commit
- **THEN** publication fails instead of moving the tag

### Requirement: Downstream upgrades remain reviewed

Platform-managed files, including self-contained CI, SHALL propagate to downstream repositories through reviewed Copier updates rather than mutable remote execution. Downstream update PRs SHALL NOT auto-merge by default.

#### Scenario: Platform version changes downstream behavior

- **WHEN** an existing managed repository adopts a newer platform release
- **THEN** the platform-managed file changes arrive as a reviewable Copier diff or PR before they affect the project

### Requirement: Managed repositories are explicitly allowlisted and known projects are classified

The platform SHALL keep an explicit central registry of known downstream project repositories and SHALL automatically mutate only entries whose state is `managed`. Known repositories intentionally outside adoption/rollout SHALL be recorded as `excluded` rather than silently omitted.

#### Scenario: Candidate repository is present in the registry

- **GIVEN** a repository is recorded as `candidate`
- **WHEN** automated rollout builds its project matrix
- **THEN** that repository is excluded from all cross-repository write operations

#### Scenario: Excluded repository is present in the registry

- **GIVEN** a repository is recorded as `excluded`
- **WHEN** automated rollout builds its project matrix
- **THEN** that repository is excluded from all cross-repository write operations and its registry note explains the intentional exclusion

#### Scenario: Managed repository is present in the registry

- **GIVEN** a repository is recorded as `managed`
- **WHEN** a target platform release is rolled out
- **THEN** the repository is included in the rollout matrix using its configured default branch

### Requirement: Successful releases dispatch reviewed downstream rollout

After publishing an immutable platform version, the central release workflow SHALL dispatch the managed-project rollout for that exact SemVer tag. Rollout SHALL also support an explicit manual retry path and SHALL reject versions that are not actually published platform releases.

#### Scenario: New platform version is published

- **WHEN** the release workflow successfully creates or confirms `vX.Y.Z` at the release commit
- **THEN** it dispatches the rollout workflow with target version `vX.Y.Z`

#### Scenario: Manual retry names an unpublished version

- **WHEN** a manually dispatched rollout requests a syntactically valid tag that is not a published immutable platform release
- **THEN** rollout fails before creating any downstream write token or mutation

### Requirement: Cross-repository rollout uses least-privilege GitHub App authentication

Automated rollout SHALL use a dedicated GitHub App rather than relying on the source repository `GITHUB_TOKEN` or a broadly reusable personal token. Each project job SHALL use separately down-scoped short-lived credentials for the private platform source and downstream target.

#### Scenario: Rollout job needs private template access

- **WHEN** Copier fetches the private `lehard/dev-platform` source
- **THEN** it uses a token scoped only to `dev-platform` with Contents read permission

#### Scenario: Rollout job writes one managed repository

- **WHEN** the job checks out, pushes or opens a PR in the downstream repository
- **THEN** it uses a different token scoped only to that repository with Contents write, Pull requests write, and Workflows write permissions so platform-managed `.github/workflows/*` changes can be delivered

### Requirement: Managed upgrades target exact immutable platform versions

Automated rollout SHALL run Copier against the exact published SemVer tag supplied by release orchestration and SHALL never update a downstream project from mutable `main`.

#### Scenario: Project is behind the target version

- **GIVEN** `.copier-answers.yml` identifies `lehard/dev-platform` and records an older platform tag
- **WHEN** rollout targets `vX.Y.Z`
- **THEN** Copier updates the project with `--vcs-ref vX.Y.Z` before validation and PR creation

### Requirement: Rollout fails closed on project ambiguity or conflicts

Automatic rollout SHALL leave the downstream default branch untouched when Copier metadata is missing or unexpected, a downgrade is requested, an unresolved Copier/Git conflict remains, project validation fails, or an unexpected rollout branch collision exists.

#### Scenario: Copier produces a rejected patch

- **WHEN** an exact-version update leaves any non-ignored `*.rej` file
- **THEN** the rollout job fails and does not push or merge changes to the downstream default branch

#### Scenario: An update PR for the same target already exists

- **WHEN** rollout finds the deterministic target branch already associated with an open pull request
- **THEN** it reports the rollout as already pending without force-pushing or opening a duplicate PR

### Requirement: Automatic rollout stops at a reviewable pull request

A clean managed-project update SHALL be committed to a deterministic automation branch and opened as a normal downstream pull request. The rollout system SHALL NOT auto-merge that pull request by default.

#### Scenario: Copier update and project checks succeed

- **WHEN** the managed project has a clean exact-version update
- **THEN** the platform opens a PR against the configured default branch and leaves merge to downstream review/CI policy

### Requirement: Existing project-owned files survive platform rollout

The Project Factory SHALL create default project-owned control files for fresh repositories but SHALL preserve existing downstream content for files explicitly classified as project-owned during Copier updates.

#### Scenario: Existing managed project customized its project contract

- **GIVEN** a managed project already contains a customized `.gitignore`, `AGENTS.md`, `README.md`, `dev-platform/checks.toml`, or `openspec/config.yaml`
- **WHEN** Copier updates the project to a newer platform release
- **THEN** those existing files are preserved rather than patched or replaced by the platform template

#### Scenario: Platform needs clone-local generated-agent ignores

- **GIVEN** a mature repository owns its `.gitignore`
- **WHEN** local readiness regenerates machine-local Claude/Codex integrations
- **THEN** Dev Platform records its generated integration patterns in the clone-local Git exclude file rather than editing the project's tracked `.gitignore`

### Requirement: Platform version metadata stays coherent

After Project Factory rendering or managed Copier update, `.dev-platform.toml` `platform_version` SHALL match the stable SemVer recorded by `.copier-answers.yml` `_commit` without the leading `v`.

#### Scenario: Managed rollout advances Copier version

- **WHEN** rollout updates `_commit` from `v1.0.2` to `v1.2.1`
- **THEN** `.dev-platform.toml` records `platform_version = "1.2.1"` before validation and commit

#### Scenario: Version metadata remains inconsistent

- **WHEN** rollout finishes Copier update but the two version records differ
- **THEN** rollout fails before pushing a branch or opening a PR

### Requirement: Project-specific doctor requirements are configuration data

Projects SHALL be able to declare additional required repository files in `.dev-platform.toml` without modifying the centrally managed `platform_doctor.py` implementation.

#### Scenario: Project requires a compatibility helper

- **GIVEN** `.dev-platform.toml` lists a project-specific required file
- **WHEN** `platform_doctor.py` runs
- **THEN** it verifies that file in addition to the shared platform requirements

### Requirement: Machine-owned Copier metadata is normalized before strict diff validation

Managed rollout SHALL normalize only `.copier-answers.yml` machine-owned trailing newline formatting after Copier update and before strict Git whitespace validation. Other downstream files SHALL remain subject to unmodified strict validation.

#### Scenario: Copier emits an extra blank line at EOF

- **WHEN** an exact-version Copier update leaves multiple trailing newlines in `.copier-answers.yml`
- **THEN** rollout rewrites that metadata file to exactly one terminating newline before running `git diff --check`

#### Scenario: Another project file contains a whitespace error

- **WHEN** the downstream update contains a whitespace error outside the explicit Copier metadata normalization
- **THEN** strict `git diff --check` still blocks rollout before push or PR creation

### Requirement: Managed rollout isolates historical Copier tasks

Managed exact-version Copier update and guarded recopy SHALL skip embedded template tasks from historical source snapshots. After a conflict-free render, rollout SHALL execute the candidate version's platform bootstrap exactly once before project validation.

#### Scenario: Historical template has an obsolete bootstrap task

- **GIVEN** a managed project was created from an older platform release whose Copier task is incompatible with the available OpenSpec CLI
- **WHEN** managed rollout updates it to a newer exact platform version
- **THEN** historical Copier tasks are not executed
- **AND** the newly rendered candidate bootstrap synchronizes platform-owned metadata before validation

#### Scenario: Copier update has unresolved conflicts

- **WHEN** exact-version Copier update leaves an unresolved rejection or otherwise fails
- **THEN** rollout fails closed
- **AND** it does not execute the candidate bootstrap or push a downstream branch

### Requirement: Managed rollout validation respects harness ownership

Central managed rollout SHALL execute only validation behavior owned by Dev Platform and SHALL NOT assume a project-owned selector CLI contract.

#### Scenario: Platform owns downstream harness

- **GIVEN** a managed repository records `harness_mode=platform`
- **WHEN** rollout validates a conflict-free exact-version update
- **THEN** it runs platform doctor
- **AND** it invokes the rendered platform-managed `scripts/select_checks.py` with the platform rollout execution contract

#### Scenario: Project owns downstream harness

- **GIVEN** a managed repository records `harness_mode=project`
- **WHEN** rollout validates a conflict-free exact-version update
- **THEN** it runs platform-owned diff and doctor validation
- **AND** it does not invoke the repository-owned `scripts/select_checks.py`
- **AND** product/application verification is left to the downstream pull request CI before merge

#### Scenario: Project-owned selector has a different CLI

- **GIVEN** `harness_mode=project`
- **AND** the repository-owned selector does not accept Dev Platform-specific execution flags
- **WHEN** managed rollout prepares an update
- **THEN** rollout does not fail merely because that project-owned CLI differs from the platform selector contract

### Requirement: Managed rollout emits one machine-readable terminal diagnostic

For every failed managed-project rollout attempt, the workflow SHALL emit one canonical machine-readable diagnostic envelope derived from structured rollout state. The envelope SHALL be available without requiring arbitrary full-log scraping and SHALL NOT alter rollout safety or outcome.

The envelope SHALL include at least: schema version, terminal status, target project, target immutable release, failure stage, failure category, stable reason, exit code, selected command when known, same-input retry advisory, and structured evidence already known to rollout such as conflict paths. It SHALL exclude credentials, unrestricted environment dumps, tokens, and raw logs.

#### Scenario: Safety guard blocks rollout
- **WHEN** a managed safety invariant fails deterministically
- **THEN** the diagnostic category is `safety_guard` or another more specific stable safety category
- **AND** the stage identifies where the guard failed
- **AND** the reason contains the canonical managed-rollout blocker
- **AND** `retry_same_inputs` is `pointless` unless the platform can prove the failure may be transient
- **AND** the workflow remains failed

#### Scenario: Selected downstream check fails
- **GIVEN** rollout has emitted `DEV_PLATFORM_CHECK_COMMAND: <command>`
- **WHEN** that selected command exits non-zero
- **THEN** the diagnostic stage is `downstream_check`
- **AND** the command field contains exactly the reserved selected command
- **AND** arbitrary compiler, diff, or application output SHALL NOT replace the command
- **AND** the exit code is preserved

#### Scenario: Runtime/environment mismatch is known
- **WHEN** rollout can identify that a platform-owned runtime baseline differs from the required managed validation baseline
- **THEN** the diagnostic category is `runtime_environment`
- **AND** the reason identifies the required/observed baseline without exposing secrets
- **AND** a same-input retry SHALL NOT be labeled `safe` when no environment input can change between attempts

#### Scenario: Failure is not classifiable
- **WHEN** rollout fails without a known blocker, structured conflict, or selected-check marker
- **THEN** the diagnostic category is `unknown`
- **AND** the stage is the narrowest known stage or `unknown`
- **AND** `retry_same_inputs` is `unknown`
- **AND** the workflow does not infer a cause from arbitrary log text

#### Scenario: Diagnostic is published for agents and humans
- **WHEN** a rollout attempt reaches a terminal failed state
- **THEN** the canonical diagnostic JSON is written to a predictable path such as `rollout-diagnostic.json`
- **AND** a compact rendering is appended to the GitHub Actions step summary
- **AND** the workflow attempts to upload a predictably named diagnostic artifact
- **AND** the annotation, summary, and artifact represent the same canonical terminal failure

#### Scenario: Diagnostic artifact upload fails
- **GIVEN** the original rollout is already failed
- **WHEN** diagnostic artifact upload or summary presentation fails
- **THEN** that presentation failure SHALL NOT replace the original blocker
- **AND** SHALL NOT convert the rollout to success
- **AND** the workflow SHALL preserve the original non-zero result

#### Scenario: Consumer reads a future diagnostic schema
- **GIVEN** a consumer understands schema version 1
- **WHEN** later platform versions add optional diagnostic fields
- **THEN** the existing stable fields remain interpretable
- **AND** consumers can reject or explicitly handle an unsupported schema version rather than relying on exact JSON byte shape

### Requirement: Repeated managed rollout failures against the same project are surfaced to a human

The platform SHALL maintain a durable, cross-run record of consecutive terminal `blocked` managed-rollout attempts per project, independent of any single ephemeral workflow run. When that count reaches a fixed threshold, the platform SHALL escalate beyond the existing per-attempt annotation into a distinct, labeled, human-discoverable alert. The record SHALL reset the next time that project's rollout preparation succeeds.

This tracking layer SHALL be strictly additive: a failure inside it SHALL NOT change rollout's own pass/fail result for the current attempt, SHALL NOT retry, push, merge, or affect PR-creation, and SHALL NOT modify any existing safety guard, recovery eligibility, or credential scope.

#### Scenario: First failure against a project opens a tracking record
- **GIVEN** a project has no open rollout-failure tracking record
- **WHEN** its managed rollout preparation reaches a terminal blocked state
- **THEN** a new durable tracking record is created for that exact project
- **AND** its consecutive-failure count is `1`
- **AND** no alert-threshold escalation occurs yet

#### Scenario: Repeated failures increment the same tracking record
- **GIVEN** a project already has an open rollout-failure tracking record with a readable prior state
- **WHEN** its managed rollout preparation reaches another terminal blocked state
- **THEN** the existing record's consecutive-failure count increments by exactly one
- **AND** the record retains which release first failed and is updated with the most recent failure's category and reason
- **AND** no second tracking record is created for the same project

#### Scenario: Consecutive failures cross the alert threshold
- **GIVEN** a project's tracking record reaches a consecutive-failure count of 3
- **WHEN** the platform updates that record
- **THEN** the record is labeled as an outstanding alert
- **AND** a distinct workflow warning annotation identifies the project, the streak length, and the tracking record
- **AND** the underlying rollout attempt remains in its original failed state

#### Scenario: A successful rollout resets the streak
- **GIVEN** a project has an open rollout-failure tracking record
- **WHEN** that project's managed rollout preparation next succeeds
- **THEN** the tracking record is closed with a note of how many consecutive failures preceded the resolution and at which release it resolved
- **AND** the record is not deleted, remaining as a historical entry
- **AND** a subsequent new failure against that project opens a fresh record starting at a consecutive-failure count of `1`

#### Scenario: A successful rollout with no prior open record is a no-op
- **GIVEN** a project has no open rollout-failure tracking record
- **WHEN** that project's managed rollout preparation succeeds
- **THEN** the platform makes no tracking-record change

#### Scenario: Prior tracking state cannot be read
- **GIVEN** a project has an open rollout-failure tracking record whose state cannot be parsed
- **WHEN** another terminal blocked attempt occurs against that project
- **THEN** the platform treats the streak as already at or above the alert threshold rather than resetting it to a lower count
- **AND** escalates as in the threshold-crossing scenario
- **AND** does not silently discard the unreadable prior record

#### Scenario: The tracking layer itself fails
- **GIVEN** a rollout attempt has already reached a terminal status
- **WHEN** creating, reading, or updating the durable tracking record fails for any reason
- **THEN** that failure is surfaced as a visible warning in the run's own output
- **AND** it SHALL NOT change the rollout attempt's already-determined success or failure result
- **AND** it SHALL NOT retry, push, merge, or otherwise act beyond the tracking record itself

### Requirement: Older managed rollout pull requests are superseded deterministically

Managed rollout SHALL prevent accumulated older platform-update PRs from remaining actionable after a newer authoritative platform target is safely available or the downstream default branch has already advanced beyond them. Automatic supersession SHALL apply only to verifiably managed rollout PRs in repositories currently allowlisted as `managed`.

#### Scenario: Newer rollout PR is successfully prepared

- **GIVEN** managed repository R has open eligible rollout PRs for versions lower than target `vN`
- **WHEN** rollout successfully creates or reuses the validated eligible rollout PR for `vN`
- **THEN** the platform closes the lower-version eligible rollout PRs as superseded by `vN`
- **AND** records which newer target/PR superseded them
- **AND** does not force-push or merge any rollout PR

#### Scenario: Newer rollout preparation fails before replacement PR exists

- **GIVEN** an older eligible rollout PR remains open
- **WHEN** preparation of newer target `vN` fails before a validated `vN` PR exists
- **THEN** the platform leaves the older pending rollout PR open
- **AND** does not remove the last reviewable update path merely because a newer attempt failed

#### Scenario: Downstream default branch already advanced

- **GIVEN** the downstream default branch records platform version `vB`
- **AND** an open eligible rollout PR targets `vA` where `vA <= vB`
- **WHEN** rollout maintenance reconciles stale PR state
- **THEN** the PR is classified stale and may be closed as superseded by the already-adopted base state

#### Scenario: Open rollout PR targets a newer version than the current request

- **GIVEN** an eligible open rollout PR targets `vM`
- **AND** the current rollout request targets `vN` where `vM > vN`
- **WHEN** supersession logic evaluates the repository
- **THEN** it SHALL NOT close or mutate the newer `vM` PR
- **AND** the older `vN` request follows existing downgrade/stale fail-closed behavior

#### Scenario: PR resembles rollout by title only

- **WHEN** an open PR title/body resembles a platform update but its head/ownership/base contract does not prove it is a managed rollout PR
- **THEN** automatic supersession SHALL leave it untouched

### Requirement: Rollout PR identity is derived from reserved branch/version and trusted automation context

Automatic rollout cleanup SHALL identify eligible rollout PRs from the exact reserved branch form, stable SemVer target, configured base branch, and expected rollout automation context. Human-readable title text SHALL NOT be the sole identity signal.

#### Scenario: Candidate or excluded repository contains a rollout-like PR

- **GIVEN** a repository is not currently `managed` in `managed-projects.json`
- **WHEN** stale-rollout maintenance runs
- **THEN** the platform SHALL NOT mutate that repository or its PRs

#### Scenario: Unrelated dev-platform branch is open

- **WHEN** a PR head does not match exact `dev-platform/rollout-vMAJOR.MINOR.PATCH`
- **THEN** it is outside automatic rollout supersession

### Requirement: Superseded rollout branch cleanup is post-close and non-destructive

Remote branch deletion for a superseded rollout SHALL occur only after the corresponding PR is confirmed closed. Branch cleanup SHALL never use force-push and SHALL NOT redefine successful PR supersession as failure if only branch deletion fails.

#### Scenario: Superseded PR closes but remote branch deletion fails

- **WHEN** the stale rollout PR is confirmed closed
- **AND** remote rollout-branch deletion fails
- **THEN** the PR remains correctly superseded/closed
- **AND** the cleanup failure is surfaced as a warning with the exact repository/branch
- **AND** no unrelated branch is modified

### Requirement: Existing stale rollout debt can be reconciled without creating a release

The platform SHALL provide an explicit maintenance mode for reporting and reconciling stale eligible rollout PRs across the current managed registry using the same identity and SemVer rules as normal rollout.

#### Scenario: Maintenance runs in dry-run mode

- **WHEN** an operator/agent invokes stale-rollout maintenance without mutation
- **THEN** it reports the exact managed repository/PR/version decisions it would apply
- **AND** performs no cross-repository write

#### Scenario: Maintenance applies cleanup

- **WHEN** reviewed maintenance mutation is invoked
- **THEN** it closes only PRs proven stale by committed downstream version or a safely available newer rollout target
- **AND** never mutates candidate/excluded repositories

