## ADDED Requirements

### Requirement: Rollout to a runner-aware release migrates or stops on a hand-edited platform runner

When a managed rollout targets a release whose template asks `ci_runner` for a GitHub project whose recorded answers lack `ci_runner`, the rollout SHALL inspect the committed `runs-on` of the platform-rendered `platform-ci` and `provision` jobs before updating, for both `harness_mode=platform` and `harness_mode=project`. It SHALL either carry the project's current runner into the recorded Copier answers and produce a result that passes `platform_doctor` with no unresolved `.rej`, or stop before publishing anything, with a message naming the repository, the file and the exact next action. It SHALL NOT record `ci_runner=github-hosted` for a project whose committed runner is not `ubuntu-latest`. A project whose committed runners are all `ubuntu-latest` SHALL update with no new manual step. The protected default branch SHALL NOT change in any case.

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
