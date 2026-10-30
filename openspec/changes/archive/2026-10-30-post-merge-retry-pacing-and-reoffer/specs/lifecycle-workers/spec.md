## MODIFIED Requirements

### Requirement: Post-merge lifecycle work runs on the operator Mac on a schedule

The platform SHALL provide a scheduled operator-Mac runner that executes the existing retrospective, terminal-reconciliation and cleanup jobs through `lifecycle_workers.py work-next --run` and its claim/result protocol, with no queue, claim format or state store of its own. One scheduled round SHALL repeat `work-next` until it reports idle or a bound is reached: a maximum number of runs, a maximum duration, the first failed run, or a GitHub REST remainder below a required threshold. The remainder SHALL be read without spending the counted limit before the round and between runs. Within one round, a PR whose post-merge run ended `blocked` or `failed` SHALL be excluded from every further `work-next` run of that round, so an obligation is attempted at most once per round while other PRs are still served. Before claiming any job the round SHALL verify that the process-check tool the cleanup job needs resolves on the runner's PATH, and SHALL fail explicitly naming it otherwise. Every round and every `work-next` run SHALL be recorded in an append-only run journal with its outcome. Missing or invalid configuration, credentials, an unreadable rate limit or an unwritable journal SHALL fail the round explicitly. The runner SHALL NOT open its own attention path: a spent post-merge obligation stays reported by the existing attention on the merged PR and in the lifecycle overview.

#### Scenario: Chain caught up in one round
- **GIVEN** merged PRs whose retrospective, terminal-reconciliation and cleanup are pending
- **WHEN** a round runs
- **THEN** it repeats `work-next` so each next job of the chain is claimed and executed until `work-next` reports idle or a bound is reached
- **AND** each run appears in the journal with PR, kind, status, outcome and duration

#### Scenario: Low REST remainder
- **WHEN** the GitHub REST remainder is below the threshold at the start of a round or between runs
- **THEN** the round claims nothing further and records a skip with the remainder and reset time
- **AND** the process exits successfully

#### Scenario: Two rounds overlap
- **WHEN** a round starts while another round holds the single-instance lock
- **THEN** it records `previous round still running` and runs nothing

#### Scenario: Round killed or machine rebooted
- **WHEN** a round dies after claiming a job
- **THEN** no result is published for it and its claim expires by the claim protocol
- **AND** the next round journals the interrupted round and the job becomes claimable again without a duplicate valid claim

#### Scenario: A job keeps failing
- **WHEN** a post-merge job fails in successive rounds until the platform attempt limit is spent
- **THEN** the existing post-merge attention is posted on the merged PR and shown by the lifecycle overview
- **AND** the runner never retries within a round or with another strategy

#### Scenario: Blocked obligation waits for the next round
- **GIVEN** a round in which PR A's cleanup ends `blocked` and PR B has a pending post-merge job
- **WHEN** the round continues
- **THEN** further `work-next` runs of that round exclude PR A and PR B's job is still claimed and executed
- **AND** PR A's next attempt happens in a later round

#### Scenario: Process-check tool missing
- **WHEN** `lsof` does not resolve on the runner's PATH
- **THEN** the round ends `failed` naming the tool before any job is claimed and no attempt of any obligation is spent

#### Scenario: Missing configuration
- **WHEN** a required argument, the `gh` credential or the journal directory is missing or invalid
- **THEN** the runner exits non-zero naming it and runs nothing

## ADDED Requirements

### Requirement: Post-merge environment defects spend no obligation attempt

When a claimed post-merge job cannot run because the executing environment is defective — the cleanup's active-process check is unavailable — the executor SHALL NOT post a `blocked` or `failed` result receipt for the job. It SHALL release its claim and `work-next` SHALL exit non-zero naming the defect, so the attempt counter of the obligation is unchanged and the caller fails visibly. A refusal that is a property of the obligation (an active board claim, a dirty or mismatched worktree, local commits outside the merged PR) SHALL remain a `blocked` outcome. A cleanup that finds no worktree of the task branch SHALL complete the obligation with the outcome `already-clean`.

#### Scenario: Process check unavailable after claim
- **WHEN** a claimed cleanup job meets `process-check-unavailable`
- **THEN** no result receipt is posted for that job, its claim is released and `work-next` exits non-zero naming the defect
- **AND** the next derivation offers the same attempt again

#### Scenario: Worktree already gone
- **WHEN** a cleanup job runs and no worktree of the task branch exists
- **THEN** the job posts `already-clean` and the cleanup obligation is complete

### Requirement: An exhausted post-merge obligation can be re-offered with a fresh budget

Post-merge derivation SHALL read an operator re-offer sequence from the merged candidate's latest exact-head coordinator record (`attempts["post-merge-reoffers"]`, with the re-offer event carried in its `next_job`). With a sequence greater than zero, an obligation SHALL count as complete when any trusted outcome of any attempt under any earlier or current sequence completed it; an incomplete obligation SHALL be offered under job ids of the current sequence with attempts `0..MAX_POST_MERGE_ATTEMPTS-1`, giving a fresh attempt budget. A record whose sequence has no matching re-offer event SHALL be rejected as malformed. Exhaustion under the current sequence SHALL be reported as before.

#### Scenario: Re-offered cleanup
- **GIVEN** a merged PR whose retrospective and terminal reconciliation completed and whose cleanup exhausted its attempts
- **WHEN** a re-offer record with sequence 1 is published
- **THEN** the next post-merge job is cleanup attempt 0 under the sequence-1 job id
- **AND** retrospective and terminal reconciliation are not offered again
