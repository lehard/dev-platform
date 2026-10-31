## MODIFIED Requirements

### Requirement: Lifecycle overview is a read-only projection of GitHub state

The platform SHALL provide a read-only lifecycle overview that, from GitHub alone (PR heads, checks, labels, versioned marker comments, claim and result receipts, Requirement Issues and Project statuses), shows a summary of all open lifecycle work and a drill-down for one PR or one Requirement.

#### Scenario: Cold session asks for the state of all work
- **WHEN** the overview is run from a fresh checkout with only repository access
- **THEN** it lists every open lifecycle candidate and active Requirement with stage, current attempt/round, source links and next operation
- **AND** it performs no GitHub write

#### Scenario: Candidate set matches the workers
- **WHEN** a merged candidate has an open post-merge obligation inside the workers' discovery bound
- **THEN** the overview lists it
- **AND** a merge outside that bound is reported as outside the stated bound rather than omitted silently

#### Scenario: Required source is unreadable
- **WHEN** a PR's comments, checks or a Requirement's progress cannot be read or contradict each other
- **THEN** that item is reported `unknown` naming the failing source
- **AND** it is never reported as healthy or delivering

#### Scenario: Repeated overview without GitHub changes
- **GIVEN** a warm read cache and no change on GitHub since the previous overview
- **WHEN** the overview is run again
- **THEN** its result equals a cache-free read
- **AND** it spends only conditional requests that return 304 plus a bounded number of counted requests

#### Scenario: Change after the previous read is reflected
- **GIVEN** a warm read cache
- **WHEN** a PR comment is added or edited, or the PR state changes, after the previous read
- **THEN** the next overview reflects the change and a 304 never hides it

#### Scenario: Corrupt cache
- **GIVEN** a cache file that is unparsable, has an unknown version or an entry whose digest does not match
- **WHEN** the overview is run
- **THEN** it fails with an error naming the cache file and the reset command
- **AND** it does not silently re-read everything instead

#### Scenario: Deleted or stale cache
- **WHEN** the cache file is absent or an entry is merely out of date
- **THEN** the overview reads from GitHub without error and returns the same result

### Requirement: Delivery stages and the stage chain are distinguished for humans

The overview SHALL classify each item into `in-development` (no handed-off PR or visible technical child yet), `handed-off`, `delivering`, `merged-open-obligations`, `closed`, `needs-intervention` or `unknown`.

#### Scenario: Merged but not done
- **GIVEN** the PR is merged and terminal reconciliation or cleanup is still open
- **WHEN** the overview is shown
- **THEN** the item is `merged-open-obligations` naming the open step
- **AND** the parent Requirement is shown separately as not `Done`

#### Scenario: Queued label hides a review claim
- **GIVEN** a PR labelled `publication:queued` whose latest record is `reviewing` with a live claim
- **WHEN** the overview is shown
- **THEN** the stage is `delivering` at review, not queued for merge

### Requirement: Exceptions are detected from observable fields and named

The overview SHALL detect and name each of: an unclaimed `next_job` older than the configured threshold, an expired claim without a completing result, a claim recorded on an earlier head than the PR's current head or checks bound to another head, an unavailable provider or auth with its recorded limitation, an operational escalation, a finding-level escalation including exhausted repair or review rounds, and an exhausted post-merge obligation. Each finding SHALL cite its evidence.

#### Scenario: Job published but not picked up
- **GIVEN** a `next_job` with no claim whose record is older than the threshold
- **WHEN** the overview is shown
- **THEN** the item is `needs-intervention` with finding `unclaimed-next-job` and the job age

#### Scenario: Claim expired
- **GIVEN** the latest claim for the exact job expired without a completing result
- **WHEN** the overview is shown
- **THEN** the finding `expired-claim` names the worker, provider and expiry

#### Scenario: Head moved
- **WHEN** the latest claim is recorded on an earlier head than the PR's current head
- **THEN** the finding names the stale head and states that the result will not be applied

#### Scenario: Provider unavailable
- **WHEN** a blocked-retryable review or repair, or an `unavailable` result, records an unavailable provider
- **THEN** the finding names the provider and the recorded limitation

#### Scenario: Missing threshold setting
- **WHEN** `[chat_coordinator] unclaimed_job_after_minutes` is absent or not a positive integer
- **THEN** the overview exits non-zero naming that key and prints no classification

### Requirement: Permitted actions come from the operator command eligibility

The overview SHALL list as permitted only actions that the existing operator commands (`resume`, `switch-provider`, `reoffer-post-merge`) would accept for the item, computed by the same state, job-kind and claim eligibility function those commands use, and SHALL print the exact command including the PR's current head as `--expected-head`.

