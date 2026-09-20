# standard-profile-lifecycle Specification

## Purpose
Define compatibility guarantees and lifecycle behavior for repositories using the standard workflow profile.
## Requirements
### Requirement: Standard profile exposes a managed task-start compatibility contract

Dev Platform SHALL provide the callable task-start interface required by
managed-task intake for every supported standard-profile generated or adopted
project. The interface SHALL create/reuse only the configured isolated task
clone/branch and SHALL preserve existing profile-specific lifecycle behavior.

#### Scenario: Managed intake starts a standard-profile task

- **GIVEN** a structurally valid managed package targets a standard-profile project
- **WHEN** managed start composes package intake with the project task-start entrypoint
- **THEN** the callable task-start contract is available and creates the expected isolated task state
- **AND** package materialization occurs only in that task checkout.

#### Scenario: Template removes a required start interface

- **WHEN** a platform template or shared helper no longer satisfies the managed intake task-start contract
- **THEN** deterministic platform compatibility tests fail before release or downstream rollout
- **AND** no downstream project must discover the mismatch during implementation.

### Requirement: Standard parent-only routing supports isolated full clones without weakening child containment

Dev Platform SHALL permit routing preflight for a parent-only standard-profile
task executed in an isolated full clone. It SHALL record that clone as the
parent route root without requiring a multi-agent linked worktree.

This exception SHALL NOT authorize a delegated child writer. A child that can
write repository state SHALL continue to require an assigned worktree and the
existing proven containment boundary.

#### Scenario: Supervisor records standard-clone preflight

- **GIVEN** a managed standard-profile task runs in a standalone isolated clone
- **WHEN** the supervisor records routing preflight
- **THEN** routing succeeds with the clone as the parent route root
- **AND** the record truthfully identifies parent-only execution.

#### Scenario: Child writer is requested from a standard clone

- **WHEN** a write-capable delegated child is requested without a distinct assigned worktree
- **THEN** the platform refuses the launch before the child can write
- **AND** parent-only route recording is not treated as child containment evidence.

### Requirement: Platform release validates downstream profile compatibility

Dev Platform SHALL run a deterministic consumer compatibility suite for light,
standard and multi-agent profiles before publishing or rolling out template
lifecycle changes. The suite SHALL include standard managed-start and routing
preflight behavior through rendered or adopted downstream-compatible files.

#### Scenario: Standard consumer canary fails

- **WHEN** the rendered/adopted standard-profile canary cannot complete managed-start composition or routing preflight
- **THEN** platform release or rollout validation fails before downstream publication
- **AND** the diagnostic identifies the profile and lifecycle boundary that failed.

#### Scenario: Profile controls remain compatible

- **WHEN** the consumer compatibility suite runs
- **THEN** light and multi-agent profile controls continue to pass their supported lifecycle contracts
- **AND** the suite does not require real GitHub credentials, a model runtime, or a write-capable child agent.

### Requirement: Standard publication core is provider-neutral

The standard profile SHALL express task publication in provider-neutral lifecycle terms: synchronize remote integration state, create/use a task branch, publish the branch, open or reuse the provider's change-review object, observe required checks, and reach a configured human or automatic merge terminal state. Provider-specific APIs and CLI commands SHALL remain behind adapters.

#### Scenario: Standard GitLab task reaches human acceptance
- **GIVEN** a standard project configured with the GitLab adapter
- **WHEN** a verified task branch is published
- **THEN** the adapter can open or reuse the exact GitLab merge request for that branch/head
- **AND** observe the GitLab CI result needed by the configured acceptance policy
- **AND** stop at human merge/acceptance for the client-pilot configuration
- **AND** the core lifecycle does not require GitHub CLI or GitHub Actions.

#### Scenario: Standard GitHub task uses the same core lifecycle
- **GIVEN** a standard project configured with the GitHub adapter
- **WHEN** a verified task branch is published
- **THEN** the existing GitHub PR/check semantics are invoked through the provider boundary
- **AND** existing publication safety remains authoritative.

### Requirement: CI provider workflows remain thin orchestration

Provider-specific CI configuration SHALL invoke repository-owned build, test and verification entrypoints rather than duplicating portable engineering logic in GitHub Actions or GitLab CI.

#### Scenario: Same repository checks run locally and in GitLab CI
- **WHEN** the client-like sandbox runs required checks locally and then through GitLab CI
- **THEN** both paths invoke the same repository-owned commands
- **AND** the GitLab workflow contains provider orchestration rather than a second implementation of test/verification policy.

### Requirement: GitLab publication success is bound to the exact task HEAD

For the bounded GitLab adapter, successful publication SHALL prove that the selected merge request identifies the current task branch and exact validated task HEAD. Branch-name equality alone SHALL NOT be sufficient when the provider reports a different head SHA.

#### Scenario: Merge request head matches current task HEAD
- **GIVEN** the task branch was pushed successfully
- **WHEN** the adapter resolves the merge request
- **THEN** it verifies the provider-reported source branch/target branch and head SHA against the current local published HEAD before accepting MR identity.

#### Scenario: Merge request head does not match
- **WHEN** the merge request or pipeline evidence refers to a different head SHA than the current validated task HEAD
- **THEN** publication returns a non-success terminal result with an actionable mismatch diagnostic
- **AND** `finish_task.py` does not report completion.

### Requirement: GitLab CI must be terminal green for the exact published HEAD

The bounded GitLab publication adapter SHALL return success only after CI evidence for the exact published task HEAD is in the configured accepted green terminal state. Failed, canceled, skipped-without-policy, pending, running, missing, unreadable, or head-ambiguous pipeline evidence SHALL fail closed or return an explicit resumable not-ready result.

#### Scenario: Exact-head pipeline is successful
- **WHEN** the exact published HEAD has a provider pipeline with accepted terminal status `success`
- **THEN** the adapter reports the MR as ready for human merge/acceptance
- **AND** exits successfully without performing the human merge.

#### Scenario: Pipeline is still running
- **WHEN** the exact-head pipeline is pending or running
- **THEN** the adapter does not claim completion
- **AND** returns an actionable resumable result instructing the caller to rerun status/finish after CI reaches a terminal state.

#### Scenario: Pipeline failed or cannot be proven
- **WHEN** the exact-head pipeline is failed, canceled, absent, unreadable, or cannot be associated unambiguously with the current HEAD
- **THEN** the adapter exits non-zero
- **AND** `finish_task.py` does not emit a generic complete stage.

### Requirement: GitLab handoff remains human-controlled

The bounded GitLab adapter SHALL stop after exact-head green CI and a ready-for-human-acceptance state. It SHALL NOT auto-merge the merge request or deploy production as part of this change.

#### Scenario: CI is green
- **WHEN** exact-head CI succeeds
- **THEN** output clearly identifies the merge request and ready-for-human-acceptance state
- **AND** no merge or production deployment API is invoked.

