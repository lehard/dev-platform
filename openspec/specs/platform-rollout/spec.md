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

Automatic rollout SHALL leave the downstream default branch untouched when Copier metadata is missing or unexpected, a downgrade is requested, an unresolved Copier/Git conflict remains, project validation fails, or an unexpected rollout branch collision exists. Detection of an already-pending rollout PR SHALL be performed by a testable, platform-owned helper that filters structured GitHub API JSON by the exact reserved branch, configured base branch, and expected rollout automation identity -- not by ad hoc shell/`jq` argument combinations, human-readable `gh` command output parsing, or PR title/body text matching.

#### Scenario: Copier produces a rejected patch

- **WHEN** an exact-version update leaves any non-ignored `*.rej` file
- **THEN** the rollout job fails and does not push or merge changes to the downstream default branch

#### Scenario: An update PR for the same target already exists

- **WHEN** rollout finds the deterministic target branch already associated with an open pull request
- **THEN** it reports the rollout as already pending without force-pushing or opening a duplicate PR
- **AND** that determination is made by the structured pending-PR helper, reusing the same eligibility rules (exact branch, base, and automation identity) already used for rollout PR supersession

#### Scenario: Pending-PR detection uses only supported CLI/API surface

- **WHEN** the rollout job checks for an already-pending PR
- **THEN** it SHALL NOT pass unsupported flags to the `gh` CLI
- **AND** a regression test SHALL assert the workflow does not combine `--jq` with a separate `--arg` flag on any `gh` invocation

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

The platform SHALL maintain a durable, cross-run record of consecutive terminal `blocked` managed-rollout attempts per project, independent of any single ephemeral workflow run. When that count reaches a fixed threshold, the platform SHALL escalate beyond the existing per-attempt annotation into a distinct, labeled, human-discoverable alert. The record SHALL reset the next time that project's rollout preparation succeeds. Before either the tracking label or the alert label is referenced, the platform SHALL idempotently ensure both exist on the tracker repository, using only the least-privilege permission already granted to the rollout job.

This tracking layer SHALL be strictly additive: a failure inside it, including a failure to bootstrap its own labels, SHALL NOT change rollout's own pass/fail result for the current attempt, SHALL NOT retry, push, merge, or affect PR-creation, and SHALL NOT modify any existing safety guard, recovery eligibility, or credential scope.

#### Scenario: First failure against a project opens a tracking record
- **GIVEN** a project has no open rollout-failure tracking record
- **WHEN** its managed rollout preparation reaches a terminal blocked state
- **THEN** a new durable tracking record is created for that exact project
- **AND** its consecutive-failure count is `1`
- **AND** no alert-threshold escalation occurs yet

#### Scenario: Tracking label does not yet exist on the tracker repository

- **GIVEN** the tracker repository does not yet have the `rollout-failure-streak` or `rollout-alert` label
- **WHEN** the tracking layer needs to create or label a tracking issue
- **THEN** the missing label is created automatically before it is referenced
- **AND** no manual repository UI setup is required

#### Scenario: Label bootstrap is idempotent

- **WHEN** label bootstrap runs against a tracker repository that already has the label
- **THEN** it succeeds without error and does not create a duplicate label

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
- **WHEN** creating, reading, or updating the durable tracking record fails for any reason, including label bootstrap
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

### Requirement: Platform-owned rollout helpers are invoked from their actual checkout path

Every platform-owned Python helper invoked from a workflow job that checks out platform tooling into a non-root path (for example `platform/` alongside a separate downstream `target/` checkout) SHALL be invoked using that actual path. A regression test SHALL verify, for each such job, that every reference to a known platform-owned root-level script resolves under the job's real checkout layout rather than relying solely on a passing workflow run.

#### Scenario: Rollout job checks out platform tooling into a non-root path

- **GIVEN** the `rollout` job in `.github/workflows/rollout.yml` checks out immutable platform tooling into `platform/` and the downstream project into `target/`
- **WHEN** any step in that job invokes a platform-owned root-level script
- **THEN** the invocation SHALL use the `platform/`-prefixed path
- **AND** a regression test SHALL fail if a bare unprefixed path is introduced