#### Scenario: Operational repair failure
- **GIVEN** a candidate escalated after a failed repair writer
- **WHEN** the overview is shown
- **THEN** `resume` is listed with the exact command and head

#### Scenario: Exhausted repair rounds
- **GIVEN** a candidate escalated for exhausted repair rounds
- **WHEN** the overview is shown
- **THEN** no action is listed and the text names pushing a fix, recording a disposition or closing the PR

#### Scenario: Live claim
- **WHEN** the job holds an unexpired claim
- **THEN** no re-offer is listed and the claim holder and expiry are shown

#### Scenario: Exhausted post-merge obligation
- **GIVEN** a merged PR whose cleanup obligation exhausted its attempts
- **WHEN** the overview is shown or the attention comment is posted
- **THEN** the exact `reoffer-post-merge` command with the merged head is listed, fix the named cause first

#### Scenario: Eligibility agrees with the command
- **WHEN** any candidate state is evaluated
- **THEN** the overview lists an action if and only if the operator command accepts it for that state

### Requirement: Operator decisions are head-bound and attributed

`publication_queue.py resume` and `switch-provider` SHALL accept `--expected-head` and, when it differs from the PR's current head, SHALL refuse before any write.

#### Scenario: Head changed between report and decision
- **WHEN** the coordinator or user continues and the PR head differs from the head in the report
- **THEN** the command refuses naming both heads and nothing is written

#### Scenario: Attributed resume
- **WHEN** an operator resumes an operationally escalated candidate
- **THEN** the candidate record shows reason, actor, the given via, PR and exact head
- **AND** the same round is offered again without spending budget

### Requirement: Escalations leave one human-readable GitHub indication

When the coordinator first publishes `blocked-escalation` for an exact head and reason, and when it first observes an exhausted post-merge obligation, it SHALL post one human-readable PR comment stating the reason, evidence links and the permitted actions or the human decision needed, idempotent per PR, head, state, red gate and attempt counters of that escalation round.

#### Scenario: Escalation
- **WHEN** a candidate transitions to `blocked-escalation`
- **THEN** exactly one attention comment exists for that head and reason, even after a repeated run

#### Scenario: Normal progress
- **WHEN** a candidate advances through review, repair and merge without escalation
- **THEN** no attention comment is posted

#### Scenario: Posting fails
- **WHEN** the comment cannot be posted
- **THEN** the already-published transition stands
- **AND** the run exits non-zero stating the failure

### Requirement: Chat coordinator role is a repository-defined delivery orchestrator

The repository SHALL define the chat coordinator role in `docs/engineering/chat-coordinator.md`, reachable from the `AGENTS.md` concern table, as the delivery orchestrator.

#### Scenario: Role assigned in a new session
- **WHEN** the user assigns a new session the chat coordinator role and asks what is going on
- **THEN** the session reads the role document, runs the overview and answers with stages, blockers and next steps with links

#### Scenario: Routine worker run after a handoff
- **WHEN** a developer hands off a PR and its review job is unclaimed
- **THEN** the coordinator launches the review worker without asking the owner

#### Scenario: Material finding
- **WHEN** an item is escalated for a material finding
- **THEN** the session shows the finding with options and a recommendation and asks the owner for the decision
- **AND** it does not run `resume`

### Requirement: Overview names why an open candidate is idle

For every open, unmerged candidate that has no executing claim, the lifecycle overview SHALL state in plain language what the candidate waits for and who or what moves it next, derived only from the candidate's observable state, offered job, claim, attempt counters and gate evidence.

#### Scenario: Job executed only on the local operator node

- **GIVEN** an open candidate offering an unclaimed `integration-repair` job
- **WHEN** the overview is rendered
- **THEN** it states the candidate waits for that job, which only an operator-run local macOS node executes, and names the operator as the mover

#### Scenario: Waiting for a developer

- **GIVEN** an open PR with no trusted lifecycle record
- **THEN** the overview states it waits for the developer to hand it off

#### Scenario: Waiting for the queue

- **GIVEN** an open candidate in `ready`
- **THEN** the overview states it waits for the publication queue to integrate it

#### Scenario: Attempt limit exhausted

- **GIVEN** an escalated candidate whose repair attempts reached the round limit
- **THEN** the overview states the limit was exhausted and that a human decision is the mover

#### Scenario: Reason cannot be established

- **GIVEN** an open candidate whose state matches no known idle rule
- **THEN** the overview reports "idle reason unknown" with the state, not an empty or healthy indication

