## MODIFIED Requirements

### Requirement: Copier upgrades are tested, not assumed

Before a platform release is published, CI SHALL exercise a real Copier update from the latest stable platform template or an explicit bootstrap baseline to the candidate template. The smoke project SHALL contain project-owned modifications before update and SHALL fail validation if those modifications are lost or unresolved conflicts remain.

#### Scenario: Candidate platform is tested against existing project state

- **WHEN** platform CI evaluates an update from the stable baseline
- **THEN** it performs a real Copier update on a smoke project containing project-owned customization and verifies that customization survives without unresolved conflicts

#### Scenario: Checkout has no historical baseline to upgrade from

- **GIVEN** the current checkout has no local stable version tag
- **AND** the bootstrap baseline commit does not exist in the checkout's own history
- **WHEN** the Copier-upgrade smoke test runs
- **THEN** it skips cleanly with a clear reason instead of failing
- **AND** it performs no Copier invocation before determining no baseline exists

### Requirement: Platform releases use stable immutable versions

Published Project Factory versions SHALL use stable SemVer Git tags. A published version tag SHALL NOT be moved or reused, and automated publication SHALL fail closed when an existing tag points elsewhere.

#### Scenario: Existing release tag points to another commit

- **WHEN** release automation finds that the requested SemVer tag already exists at a different commit
- **THEN** publication fails instead of moving the tag

#### Scenario: A fresh-history root commit includes a valid VERSION

- **GIVEN** the current commit has no Git parent (for example a freshly bootstrapped public-history checkout)
- **AND** its `VERSION` file parses as valid SemVer
- **WHEN** release automation evaluates release intent
- **THEN** no tag is created
- **AND** no GitHub Release is created
- **AND** the run completes without publishing anything

#### Scenario: VERSION is unchanged from the parent commit

- **GIVEN** a non-root commit whose `VERSION` value is identical to its first parent's
- **WHEN** release automation evaluates release intent
- **THEN** no tag or release is created for that commit

### Requirement: Successful releases dispatch reviewed downstream rollout

