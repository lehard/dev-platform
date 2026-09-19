## ADDED Requirements

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