## ADDED Requirements

### Requirement: The lifecycle overview writes nothing to GitHub

The lifecycle overview SHALL write no GitHub comment, label or status and SHALL treat GitHub as its only source of truth.

#### Scenario: The lifecycle overview is produced

- **WHEN** the lifecycle overview is produced
- **THEN** it writes no GitHub comment, label or status
- **AND** it treats GitHub as its only source of truth

### Requirement: The lifecycle overview read cache is disposable

The lifecycle overview MAY keep one local, disposable read cache of GitHub GET responses, revalidated by ETag on every read, and SHALL produce the same overview with that cache present, stale or deleted.

#### Scenario: The lifecycle overview read cache is stale or deleted

- **GIVEN** the lifecycle overview keeps a local read cache of GitHub GET responses
- **WHEN** the overview is produced with that cache present, stale or deleted
- **THEN** every read is revalidated by ETag
- **AND** the overview is the same in each case

### Requirement: A corrupt lifecycle overview read cache fails explicitly

A corrupt or inconsistent lifecycle overview read cache SHALL fail explicitly naming the cache file and how to reset it, and SHALL NOT be replaced by a silent full re-read.

#### Scenario: The lifecycle overview read cache is corrupt

- **GIVEN** the lifecycle overview read cache is corrupt or inconsistent
- **WHEN** the overview is produced
- **THEN** it fails explicitly naming the cache file and how to reset it
- **AND** it does not silently re-read everything instead

### Requirement: The lifecycle overview cites the source of every fact

The lifecycle overview SHALL cite for every reported fact the GitHub object or record field it came from.

#### Scenario: The lifecycle overview reports a fact

- **WHEN** the lifecycle overview reports a fact
- **THEN** it cites the GitHub object or record field the fact came from

### Requirement: The lifecycle overview considers the lifecycle workers' candidate set

The lifecycle overview SHALL consider exactly the candidate set that lifecycle workers consider and SHALL state any bound of that set.

#### Scenario: The lifecycle overview selects candidates

- **WHEN** the lifecycle overview selects the candidates it reports
- **THEN** it considers exactly the candidate set that lifecycle workers consider
- **AND** it states any bound of that set

### Requirement: A new chat session obtains an equivalent lifecycle overview

A new, unrelated chat session SHALL obtain an equivalent lifecycle overview with no earlier conversation.

#### Scenario: A new chat session asks for the lifecycle overview

- **GIVEN** a new, unrelated chat session with no earlier conversation
- **WHEN** it requests the lifecycle overview
- **THEN** it obtains an equivalent overview

### Requirement: The overview shows the stage chain for one PR or Requirement

For one PR or Requirement the overview SHALL show the chain review, repair, repeat review, finalization, integration, retrospective, terminal reconciliation and cleanup with the current attempt/round and the step reached.

#### Scenario: The overview drills down into one PR or Requirement

- **WHEN** the overview shows one PR or Requirement
- **THEN** it shows the chain review, repair, repeat review, finalization, integration, retrospective, terminal reconciliation and cleanup
- **AND** it shows the current attempt/round and the step reached

### Requirement: A merged PR with open obligations is distinct from closed

The overview SHALL show a merged PR whose Requirement is not `Done`, or which still has a post-merge obligation, as `merged-open-obligations`, distinct from `closed`.

#### Scenario: A merged PR still has open obligations

- **GIVEN** a merged PR whose Requirement is not `Done`, or which still has a post-merge obligation
- **WHEN** the overview classifies it
- **THEN** it is shown as `merged-open-obligations`, distinct from `closed`

### Requirement: A waiting queue state is not presented as delivered

A successful workflow run whose queue state is `waiting` SHALL NOT be presented as delivered.

#### Scenario: A successful workflow run leaves the queue waiting

- **GIVEN** a successful workflow run whose queue state is `waiting`
- **WHEN** the run is presented
- **THEN** it is not presented as delivered

### Requirement: The unclaimed-job threshold comes from required configuration

The unclaimed-job threshold SHALL come from the required `[chat_coordinator] unclaimed_job_after_minutes` setting; a missing or invalid setting SHALL fail the overview naming the key and SHALL NOT be replaced by a default.

#### Scenario: The unclaimed-job threshold setting is missing or invalid

- **GIVEN** the `[chat_coordinator] unclaimed_job_after_minutes` setting is missing or invalid
- **WHEN** the overview runs
- **THEN** it fails naming the key
- **AND** no default threshold is used

### Requirement: An exhausted post-merge obligation without a live claim permits reoffer-post-merge

