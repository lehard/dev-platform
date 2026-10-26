## MODIFIED Requirements

### Requirement: Declared generated files are regenerated on integration

When preparing a candidate on current main, the coordinator SHALL treat files that its default branch declares generated in the committed check configuration as derived. When a merge of current main conflicts only in declared generated files and archive-derived current-spec paths, or a declared generated file changed both in main since the admission base and in the candidate, the coordinator SHALL merge in a disposable checkout, re-derive archive-derived specs as before, regenerate each such file by running its declared command from the default-branch code over the merged tree, and push the result as a recorded coordinator update whose parents are the claimed head and main. Required checks SHALL run on that head and gate the merge unchanged. A remaining conflict, a conflict in any other file, or a regeneration that fails on the merged tree while the same command succeeds on a pristine checkout of main SHALL become integration repair. A failure of the coordinator's own environment — the OpenSpec CLI is unavailable, a declared regeneration command cannot start, or the command fails on the pristine checkout of main as well — SHALL NOT become integration repair: the coordinator SHALL leave the candidate's state unchanged, publish no job, still evaluate the other candidates, and end the run as a failure naming each cause. The coordinator SHALL NOT execute pull-request-controlled code while holding the App token. Recovery of an unrecorded update SHALL accept a merge that differs from both parents only in archive-derived specs and declared generated files.

#### Scenario: Candidate conflicts with main only in the generated manifest
- **GIVEN** a ready candidate and a main that both changed neighbouring entries of the declared platform manifest
- **WHEN** the coordinator prepares the candidate
- **THEN** it pushes a coordinator merge with a regenerated manifest and records the update
- **AND** required checks run on that head, and after merge `generate_platform_manifest.py --check` passes on main

#### Scenario: Conflict in an ordinary file
- **GIVEN** a ready candidate whose merge with main conflicts in a file that is neither generated nor archive-derived
- **WHEN** the coordinator prepares the candidate
- **THEN** it offers integration repair as before and pushes nothing

#### Scenario: Regeneration fails
- **GIVEN** a candidate whose only conflict is in a declared generated file
- **WHEN** the declared regeneration command fails on the merged tree and succeeds on a pristine checkout of main
- **THEN** the coordinator offers integration repair naming the failure and pushes nothing

#### Scenario: Regeneration environment is missing
- **GIVEN** a candidate whose only conflict is in a declared generated file
- **WHEN** the declared regeneration command fails on a pristine checkout of main as well, for example because a dependency is not installed on the runner
- **THEN** the coordinator records nothing on the candidate and publishes no integration-repair job
- **AND** it still evaluates the other candidates and the run fails naming the command and the failure

## ADDED Requirements

### Requirement: A writer-needing repair is escalated to the operator

A candidate that enters `repair-pending` or `integration-repair-pending` needs a writer, and no writer SHALL be launched automatically for it. The coordinator SHALL post one human-readable attention comment per exact repair round on the pull request, titled as a needed repair of that pull request, naming the reason, the head, the attempts and the worker command an operator runs to execute the published job. The published job SHALL stay claimable. A lost attention comment SHALL be posted on the next observation of the same round; an unchanged round SHALL NOT post another.

#### Scenario: Integration repair is offered
- **WHEN** a real conflict makes the coordinator offer an integration-repair job for PR #N
- **THEN** PR #N gets one "Repair needed" attention comment with the conflict, the head and the `work-next --kinds integration-repair` command

#### Scenario: Review findings need repair
- **WHEN** independent review moves PR #N to `repair-pending`
- **THEN** PR #N gets one "Repair needed" attention comment naming the `repair` command

#### Scenario: Same round observed again
- **WHEN** the coordinator observes the same repair round again
- **THEN** no second attention comment is posted unless the first one is missing