After publishing an immutable platform version, the central release workflow SHALL dispatch the managed-project rollout for that exact SemVer tag only when the repository has explicitly opted in via a repository variable (never a secret, since a secret's mere presence SHALL NOT double as a feature flag).

#### Scenario: New platform version is published

- **GIVEN** the repository has explicitly opted in to managed rollout via its repository variable
- **WHEN** the release workflow successfully creates or confirms `vX.Y.Z` at the release commit
- **THEN** it dispatches the rollout workflow with target version `vX.Y.Z`

#### Scenario: A generic repository publishes a release without operator opt-in

- **GIVEN** the repository has not set the managed-rollout opt-in variable (the default for a generic public checkout)
- **WHEN** the release workflow successfully creates or confirms `vX.Y.Z` at the release commit
- **THEN** the release and tag are created normally
- **AND** rollout is not dispatched
- **AND** the run explicitly reports that managed rollout is disabled/not configured
- **AND** the run completes successfully

#### Scenario: Manual retry names an unpublished version

- **WHEN** a manually dispatched rollout requests a syntactically valid tag that is not a published immutable platform release
- **THEN** rollout fails before creating any downstream write token or mutation

#### Scenario: A bootstrap run does not dispatch rollout

- **GIVEN** the release workflow's own release-intent determination for the current commit is false (for example a fresh-history root commit)
- **WHEN** the release workflow runs
- **THEN** it does not dispatch the rollout workflow, regardless of the managed-rollout opt-in variable

### Requirement: Rollout fails closed on project ambiguity or conflicts

Automatic rollout SHALL leave the downstream default branch untouched when Copier metadata is missing or unexpected, a downgrade is requested, an unresolved Copier/Git conflict remains, project validation fails, or an unexpected rollout branch collision exists.

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

### Requirement: Managed rollout emits one machine-readable terminal diagnostic

For every failed managed-project rollout attempt, the workflow SHALL emit one canonical machine-readable diagnostic envelope derived from structured rollout state. The envelope SHALL be available without requiring arbitrary full-log scraping and SHALL NOT alter rollout safety or outcome.

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

The platform SHALL maintain a durable, cross-run record of consecutive terminal `blocked` managed-rollout attempts per project, independent of any single ephemeral workflow run. When that count reaches a fixed threshold, the platform SHALL escalate beyond the existing per-attempt annotation into a distinct, labeled, human-discoverable alert.

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
- **WHEN** creating, reading, or updating the durable tracking record fails for any reason, including label bootstrap or a missing required token
- **THEN** the tracking step fails with a non-zero exit and a message naming the failed operation
- **AND** the failure is not downgraded to a warning or hidden by `continue-on-error`
- **AND** it SHALL NOT retry, push, merge, or otherwise act beyond the tracking record itself

#### Scenario: Preparation diagnostic is missing when recording a failure
- **GIVEN** rollout preparation failed for a project
- **WHEN** the failure record is written and the preparation diagnostic file is missing or unreadable
- **THEN** the tracking step fails naming the missing diagnostic
- **AND** no `unknown` category or reason is substituted

### Requirement: Historical Copier replay may recover only proven platform-owned state

Managed rollout MAY use guarded Copier recopy to recover a smart-update conflict on a platform-owned harness only when every conflicted path is proven safe from immutable pre-update state. Any currently divergent or otherwise unproven path SHALL remain fail-closed.

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
- **WHEN** any conflicted path differs from its recorded old-template state, from any applicable reclaimed target state and from its target render with the recorded answers
- **THEN** managed rollout fails closed without recopy

#### Scenario: Baseline proof is computed after Copier mutates the worktree
- **WHEN** rollout classifies conflicts after smart update has emitted `.rej` files
- **THEN** downstream equivalence SHALL be derived from committed `HEAD` rather than current worktree bytes
- **AND** the old side SHALL be read from the exact immutable tag recorded by `.copier-answers.yml`

#### Scenario: Hand edit already equals the target render
- **GIVEN** a managed repository uses `harness_mode=platform`
- **AND** it hand-edited a platform-owned workflow and recorded the answers under which the target template renders exactly that edit
- **WHEN** smart Copier update replays the edit from the recorded old template and emits a rejection because the target template changed the same lines
- **THEN** the path is eligible for guarded recopy, because the committed file is byte-identical to the target render
- **AND** after recopy the path SHALL match the target render
- **AND** a hand edit that differs from the target render in any byte, or a path missing on either side, SHALL remain fail-closed

### Requirement: Rollout alerts reconcile against recovered project state

The platform SHALL offer a bounded reconciliation of open rollout failure issues against the managed project's authoritative current platform state. It SHALL close an existing issue with a resolution note only when recovery after its last failed release is proven. Unreadable or ambiguous evidence SHALL leave the alert open. The existing issue SHALL remain the sole durable alert record.

#### Scenario: Project recovered outside rollout

- **GIVEN** an open rollout failure issue for a managed project
- **AND** the project's default branch has coherent platform version records proving recovery at or beyond the failed release
- **WHEN** alert reconciliation runs
- **THEN** it closes the existing issue with a recovery note

#### Scenario: Recovery cannot be proven

- **WHEN** the project version records are stale, inconsistent or unreadable
- **THEN** reconciliation leaves the issue open and reports why

#### Scenario: Reconciliation runs twice

- **WHEN** reconciliation repeats after an issue was closed
- **THEN** it makes no further mutation or duplicate alert record

### Requirement: Failed managed rollout runs raise a release-level alarm

When the plan job or any per-project job of a `Roll Out Platform` run did not succeed (failed, cancelled, timed out or never finished), the platform SHALL open one durable alert per release tag in the platform repository, or add to the open one, naming the release tag, each failed stage or target repository, its failed step and its error text, together with the run link and dispatch context.

#### Scenario: Plan stage fails
- **GIVEN** a rollout run whose plan job fails, for example because the operator registry checkout reports the repository not found
- **WHEN** the alarm job runs
- **THEN** an open alert labeled `rollout-alert` for the requested release tag names stage `plan`, its failed step and the error text
- **AND** the release tag is named even when plan failed before resolving it, using the same rule as plan (`version` input or `v<VERSION>`)

#### Scenario: One target fails while others succeed
- **GIVEN** a rollout run in which some per-project jobs succeed and one fails or is cancelled
- **WHEN** the alarm job runs
- **THEN** the alert names only the failed target repositories with their failed step and error
- **AND** the run is reported as a failure, not as success

#### Scenario: Release-dispatched and manually dispatched runs are both covered
- **WHEN** a rollout run started by the release workflow, or a manual dispatch for all projects or for one `repository`, has a failed job
- **THEN** the alert is raised and records the event, the triggering actor and the requested scope

#### Scenario: A later failing run for the same release
- **GIVEN** an alert for release `vX.Y.Z` is already open
- **WHEN** another rollout run for `vX.Y.Z` fails
- **THEN** the failure is added to the same alert and no second alert is opened for that tag

#### Scenario: Successful run
- **WHEN** every job of a rollout run succeeds
- **THEN** no alert is created
- **AND** if an alert for that release is open, it receives a note that this run succeeded for its scope and stays open

#### Scenario: Failed job without an error annotation
- **WHEN** a failed job has no failure-level annotation
- **THEN** the alert states that no error annotation was recorded and links the job log
- **AND** no error text is invented

#### Scenario: The alarm cannot be delivered
- **WHEN** reading the run's jobs, bootstrapping the label, or creating or commenting on the alert fails
- **THEN** the alarm job exits non-zero naming the failed operation
- **AND** it is not hidden by `continue-on-error`

### Requirement: Managed project-owned publication harnesses prove exact-head merge safety without platform rewrites

Managed rollout SHALL treat exact-head publication safety as a conformance requirement for project-owned publication code and SHALL NOT rewrite project-owned harness bytes to obtain it.

#### Scenario: Project-owned publication harness does not prove conformance

- **GIVEN** a managed `harness_mode=project` repository whose publication surface lacks the exact-head conformance signals
- **WHEN** rollout runs
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

## ADDED Requirements

### Requirement: The Copier upgrade test falls back to a bootstrap baseline without a stable tag

For the pre-release Copier update test, when no local stable version tag exists, CI SHALL fall back to a bootstrap baseline commit.

#### Scenario: No local stable version tag exists

- **GIVEN** the current checkout has no local stable version tag
- **WHEN** CI runs the pre-release Copier update test
- **THEN** CI falls back to a bootstrap baseline commit

### Requirement: The Copier upgrade smoke test skips cleanly without a prior baseline

If neither a stable tag nor a resolvable bootstrap baseline exists in the current checkout's own history (for example a fresh-history public-distribution snapshot with no prior commits), the Copier upgrade smoke test SHALL skip cleanly instead of failing, since there is no meaningful prior platform state to upgrade from in that checkout.

#### Scenario: Fresh-history checkout has no stable tag and no bootstrap baseline

- **GIVEN** neither a stable tag nor a resolvable bootstrap baseline exists in the current checkout's own history
- **WHEN** the Copier upgrade smoke test runs
- **THEN** the smoke test skips cleanly instead of failing

### Requirement: Release automation determines release intent before tagging

Release automation SHALL first determine whether the current commit actually establishes publishable release intent before creating or confirming any tag or release.

#### Scenario: Release automation runs on a commit

- **WHEN** release automation runs on the current commit
- **THEN** it first determines whether the commit establishes publishable release intent
- **AND** only then creates or confirms any tag or release

### Requirement: A root commit never establishes release intent

A commit with no Git parent (a repository root/bootstrap commit) SHALL NEVER establish release intent, regardless of what its `VERSION` file contains: a fresh-history bootstrap commit and a genuine first version bump are structurally identical by file content alone, so parentage is the fact that distinguishes them.

#### Scenario: Root commit contains a VERSION file

- **GIVEN** a commit with no Git parent whose `VERSION` file contains a valid version
- **WHEN** release intent is determined for that commit
- **THEN** the commit does not establish release intent

### Requirement: A non-root commit establishes release intent only by changing VERSION

A non-root commit SHALL establish release intent only when its `VERSION` value differs from its first parent's; an unchanged `VERSION` SHALL NOT trigger publication.

#### Scenario: Non-root commit changes VERSION

- **WHEN** a non-root commit's `VERSION` value differs from its first parent's
- **THEN** the commit establishes release intent

#### Scenario: Non-root commit keeps VERSION unchanged

- **WHEN** a non-root commit's `VERSION` value equals its first parent's
- **THEN** the unchanged `VERSION` does not trigger publication

### Requirement: Release publication does not require operator fleet configuration

Publishing an immutable platform release is a core Dev Platform capability available to any checkout. Managed fleet rollout is a distinct, optional operator capability that requires a private managed-projects registry and dedicated GitHub App credentials. Publishing a release SHALL NEVER by itself require or imply operator fleet configuration.

#### Scenario: Checkout without fleet configuration publishes a release

- **GIVEN** a checkout has no private managed-projects registry and no dedicated GitHub App credentials
- **WHEN** it publishes an immutable platform release
- **THEN** publishing the release does not require or imply operator fleet configuration

### Requirement: A release without managed rollout opt-in stays published and reports rollout disabled

After publishing an immutable platform version, absent or non-affirmative repository opt-in to managed rollout SHALL leave the release published but SHALL NOT dispatch rollout, and the run SHALL explicitly report that managed rollout is disabled or not configured.

#### Scenario: Release published with non-affirmative opt-in

- **GIVEN** the repository's managed rollout opt-in is absent or non-affirmative
- **WHEN** the central release workflow publishes an immutable platform version
- **THEN** the release stays published
- **AND** rollout is not dispatched
- **AND** the run explicitly reports that managed rollout is disabled or not configured

### Requirement: Managed rollout supports manual retry and rejects unpublished versions

Managed-project rollout SHALL also support an explicit manual retry path and SHALL reject versions that are not actually published platform releases.

#### Scenario: Operator retries rollout manually for a published release

- **WHEN** an operator manually retries managed-project rollout for a published platform release
- **THEN** rollout accepts the explicit manual retry

#### Scenario: Requested rollout version is not a published release

- **WHEN** managed-project rollout is requested for a version that is not actually a published platform release
- **THEN** rollout rejects that version

### Requirement: Release workflow dispatches rollout only for established release intent

Rollout dispatch from the release workflow SHALL occur only when the current run itself established publishable release intent (an actual version bump) AND the repository has opted in to managed rollout. A run that determines it has no release intent (including a fresh-history root/bootstrap commit or an unchanged `VERSION`) SHALL NOT dispatch rollout regardless of opt-in.

#### Scenario: Opted-in run has no release intent

- **GIVEN** the repository has opted in to managed rollout
- **WHEN** a release workflow run determines it has no release intent because `VERSION` is unchanged
- **THEN** the run does not dispatch rollout

#### Scenario: Opted-in run established release intent

- **GIVEN** the repository has opted in to managed rollout
- **WHEN** the current release workflow run itself established publishable release intent through an actual version bump
- **THEN** the run may dispatch rollout

### Requirement: Pending rollout PR detection uses a platform-owned structured helper

Detection of an already-pending rollout PR SHALL be performed by a testable, platform-owned helper that filters structured GitHub API JSON by the exact reserved branch, configured base branch, and expected rollout automation identity -- not by ad hoc shell/`jq` argument combinations, human-readable `gh` command output parsing, or PR title/body text matching.

#### Scenario: Rollout checks for an already-pending rollout PR

- **WHEN** automatic rollout checks whether a rollout PR is already pending
- **THEN** a testable, platform-owned helper filters structured GitHub API JSON by the exact reserved branch, configured base branch and expected rollout automation identity
- **AND** the detection does not rely on ad hoc shell/`jq` argument combinations, human-readable `gh` command output parsing, or PR title/body text matching

### Requirement: The managed rollout diagnostic envelope carries the required fields

The managed rollout diagnostic envelope SHALL include at least: schema version, terminal status, target project, target immutable release, failure stage, failure category, stable reason, exit code, selected command when known, same-input retry advisory, and structured evidence already known to rollout such as conflict paths.

#### Scenario: Diagnostic envelope is emitted for a failed rollout with known conflict paths

- **GIVEN** a managed-project rollout attempt failed with conflict paths known to rollout
- **WHEN** the diagnostic envelope is emitted
- **THEN** it includes schema version, terminal status, target project, target immutable release, failure stage, failure category, stable reason, exit code and same-input retry advisory
- **AND** it includes the selected command when known
- **AND** it includes the known conflict paths as structured evidence

### Requirement: The managed rollout diagnostic envelope excludes secrets and raw logs

The managed rollout diagnostic envelope SHALL exclude credentials, unrestricted environment dumps, tokens, and raw logs.

#### Scenario: Diagnostic envelope is emitted from a run with credentials and logs

- **WHEN** the managed rollout diagnostic envelope is emitted
- **THEN** it contains no credentials, unrestricted environment dumps, tokens, or raw logs

### Requirement: The repeated rollout failure record is written on failed preparation and reset on success

The durable, cross-run record of consecutive terminal `blocked` managed-rollout attempts per project SHALL reset the next time that project's rollout preparation succeeds. The failure record is written exactly when rollout preparation itself failed; failures before preparation are covered by the release-level rollout alarm.

#### Scenario: Project rollout preparation succeeds after recorded failures

- **GIVEN** a project has a record of consecutive terminal `blocked` managed-rollout attempts
- **WHEN** that project's rollout preparation next succeeds
- **THEN** the record resets

#### Scenario: Rollout fails before preparation

- **WHEN** a managed rollout fails before rollout preparation
- **THEN** no failure record is written for that attempt
- **AND** the failure is covered by the release-level rollout alarm

### Requirement: Repeated rollout failure tracking ensures its labels exist

For repeated managed-rollout failure tracking, before either the tracking label or the alert label is referenced, the platform SHALL idempotently ensure both exist on the tracker repository, using only the least-privilege permission already granted to the rollout job.

#### Scenario: Tracking references its labels

- **WHEN** repeated managed-rollout failure tracking is about to reference the tracking label or the alert label
- **THEN** the platform first idempotently ensures both labels exist on the tracker repository
- **AND** it uses only the least-privilege permission already granted to the rollout job

### Requirement: Repeated rollout failure tracking does not affect rollout behavior

The repeated managed-rollout failure tracking layer SHALL NOT retry, push, merge, or affect PR-creation, and SHALL NOT modify any existing safety guard, recovery eligibility, or credential scope.

#### Scenario: Tracking records a blocked attempt

- **WHEN** the repeated managed-rollout failure tracking layer records a terminal `blocked` attempt
- **THEN** it does not retry, push, merge, or affect PR-creation
- **AND** it does not modify any existing safety guard, recovery eligibility, or credential scope

### Requirement: A repeated rollout failure tracking error fails the tracking step explicitly

A failure inside the repeated managed-rollout failure tracking layer, including a failure to bootstrap its own labels or a missing required input, SHALL fail the tracking step explicitly with a message naming what failed; the failure SHALL NOT be converted into a warning.

#### Scenario: Tracking cannot bootstrap its labels

- **WHEN** the repeated managed-rollout failure tracking layer fails to bootstrap its own labels or lacks a required input
- **THEN** the tracking step fails explicitly with a message naming what failed
- **AND** the failure is not converted into a warning

### Requirement: A guarded Copier recopy conflict is safe only under the recorded conditions

A conflict SHALL count as safe when either (a) an explicitly reclaimed migration path already matches the exact target immutable template, (b) the committed downstream path exactly matches the same path in the immutable platform template version recorded by `.copier-answers.yml`, or (c) the committed downstream path is a regular file byte-identical to the target immutable template rendered with the recorded answers, re-proven from committed `HEAD` after the reset and matched again after recopy.

#### Scenario: A conflicted path meets one of the safe conditions

- **WHEN** a conflicted path of a guarded Copier recopy is an explicitly reclaimed migration path matching the exact target immutable template, matches the same path in the recorded immutable platform template version, or is a regular file byte-identical to the target immutable template rendered with the recorded answers and re-proven from committed `HEAD`
- **THEN** the conflict counts as safe

### Requirement: Missing paths count as baseline equivalence for guarded Copier recopy

For guarded Copier recopy, missing/missing SHALL count as baseline equivalence.

#### Scenario: A conflicted path is missing in both states

- **WHEN** a conflicted path is missing in both compared states of a guarded Copier recopy
- **THEN** the path counts as baseline equivalence

### Requirement: Rollout alert reconciliation runs periodically

Reconciliation of open rollout failure issues SHALL run periodically without requiring a later automated rollout or a manual stale-rollout supersession apply action.

#### Scenario: No later rollout or supersession apply happens

- **GIVEN** an open rollout failure issue exists
- **AND** no later automated rollout and no manual stale-rollout supersession apply action runs
- **WHEN** the periodic schedule fires
- **THEN** reconciliation of open rollout failure issues runs

### Requirement: Every Roll Out Platform run ends with an alarm job

Every `Roll Out Platform` run, whether dispatched by the release workflow or manually for all managed projects or one repository, SHALL end with an always-running alarm job that runs reviewed workflow-ref code and inspects the current run attempt's own jobs.

#### Scenario: Roll Out Platform is dispatched manually for one repository

- **WHEN** a `Roll Out Platform` run is dispatched manually for one repository
- **THEN** the run ends with an always-running alarm job
- **AND** the alarm job runs reviewed workflow-ref code and inspects the current run attempt's own jobs

### Requirement: A fully successful Roll Out Platform run raises no alarm

A fully successful `Roll Out Platform` run SHALL raise no alarm.

#### Scenario: Every job of the rollout run succeeds

- **WHEN** the plan job and every per-project job of a `Roll Out Platform` run succeed
- **THEN** the run raises no alarm

### Requirement: The release-level rollout alarm does not change rollout state

The release-level rollout alarm SHALL NOT retry, repair, push or merge anything.

#### Scenario: Alarm is raised for a failed rollout

- **WHEN** the release-level rollout alarm is raised
- **THEN** it does not retry, repair, push or merge anything

### Requirement: An undeliverable release-level rollout alarm fails the alarm job

When the release-level rollout alarm cannot be delivered, the alarm job SHALL fail with a message naming what failed.

#### Scenario: Alarm delivery fails

- **WHEN** the release-level rollout alarm cannot be delivered
- **THEN** the alarm job fails with a message naming what failed

### Requirement: Project-owned harness ownership does not weaken platform merge safety

A managed repository with `harness_mode=project` SHALL retain ownership of its repository-specific task/worktree/integration harness, but that ownership SHALL NOT weaken the platform-owned merge-safety invariant.

#### Scenario: Managed repository owns its harness

- **GIVEN** a managed repository with `harness_mode=project`
- **WHEN** managed rollout runs
- **THEN** the repository retains ownership of its repository-specific task/worktree/integration harness
- **AND** the platform-owned merge-safety invariant still applies

### Requirement: A non-conforming project-owned harness fails closed and is preserved

A project-owned harness that does not prove exact-head publication safety conformance SHALL fail closed with an actionable diagnostic and SHALL be preserved rather than overwritten.

#### Scenario: Project-owned harness does not prove conformance

- **WHEN** a project-owned harness does not prove exact-head publication safety conformance
- **THEN** managed rollout fails closed with an actionable diagnostic
- **AND** the harness is preserved rather than overwritten

### Requirement: Version metadata alone is not safety adoption for a project-owned harness

Advancing `.copier-answers.yml` or `.dev-platform.toml` platform version metadata alone SHALL NOT count as successful safety adoption for a project-owned harness whose publication surface is known to require conformance.

#### Scenario: Only platform version metadata advances

- **GIVEN** a project-owned harness whose publication surface is known to require conformance
- **WHEN** only the `.copier-answers.yml` or `.dev-platform.toml` platform version metadata advances
- **THEN** that advance does not count as successful safety adoption