#### Scenario: A different workflow uses a single root checkout

- **GIVEN** a workflow job checks out the platform repository directly at the job's working directory with no separate `platform/` path
- **WHEN** that job invokes a platform-owned root-level script
- **THEN** the bare root-relative path is correct for that job's layout
- **AND** the path-correctness regression test SHALL evaluate each job against its own actual checkout layout, not a single assumed layout

### Requirement: Historical Copier replay may recover only proven platform-owned state

Managed rollout MAY use guarded Copier recopy to recover a smart-update conflict on a platform-owned harness only when every conflicted path is proven safe from immutable pre-update state. A conflict is safe when either (a) an explicitly reclaimed migration path already matches the exact target immutable template, or (b) the committed downstream path exactly matches the same path in the immutable platform template version recorded by `.copier-answers.yml`. Missing/missing SHALL count as baseline equivalence. Any currently divergent or otherwise unproven path SHALL remain fail-closed.

#### Scenario: Platform-owned file already equals target but historical replay conflicts
- **GIVEN** a managed repository uses `harness_mode=platform`
- **AND** `scripts/project_publish.py` exactly matches the target immutable platform template before update
- **WHEN** `copier update` replays historical downstream edits and emits `scripts/project_publish.py.rej`
- **THEN** managed rollout may reset the ephemeral rollout branch and use guarded recopy
- **AND** it verifies protected snapshots and platform configuration after recopy
- **AND** it can continue to normal validation and reviewed PR creation

#### Scenario: Unmodified old-platform file conflicts during historical replay
- **GIVEN** a managed repository uses `harness_mode=platform`
- **AND** a conflicted downstream path in committed `HEAD` exactly equals the same path in the immutable platform version recorded by `.copier-answers.yml`
- **WHEN** smart Copier update emits a rejection for that path
- **THEN** the path is eligible for guarded recopy without adding a repository-specific allowlist entry
- **AND** after recopy the path SHALL match the new target template state

#### Scenario: Path is absent in both downstream and recorded old template
- **GIVEN** a managed repository uses `harness_mode=platform`
- **AND** a rejection names a path absent from both committed downstream `HEAD` and the recorded old consumer template
- **THEN** that missing/missing state is treated as baseline-equivalent
- **AND** guarded recopy MAY recover it if every other conflict is also proven safe

#### Scenario: Reclaimed path still contains downstream divergence
- **GIVEN** a managed repository uses `harness_mode=platform`
- **AND** an allowlisted reclaimed path does not match the target immutable template before update
- **AND** it also does not match its recorded old-template state
- **WHEN** Copier reports a conflict on that path
- **THEN** managed rollout fails closed
- **AND** it does not use recopy, push a rollout branch, or open a PR

#### Scenario: Platform-mode conflict contains real downstream customization
- **GIVEN** a managed repository uses `harness_mode=platform`
- **WHEN** any conflicted path differs from both its recorded old-template state and any applicable reclaimed target state
- **THEN** managed rollout fails closed without recopy

#### Scenario: Baseline proof is computed after Copier mutates the worktree
- **WHEN** rollout classifies conflicts after smart update has emitted `.rej` files
- **THEN** downstream equivalence SHALL be derived from committed `HEAD` rather than current worktree bytes
- **AND** the old side SHALL be read from the exact immutable tag recorded by `.copier-answers.yml`

### Requirement: Managed rollout failures remain fail-closed and diagnosable

The managed rollout workflow SHALL preserve a non-zero rollout preparation result and SHALL surface its blocking reason in GitHub Actions when preparation fails. The selected-check helper SHALL emit a reserved command marker before each selected downstream command so compiler, diff, or application output cannot be mistaken for the command being executed. Diagnostic handling SHALL NOT push the rollout branch, open a pull request, skip a guard, or convert a failed rollout into success.

#### Scenario: Prepare fails on a safety guard
- **WHEN** `rollout_project.py` exits non-zero because a managed safety invariant fails
- **THEN** the workflow records the command output
- **AND** emits a readable GitHub Actions error annotation containing the final `Managed rollout: BLOCKED:` reason
- **AND** remains failed
- **AND** branch push and PR creation remain skipped

