# managed-rollout Specification

## Purpose
Define the managed rollout registry, release ownership, and recovery controls for downstream adoption.

## Requirements

### Requirement: Guarded recopy permits only its deterministic task-intake migration

When managed rollout adds or normalizes the platform-owned marked task-intake reference in a project-owned root `AGENTS.md`, guarded Copier recopy SHALL accept that exact deterministic migration while continuing to reject any other change to protected project-owned paths.

#### Scenario: A mature downstream project receives the missing migration reference

- **GIVEN** a project-owned root `AGENTS.md` without the marked task-intake reference
- **WHEN** managed rollout performs guarded Copier recopy and its deterministic migration
- **THEN** rollout does not report project-owned drift solely for that marked insertion
- **AND** the project-owned rules remain otherwise unchanged

#### Scenario: Protected rules change outside the migration

- **GIVEN** a protected project-owned path changes beyond the deterministic migration
- **WHEN** guarded recopy comparison runs
- **THEN** rollout fails closed
- **AND** reports the affected protected path

### Requirement: Task-intake migration is idempotent

Managed rollout SHALL leave exactly one canonical marked task-intake reference after repeated successful runs and SHALL NOT duplicate or rewrite project-owned rule content.

#### Scenario: Project is rolled out twice

- **GIVEN** a project already has the canonical marked reference
- **WHEN** managed rollout is repeated
- **THEN** the reference remains singular
- **AND** guarded protected-path comparison still detects unrelated drift

### Requirement: Supersession reconciliation runs with its own operator-registry access in every job that calls it

Every workflow job that invokes `rollout_supersession.py reconcile` SHALL independently obtain read access to the operator-owned managed-project registry before calling it, since GitHub Actions job outputs do not carry a prior job's checked-out working tree across separate runners.

#### Scenario: A rollout or maintenance job runs on a separate runner from its planning job

- **GIVEN** a workflow's `plan` job checks out the private operator registry for its own matrix-building use
- **AND** a later job in the same workflow needs to call `rollout_supersession.py reconcile`
- **WHEN** that later job runs on its own fresh runner
- **THEN** it checks out the operator registry itself and passes `--registry` to the reconcile call

#### Scenario: Reconcile is invoked without a registry

- **WHEN** `rollout_supersession.py reconcile` is invoked without `--registry`
- **THEN** it fails closed with a missing-argument error rather than silently skipping the managed/base-branch safety check

### Requirement: Rollout to a runner-aware release migrates or stops on a hand-edited platform runner

When a managed rollout targets a release whose template asks `ci_runner` for a GitHub project whose recorded answers lack `ci_runner`, the rollout SHALL inspect the committed `runs-on` of the platform-rendered `platform-ci` and `provision` jobs before updating, for both `harness_mode=platform` and `harness_mode=project`.

#### Scenario: Simple self-hosted runner is migrated in platform mode
- **GIVEN** a project on an earlier release whose `platform-ci` and `provision` `runs-on` were hand-edited to the same simple label(s), and whose workflows otherwise equal the baseline render
- **WHEN** the rollout targets a release that asks `ci_runner`
- **THEN** the rollout records `ci_runner: self-hosted` and `ci_runner_labels` with those labels
- **AND** the updated workflows run on those labels and include the shared-workspace repair step before `platform_doctor`
- **AND** no `.rej` file remains and `platform_doctor` passes

#### Scenario: Simple self-hosted runner is migrated in project mode
- **GIVEN** the same project with `harness_mode=project`
- **WHEN** the rollout runs
- **THEN** the outcome is identical to platform mode, without guarded recopy

#### Scenario: Customization the rollout cannot prove is not migrated
- **GIVEN** a hand-edited runner that is an expression, a group/labels mapping, differs between the two jobs, or comes with other edits to the same workflow file
- **WHEN** the rollout runs
- **THEN** it stops with a message naming the repository, the file, what was found and one next action
- **AND** no `ci_runner: github-hosted` answer is recorded and the default branch is unchanged

#### Scenario: Project without runner edits needs nothing new
- **GIVEN** a project whose `runs-on` are `ubuntu-latest`
- **WHEN** the rollout runs
- **THEN** it completes through the ordinary update with no migration commit and no manual step

#### Scenario: Older target and GitLab are unaffected
- **WHEN** the target template does not ask `ci_runner`, or the project is a GitLab project
- **THEN** the runner preflight does not run and no answer or file is changed by it

#### Scenario: Migration path is documented
- **WHEN** a maintainer reads `docs/managed-rollout.md`
- **THEN** it explains the automatic migration, each stop condition and the action to take after a stop

### Requirement: A runner-aware rollout either carries the current runner or stops before publishing

When a managed rollout targets a release whose template asks `ci_runner` for a GitHub project whose recorded answers lack `ci_runner`, the rollout SHALL either carry the project's current runner into the recorded Copier answers and produce a result that passes `platform_doctor` with no unresolved `.rej`, or stop before publishing anything, with a message naming the repository, the file and the exact next action.

#### Scenario: Runner is carried or the rollout stops

- **GIVEN** a GitHub project whose recorded answers lack `ci_runner`
- **WHEN** a managed rollout targets a release whose template asks `ci_runner`
- **THEN** the rollout either carries the project's current runner into the recorded Copier answers with a result that passes `platform_doctor` and no unresolved `.rej`
- **AND** otherwise it stops before publishing anything with a message naming the repository, the file and the exact next action

### Requirement: A runner-aware rollout records github-hosted only for ubuntu-latest runners

When a managed rollout targets a release whose template asks `ci_runner` for a GitHub project whose recorded answers lack `ci_runner`, the rollout SHALL NOT record `ci_runner=github-hosted` for a project whose committed runner is not `ubuntu-latest`.

#### Scenario: Committed runner is not ubuntu-latest

- **GIVEN** a GitHub project whose recorded answers lack `ci_runner` and whose committed runner is not `ubuntu-latest`
- **WHEN** a managed rollout targets a release whose template asks `ci_runner`
- **THEN** the rollout does not record `ci_runner=github-hosted`

### Requirement: A runner-aware rollout of an ubuntu-latest project adds no manual step

When a managed rollout targets a release whose template asks `ci_runner` for a GitHub project whose recorded answers lack `ci_runner`, a project whose committed runners are all `ubuntu-latest` SHALL update with no new manual step.

#### Scenario: All committed runners are ubuntu-latest

- **GIVEN** a GitHub project whose recorded answers lack `ci_runner` and whose committed runners are all `ubuntu-latest`
- **WHEN** a managed rollout targets a release whose template asks `ci_runner`
- **THEN** the project updates with no new manual step

### Requirement: A runner-aware rollout never changes the protected default branch

When a managed rollout targets a release whose template asks `ci_runner` for a GitHub project whose recorded answers lack `ci_runner`, the protected default branch SHALL NOT change in any case.

#### Scenario: Protected default branch is untouched

- **GIVEN** a GitHub project whose recorded answers lack `ci_runner`
- **WHEN** a managed rollout targets a release whose template asks `ci_runner`, whatever its outcome
- **THEN** the protected default branch does not change
