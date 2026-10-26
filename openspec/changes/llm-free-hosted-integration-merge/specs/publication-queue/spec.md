## ADDED Requirements

### Requirement: A clean merge after a failed derived merge is integrated without a writer

When integration of a candidate fails on the `integration` gate and a trial merge of the candidate head with current main has no conflict, the coordinator SHALL offer an `integration-merge` job instead of an integration-repair job. The job SHALL name no provider and no route, SHALL count against the same bounded integration-repair attempts, and SHALL record on the candidate that the round is merge-only so a re-published job and a recovered push keep the kind. Its executor SHALL merge current main in a disposable harness checkout without starting any writer, validate the result like an integration repair, push it under the claim and advance the candidate like an integration repair. When the merge conflicts or a required check is red at execution time, the job SHALL fail naming the conflicts and the coordinator SHALL offer an integration-repair job in the next attempt, never a writer inside the integration-merge job. A conflict, a red required check or a failed GitHub branch update SHALL keep offering integration repair as before.

#### Scenario: Derived merge failed but the plain merge is clean
- **GIVEN** a candidate whose derived merge failed for a candidate reason and whose trial merge with main has no conflict
- **WHEN** the coordinator handles the integration failure
- **THEN** it records `integration-repair-pending` marked merge-only and publishes an `integration-merge` job without providers

#### Scenario: Integration merge succeeds
- **WHEN** a worker runs the claimed `integration-merge` job and the merge is clean
- **THEN** the harness pushes the merge of main without any writer and the candidate advances as after an integration repair

#### Scenario: Integration merge meets a conflict
- **WHEN** the merge of main conflicts at execution time
- **THEN** the job fails naming the conflicting paths and starts no writer
- **AND** the next attempt is an integration-repair job, or the candidate is blocked when the bound is spent

#### Scenario: Real conflict keeps integration repair
- **WHEN** the trial merge of the candidate with main conflicts in an ordinary file
- **THEN** the coordinator offers an integration-repair job as before

## MODIFIED Requirements

### Requirement: A writer-needing repair is escalated to the operator

A candidate that enters `repair-pending` or `integration-repair-pending` needs a writer, and no writer SHALL be launched automatically for it. The coordinator SHALL post one human-readable attention comment per exact repair round on the pull request, titled as a needed repair of that pull request, naming the reason, the head, the attempts and the worker command an operator runs to execute the published job. The published job SHALL stay claimable. An `integration-merge` round needs no writer and SHALL NOT post this comment. A lost attention comment SHALL be posted on the next observation of the same round; an unchanged round SHALL NOT post another.

#### Scenario: Integration repair is offered
- **WHEN** a real conflict makes the coordinator offer an integration-repair job for PR #N
- **THEN** PR #N gets one "Repair needed" attention comment with the conflict, the head and the `work-next --kinds integration-repair` command

#### Scenario: Review findings need repair
- **WHEN** independent review moves PR #N to `repair-pending`
- **THEN** PR #N gets one "Repair needed" attention comment naming the `repair` command

#### Scenario: Same round observed again
- **WHEN** the coordinator observes the same repair round again
- **THEN** no second attention comment is posted unless the first one is missing

#### Scenario: Integration merge needs no repair comment
- **WHEN** the coordinator offers an `integration-merge` job for PR #N
- **THEN** no "Repair needed" attention comment is posted for that round