#### Scenario: Downstream validation command fails
- **GIVEN** rollout safely reached downstream platform/product validation
- **WHEN** a checked selected command exits non-zero without a `Managed rollout: BLOCKED:` marker
- **THEN** `select_checks.py` has emitted `DEV_PLATFORM_CHECK_COMMAND: <command>` immediately before that command
- **AND** the workflow reports the last such reserved marker with the exit code
- **AND** arbitrary source/compiler lines beginning with `+` or containing `Error:` SHALL NOT replace that blocker
- **AND** the failed command remains a blocking result rather than becoming recoverable

#### Scenario: Failure occurs outside selected checks
- **WHEN** rollout preparation exits non-zero before any stable blocker or selected-check marker exists
- **THEN** the workflow reports the preparation exit code generically
- **AND** does not guess a command from arbitrary subprocess output
- **AND** the rollout remains failed

### Requirement: Managed rollout validates with the platform CI runtime baseline

Managed rollout SHALL provision the same platform-owned base runtime versions used by the generated downstream Dev Platform gate before executing selected downstream checks. Runtime parity SHALL be tested so a platform release cannot silently validate a consumer under a different Node baseline than the generated PR gate.

#### Scenario: Rollout executes JavaScript checks
- **GIVEN** the generated Dev Platform workflow pins Node `20.19.0`
- **WHEN** managed rollout reaches selected downstream checks
- **THEN** the rollout job has provisioned Node `20.19.0` before those checks
- **AND** the downstream build is evaluated under the same platform-owned Node baseline as its PR gate

#### Scenario: Platform changes the generated Node baseline
- **WHEN** a later platform release changes the Node version in the generated Dev Platform workflow
- **THEN** validation fails unless managed rollout is updated to the same version in that release

### Requirement: Rollout service branches do not weaken interactive task branch rules

Managed rollout SHALL use only the reserved service-branch form `dev-platform/rollout-vX.Y.Z` generated from an exact SemVer release. This automation branch SHALL be validated through rollout-specific validation and SHALL NOT cause interactive task lifecycle rules to accept arbitrary `dev-platform/*` branches in place of `agent/<task>`.

#### Scenario: Rollout validates an automation branch
- **GIVEN** managed rollout created `dev-platform/rollout-v1.2.3`
- **WHEN** downstream validation runs before push
- **THEN** rollout-specific platform validation and selected project checks MAY run on that service branch
- **AND** no interactive `agent/<task>` branch precondition is required
- **AND** ordinary task creation/publication continues to use its existing agent branch contract

### Requirement: Pending rollout identity is reusable by downstream task preflight

The platform SHALL expose one structured eligibility contract for determining whether an open downstream PR is a platform-owned rollout. Central rollout automation and downstream pre-task reconciliation SHALL use the same ownership semantics based on configured repository/base, reserved rollout branch/version contract, and expected automation identity. PR title or body text SHALL NOT establish ownership.

#### Scenario: Pre-task reconciliation sees an old and a new rollout PR

- **GIVEN** multiple historical rollout records exist for the repository
- **WHEN** pre-task reconciliation chooses a candidate for automatic adoption
- **THEN** only the newest authoritative eligible pending rollout may be selected
- **AND** an older superseded rollout is not merged

#### Scenario: Similar-looking PR is not owned by rollout automation

- **WHEN** an open PR has a rollout-like title or body but does not satisfy the structured branch/base/automation identity contract
- **THEN** pre-task reconciliation does not treat it as an automatically adoptable platform rollout

### Requirement: Automatic release rollout remains reviewable

The release workflow SHALL continue to dispatch managed rollout automatically after publishing an immutable platform version, and ordinary rollout SHALL continue to stop at a reviewable downstream PR. Pre-task rollout reconciliation MAY later adopt that PR through normal downstream GitHub gates, but SHALL NOT redefine routine rollout creation as unconditional auto-merge.

#### Scenario: New immutable platform release is published

- **WHEN** release automation publishes `vX.Y.Z`
- **THEN** it dispatches managed rollout for that exact release
- **AND** a clean downstream update is opened as a reviewable rollout PR
- **AND** central rollout does not unconditionally merge that PR