For a merged PR whose post-merge obligation is exhausted and holds no live claim, the overview SHALL list `reoffer-post-merge`.

#### Scenario: A merged PR has an exhausted post-merge obligation

- **GIVEN** a merged PR whose post-merge obligation is exhausted and holds no live claim
- **WHEN** the overview lists permitted actions for it
- **THEN** it lists `reoffer-post-merge`

### Requirement: Items needing a human decision list no permitted action

For a finding-level escalation, a rejected review, an exhausted round, a disputed disposition, a live claim, a closed PR, a merged PR without an exhausted post-merge obligation, or a needed OpenSpec or business decision, the overview SHALL list no action and SHALL show the finding or basis and the human decisions available.

#### Scenario: An item holds a finding-level escalation

- **GIVEN** an item with a finding-level escalation
- **WHEN** the overview lists permitted actions for it
- **THEN** it lists no action
- **AND** it shows the finding or basis and the human decisions available

### Requirement: The overview suggests no substitute for a decision it cannot apply safely

Where the supported contract cannot apply a decision safely the overview SHALL say so and SHALL NOT suggest a substitute.

#### Scenario: The supported contract cannot apply a decision safely

- **GIVEN** the supported contract cannot apply a decision safely
- **WHEN** the overview reports the item
- **THEN** it says so
- **AND** it suggests no substitute

### Requirement: Every re-offer records its reason, actor and head

Every re-offer SHALL record, in the existing candidate record, the reason, the acting authenticated GitHub identity, the `via` label when one is given, the PR and the exact head. An actor that cannot be resolved SHALL fail the command.

#### Scenario: A re-offer is recorded

- **WHEN** a re-offer is made
- **THEN** the existing candidate record holds the reason, the acting authenticated GitHub identity, the `via` label when one is given, the PR and the exact head

#### Scenario: The re-offer actor cannot be resolved

- **WHEN** the acting identity of a re-offer cannot be resolved
- **THEN** the command fails

### Requirement: The chat coordinator runs operator recovery commands only within its authority

The chat coordinator MAY run `publication_queue.py resume` and `switch-provider` for routine recovery after a technical failure once its cause is understood, without a per-PR owner decision; for material findings, exhausted review or repair rounds and disputed rejections or dispositions the chat coordinator SHALL run them only after an explicit owner decision naming the PR.

#### Scenario: The chat coordinator recovers a technical failure

- **GIVEN** a technical failure whose cause is understood
- **WHEN** the chat coordinator runs `publication_queue.py resume` for routine recovery
- **THEN** no per-PR owner decision is needed

#### Scenario: The chat coordinator meets a material finding

- **GIVEN** a candidate with a material finding, exhausted review or repair rounds, or a disputed rejection or disposition
- **WHEN** the chat coordinator considers `publication_queue.py resume` or `switch-provider`
- **THEN** it runs the command only after an explicit owner decision naming the PR

### Requirement: The chat coordinator does not bypass an unexpired claim when deciding

The chat coordinator SHALL NOT bypass an unexpired claim and SHALL report the command result truthfully.

#### Scenario: The chat coordinator runs an operator command

- **WHEN** the chat coordinator runs an operator command
- **THEN** it does not bypass an unexpired claim
- **AND** it reports the command result truthfully

### Requirement: A successful stage posts no escalation comment

A successful stage SHALL post nothing.

#### Scenario: A stage succeeds

- **WHEN** a stage succeeds
- **THEN** no PR comment is posted

### Requirement: A failure to post the escalation comment fails the run

A failure to post the human-readable escalation PR comment SHALL be raised after the transition is published and SHALL fail the run visibly, without a second channel or a swallowed error.

#### Scenario: The escalation comment cannot be posted

- **WHEN** posting the human-readable escalation PR comment fails
- **THEN** the failure is raised after the transition is published
- **AND** the run fails visibly, without a second channel or a swallowed error

### Requirement: Final Requirement closure keeps the existing Requirement Issue close

Final Requirement closure SHALL keep using the existing close of the Requirement Issue.

#### Scenario: A Requirement is finally closed

- **WHEN** a Requirement reaches final closure
- **THEN** the existing close of the Requirement Issue is used

### Requirement: The chat coordinator keeps the backlog roadmap

The chat coordinator SHALL keep the backlog roadmap (what is taken into work and in which order).

#### Scenario: Work is taken from the backlog

- **WHEN** work is taken into work from the backlog
- **THEN** the chat coordinator decides what is taken and in which order

### Requirement: The chat coordinator starts and holds development streams