### Requirement: Routine rollout delivery does not create managed backlog work

A routine platform rollout PR SHALL remain operational delivery state and SHALL NOT create a Development Backlog managed task solely because it is waiting for downstream adoption.

#### Scenario: Rollout PR waits for later adoption

- **WHEN** a clean rollout PR remains open after central rollout completes
- **THEN** no Development Backlog issue is created solely for that pending PR
- **AND** later supported task preflight is responsible for detecting and reconciling it

### Requirement: A delivered shared-workspace permission change is released immutably

After the shared-workspace permission implementation is merged, the platform
SHALL publish it through a new immutable SemVer release and SHALL dispatch
managed rollout using that exact published tag. It SHALL NOT use mutable source
history, move an existing tag, force-push a rollout branch, or auto-merge a
downstream rollout PR.

#### Scenario: Exact-version rollout follows the release

- **GIVEN** the source implementation is merged and a new unused patch version
  is selected
- **WHEN** its release PR changes `VERSION` and GitHub publishes the release
- **THEN** rollout receives the exact immutable release tag
- **AND** each `managed` inventory entry receives a reviewed exact-version
  Copier update PR or an explicit bounded diagnostic
- **AND** `candidate` and `excluded` inventory entries are not mutated

### Requirement: Blocked managed rollout is recoverable through the same delivery contract

A terminal blocked rollout attempt SHALL preserve enough structured evidence to identify the owning blocker when that blocker is deterministically knowable, and a later retry after the blocker is resolved SHALL reuse the normal exact-version reviewed-rollout path rather than require a manual alternate delivery mechanism.

#### Scenario: Multiple managed repositories fail for different reasons

- **WHEN** one platform release produces blocked rollout attempts in multiple managed repositories
- **THEN** each repository is classified from its own structured evidence
- **AND** the platform SHALL NOT infer one shared root cause merely from temporal coincidence

#### Scenario: Existing diagnostic reports unknown but a stable platform stage exposes the blocker

- **WHEN** rollout terminates in a platform-owned stage with enough bounded structured state to identify the failure class
- **THEN** the terminal diagnostic SHALL use that stable category/reason instead of `unknown`
- **AND** SHALL NOT scrape arbitrary unrestricted logs to guess a cause

#### Scenario: Failure is caused by shared-workspace permissions owned by another accepted change

- **GIVEN** the same root cause is already owned by managed change `enforce-shared-workspace-permissions`
- **WHEN** rollout repair diagnoses that condition
- **THEN** this change records the dependency instead of implementing a competing permission mechanism
- **AND** independent rollout defects continue to be repaired in parallel

#### Scenario: Blocker is resolved and rollout is retried

- **WHEN** the exact target release or a later cumulative immutable release containing the fix is retried
- **THEN** each managed repository passes normal rollout preparation and creates/reuses its reviewable rollout PR, or is proven already at the exact target version
- **AND** its failure-streak tracker is closed by the existing successful-preparation path rather than manual bookkeeping

### Requirement: Rollout recovery preserves conflict and ownership safety

Repairing a failed rollout SHALL NOT turn unresolved Copier conflicts, project-owned path ambiguity, changed automation head, failed validation or branch-protection requirements into success.

#### Scenario: Copier leaves an unresolved rejection during recovery

- **WHEN** a retry still contains a non-ignored `.rej` or unresolved ownership conflict
- **THEN** rollout remains blocked
- **AND** no downstream default-branch mutation or silent overwrite occurs

#### Scenario: Historical platform workflow differs only in redundant blank separators

- **GIVEN** a platform-owned `.github/workflows/dev-platform.yml` has no YAML block scalar content
- **AND** its committed historical rendering differs from its recorded immutable baseline only by repeated blank separators
- **WHEN** Copier reports a conflict for that workflow during guarded recovery
- **THEN** rollout MAY treat that formatting-only difference as baseline-equivalent and recopy the platform-owned workflow
- **AND** comments, non-empty content, all other paths, and workflows containing YAML block scalars SHALL remain byte-sensitive ownership checks

#### Scenario: Downstream validation creates disposable build artifacts

- **GIVEN** Copier and candidate bootstrap have produced a reviewable exact-version diff
- **WHEN** a downstream validation command creates generated files in the isolated rollout checkout
- **THEN** rollout SHALL commit only the Copier/bootstrap diff staged before validation
- **AND** validation failure SHALL still block delivery
- **AND** validation filesystem side effects SHALL NOT be added to the rollout pull request

### Requirement: Managed rollout preserves project-owned ignore extensions

A fresh managed platform render SHALL seed the platform `.gitignore` baseline. On every later Copier update, the complete existing downstream `.gitignore` SHALL be treated as project-owned and preserved byte-for-byte, regardless of harness mode. The platform SHALL NOT treat any part of an existing downstream `.gitignore` as replaceable template content.

#### Scenario: Project adds local runtime ignore rules

- **GIVEN** a managed repository has project-owned ignore entries in addition to the platform baseline
- **WHEN** a later platform release is applied through the supported Copier rollout path
- **THEN** the project-owned ignore behavior remains effective
- **AND** the initial-render baseline remains intact alongside those project rules

### Requirement: Rollout fails closed when managed rendering removes ignore coverage

Before publishing a managed rollout, the platform SHALL detect when managed rendering causes previously ignored representative local-secret or runtime artifact classes to become visible to Git and SHALL stop the rollout with an actionable diagnostic.

#### Scenario: Copier render drops a credential/runtime ignore rule

- **GIVEN** a representative synthetic secret/runtime path is ignored before the managed render
- **AND** the render removes the rule responsible for that coverage
- **WHEN** rollout validation evaluates the rendered result
- **THEN** rollout publication is blocked
- **AND** the diagnostic identifies lost ignore coverage without reading, deleting, staging or committing the local artifact

#### Scenario: Project extensions survive a normal update

- **GIVEN** project-owned ignore rules cover representative environment, database, dependency and build artifacts
- **WHEN** the managed Copier update preserves those rules
- **THEN** validation passes this guard
- **AND** those artifacts remain ignored after the update

### Requirement: Managed project-owned publication harnesses conform to shared exact-head merge safety

A managed repository with `harness_mode=project` SHALL retain ownership of its repository-specific task/worktree/integration harness, but that ownership SHALL NOT weaken the platform-owned merge-safety invariant. Managed rollout SHALL treat exact-head publication safety as a conformance requirement for project-owned publication code.

A bounded compatibility migration MAY change only the recognized publication identity/confirmation surface when applicability is proven by a deterministic, reviewed compatibility predicate. Unknown or drifted project-owned harness content SHALL fail closed with an actionable diagnostic and SHALL be preserved rather than overwritten.

Advancing `.copier-answers.yml` or `.dev-platform.toml` platform version metadata alone SHALL NOT count as successful safety adoption for a project-owned harness whose publication surface is known to require conformance.

#### Scenario: Jara-like project harness has a recognized vulnerable publication shape

- **GIVEN** a managed project-owned harness matches the reviewed Jara-like compatibility fixture
- **WHEN** rollout applies the safety release
- **THEN** only the vulnerable publication identity/confirmation surface is migrated to stable PR identity plus exact expected head
- **AND** project-owned board, worktree, and serialized integration behavior remains intact
- **AND** the migration is idempotent

#### Scenario: Planner-like project harness has a recognized vulnerable publication shape

- **GIVEN** a managed project-owned harness matches the reviewed Planner-like compatibility fixture
- **WHEN** rollout applies the safety release
- **THEN** its publication path gains stable PR identity and exact-head confirmation
- **AND** its standalone integration-clone semantics remain intact
- **AND** the migration is idempotent

#### Scenario: Project-owned publication harness has unexpected drift

- **GIVEN** a managed `harness_mode=project` repository does not match a reviewed compatibility predicate
- **WHEN** rollout cannot prove the bounded safety migration is applicable
- **THEN** rollout fails closed before publishing a downstream update that claims safety conformance
- **AND** the project-owned harness bytes remain unchanged
- **AND** the diagnostic identifies the publication-safety compatibility blocker without guessing a rewrite