The chat coordinator SHALL start and hold development streams (at most two code streams unless the owner decides otherwise).

#### Scenario: Two code streams are already held

- **GIVEN** the chat coordinator holds two code streams
- **AND** the owner has not decided otherwise
- **WHEN** another code stream could be started
- **THEN** the chat coordinator does not start it

### Requirement: The chat coordinator drives lifecycle jobs after a developer handoff

After a developer handoff the chat coordinator SHALL launch review, repair and post-merge workers and run LLM-free lifecycle jobs itself until no job remains.

#### Scenario: A developer hands off a candidate

- **WHEN** a developer handoff is admitted
- **THEN** the chat coordinator launches review, repair and post-merge workers
- **AND** it runs LLM-free lifecycle jobs itself until no job remains

### Requirement: The chat coordinator writes no code

The chat coordinator SHALL NOT write code or perform a stream's task.

#### Scenario: A stream's task needs code

- **WHEN** a stream's task needs code written
- **THEN** the chat coordinator does not write it or perform the task

### Requirement: Routine recovery needs no per-PR owner decision

Routine recovery after a technical failure (`resume`, `switch-provider`, `reoffer-post-merge`, `restore-gates`) SHALL need no per-PR owner decision.

#### Scenario: A technical failure is recovered

- **WHEN** routine recovery runs `resume`, `switch-provider`, `reoffer-post-merge` or `restore-gates` after a technical failure
- **THEN** no per-PR owner decision is needed

### Requirement: Material and business decisions remain the owner's

Material review findings, exhausted review or repair rounds, disputed rejections or dispositions, business decisions and OpenSpec changes SHALL remain the owner's decision; the chat coordinator SHALL bring them with options, cost or risk and a recommendation, and where an executor's contract needs the owner's own words it SHALL ask the owner and not supply them.

#### Scenario: A material review finding needs a decision

- **WHEN** a material review finding needs a decision
- **THEN** the owner decides
- **AND** the chat coordinator brings it with options, cost or risk and a recommendation

#### Scenario: An executor's contract needs the owner's own words

- **WHEN** an executor's contract needs the owner's own words
- **THEN** the chat coordinator asks the owner and does not supply them

### Requirement: The chat coordinator states facts only from the overview and GitHub

The chat coordinator SHALL state facts only from the overview and GitHub, and unknown SHALL remain unknown.

#### Scenario: A fact cannot be established

- **WHEN** the overview and GitHub do not establish a fact
- **THEN** the chat coordinator reports it as unknown

### Requirement: The chat coordinator bypasses no protection and touches no other agent's state

The chat coordinator SHALL NOT bypass a live claim, a required check or branch protection, touch another agent's state, worktree or scope, or simulate success.

#### Scenario: A live claim blocks progress

- **WHEN** a live claim, a required check or branch protection blocks progress
- **THEN** the chat coordinator does not bypass it
- **AND** it does not touch another agent's state, worktree or scope or simulate success

### Requirement: The chat coordinator runbook lets a new session reconstruct state

The chat coordinator runbook SHALL let a new session holding only the chat coordinator role reconstruct the current state and next step from GitHub.

#### Scenario: A new session takes the chat coordinator role

- **GIVEN** a new session holding only the chat coordinator role
- **WHEN** it follows the runbook
- **THEN** it reconstructs the current state and next step from GitHub

### Requirement: A candidate with an executing claim reports no idle reason

A candidate with an executing claim SHALL report no idle reason.

#### Scenario: A candidate is being executed

- **GIVEN** a candidate with an executing claim
- **WHEN** the lifecycle overview reports it
- **THEN** no idle reason is reported

### Requirement: An idle reason that cannot be established is reported as unknown

When the idle reason of a candidate cannot be established from the candidate's observable state, offered job, claim, attempt counters and gate evidence, the lifecycle overview SHALL report the idle reason explicitly as unknown, naming the state, and SHALL NOT present the candidate as healthy or leave it unexplained.

#### Scenario: The idle reason cannot be established

- **GIVEN** an idle candidate whose reason cannot be established from its observable state, offered job, claim, attempt counters and gate evidence
- **WHEN** the lifecycle overview reports it
- **THEN** the idle reason is reported as unknown, naming the state
- **AND** the candidate is not presented as healthy or left unexplained

### Requirement: The lifecycle overview does not act on an idle reason

The lifecycle overview SHALL NOT act on the idle reason.

#### Scenario: The lifecycle overview reports an idle reason

- **WHEN** the lifecycle overview reports why a candidate is idle
- **THEN** it takes no action on that reason