#### Scenario: Platform-owned harness receives the same safety release

- **GIVEN** a managed repository uses `harness_mode=platform`
- **WHEN** rollout applies the safety release
- **THEN** normal Copier-managed lifecycle files receive the exact-head publication implementation
- **AND** no project-harness compatibility rewrite is attempted

#### Scenario: Candidate or excluded repository is known to the registry

- **GIVEN** a repository is not in `managed` state
- **WHEN** ordinary managed rollout runs for the safety release
- **THEN** the repository is not mutated
- **AND** it receives the corrected contract only through a later deliberate adoption path

### Requirement: Compatibility migration activates before a project harness CLI guard

When a managed project-owned publication harness matches a reviewed legacy
compatibility predicate, Dev Platform SHALL install the exact-head publication
implementation before the script's effective CLI entrypoint. A migration SHALL
NOT rely on definitions that execute only after `if __name__ == "__main__"`.
The migration SHALL preserve repository-specific orchestration outside the
bounded publication surface and SHALL fail closed without writing unrecognized
or structurally ambiguous harness bytes.

#### Scenario: Jara-like harness is invoked as a CLI after migration

- **GIVEN** a reviewed Jara-like harness has an old merged PR for branch X at
  head A and a current reused branch X at head B
- **WHEN** its migrated script is run through Python's CLI entrypoint
- **THEN** the exact-head publication implementation is active before `main()`
- **AND** PR A cannot authorize terminal success, remote deletion, or board
  cleanup for B
- **AND** board/worktree/serialized orchestration remains intact.

#### Scenario: Planner-like harness is invoked as a CLI after migration

- **GIVEN** a reviewed Planner-like harness is migrated
- **WHEN** the script is invoked through its real CLI entrypoint
- **THEN** exact PR identity and exact merge confirmation are active before
  `main()`
- **AND** standalone integration-clone orchestration remains intact.

#### Scenario: Unknown or ambiguous project harness is encountered

- **WHEN** its source fingerprint or CLI guard shape differs from a reviewed
  migration predicate
- **THEN** rollout fails with a compatibility diagnostic
- **AND** it does not write the helper or modify harness bytes.

### Requirement: Reviewed Jara exact-head migration adapts its known regression surface

When a reviewed Jara project-owned publication harness requires an exact-head
compatibility migration, Dev Platform SHALL also adapt the known reviewed
regression test surface that strictly mocks that publication behavior. Both
surfaces SHALL be selected only by exact reviewed bytes and a rerun SHALL
prove the generated state by reconstructing those bytes. Unknown or partial
project-owned test drift SHALL block without writing either surface.

#### Scenario: Known Jara strict mocks receive exact-head responses

- **GIVEN** Jara's reviewed legacy test source and publication harness
- **WHEN** rollout applies the exact-head migration
- **THEN** the strict mocks return a local branch head and one matching exact
  PR record
- **AND** Jara's merge-policy and cleanup regressions remain asserted
- **AND** the resulting Jara CI is eligible to pass without manual edits.

#### Scenario: Unknown Jara regression-test drift is encountered

- **WHEN** the companion test source differs from both the reviewed legacy
  and reversibly generated forms
- **THEN** rollout fails closed before modifying the harness, helper, or test.

### Requirement: Project-harness rollout proves terminal reconciliation conformance

For a managed project-owned harness whose lifecycle requires terminal status
projection, rollout SHALL not treat platform version metadata advancement as
successful adoption unless the reviewed compatibility surface proves exact
merged-PR terminal reconciliation. Unknown or drifted project-owned harnesses
SHALL remain unchanged and block rollout.

#### Scenario: Recognized Planner-like harness receives terminal migration

- **GIVEN** the reviewed Planner-like publication and finish surfaces match the
  approved compatibility predicate
- **WHEN** rollout applies the terminal reconciliation release
- **THEN** exact merge proof, pending-reconciliation recovery and idempotent
  `Done` projection are installed without replacing standalone-clone behavior

#### Scenario: Planner-like harness cannot be proven safe

- **WHEN** either required compatibility surface has unknown or drifted bytes
- **THEN** rollout fails before advancing version metadata or modifying harness bytes

