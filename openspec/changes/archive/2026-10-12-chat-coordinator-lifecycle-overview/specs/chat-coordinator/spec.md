# chat-coordinator Specification

## Purpose

Let the owner assign any new Codex or Claude session as the chat coordinator, which reads the true delivery state of Requirements and PRs from GitHub alone, names exceptions with evidence, and applies only the existing validated recovery commands after an explicit owner decision, without a persistent chat, a second state store or a new step on the happy path.

## ADDED Requirements

### Requirement: Lifecycle overview is a read-only projection of GitHub state

The platform SHALL provide a read-only lifecycle overview that, from GitHub alone (PR heads, checks, labels, versioned marker comments, claim and result receipts, Requirement Issues and Project statuses), shows a summary of all open lifecycle work and a drill-down for one PR or one Requirement. It SHALL write no file, comment, label or status, SHALL keep no state store or cache, and SHALL cite for every reported fact the GitHub object or record field it came from. It SHALL consider exactly the candidate set that lifecycle workers consider and SHALL state any bound of that set. A new, unrelated chat session SHALL obtain an equivalent overview with no earlier conversation.

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

### Requirement: Delivery stages and the stage chain are distinguished for humans

The overview SHALL classify each item into `in-development` (no handed-off PR or visible technical child yet), `handed-off`, `delivering`, `merged-open-obligations`, `closed`, `needs-intervention` or `unknown`, and for one PR or Requirement SHALL show the chain review, repair, repeat review, finalization, integration, retrospective, terminal reconciliation and cleanup with the current attempt/round and the step reached. It SHALL show a merged PR whose Requirement is not `Done`, or which still has a post-merge obligation, as `merged-open-obligations`, distinct from `closed`. A successful workflow run whose queue state is `waiting` SHALL NOT be presented as delivered.

#### Scenario: Merged but not done
- **GIVEN** the PR is merged and terminal reconciliation or cleanup is still open
- **WHEN** the overview is shown
- **THEN** the item is `merged-open-obligations` naming the open step
- **AND** the parent Requirement is shown separately as not `Done`

#### Scenario: Queued label hides a review claim
- **GIVEN** a PR labelled `publication:queued` whose latest record is `reviewing` with a live claim
- **WHEN** the overview is shown
- **THEN** the stage is `delivering` at review, not queued for merge

### Requirement: Executor attribution never claims activity from a claim alone

The overview SHALL name a job's executor only from the winning, unexpired, trusted claim (worker identity, provider, expiry, comment reference) and SHALL state `executor activity: not confirmed` unless an explicit read-only signal bound to the exact job id and head confirms it, in which case it SHALL name that source. With no claim it SHALL state `executor not confirmed`. Absence of any signal SHALL be `unknown`, never a healthy executor.

#### Scenario: Live claim without liveness signal
- **WHEN** a job has a valid unexpired claim and no activity signal
- **THEN** the overview prints the claim facts and `executor activity: not confirmed`

#### Scenario: No claim
- **WHEN** a published job has no claim
- **THEN** the overview prints `executor not confirmed` and the job's age

### Requirement: Exceptions are detected from observable fields and named

The overview SHALL detect and name each of: an unclaimed `next_job` older than the configured threshold, an expired claim without a completing result, a claim recorded on an earlier head than the PR's current head or checks bound to another head, an unavailable provider or auth with its recorded limitation, an operational escalation, a finding-level escalation including exhausted repair or review rounds, and an exhausted post-merge obligation. Each finding SHALL cite its evidence. The unclaimed-job threshold SHALL come from the required `[chat_coordinator] unclaimed_job_after_minutes` setting; a missing or invalid setting SHALL fail the overview naming the key and SHALL NOT be replaced by a default.

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

The overview SHALL list as permitted only actions that the existing operator commands (`resume`, `switch-provider`) would accept for the item, computed by the same state, job-kind and claim eligibility function those commands use, and SHALL print the exact command including the PR's current head as `--expected-head`. For a finding-level escalation, a rejected review, an exhausted round, a disputed disposition, a live claim, a merged or closed PR, or a needed OpenSpec or business decision, it SHALL list no action and SHALL show the finding or basis and the human decisions available. Where the supported contract cannot apply a decision safely it SHALL say so and SHALL NOT suggest a substitute.

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

#### Scenario: Eligibility agrees with the command
- **WHEN** any candidate state is evaluated
- **THEN** the overview lists an action if and only if the operator command accepts it for that state

### Requirement: Operator decisions are head-bound and attributed

`publication_queue.py resume` and `switch-provider` SHALL accept `--expected-head` and, when it differs from the PR's current head, SHALL refuse before any write. Every re-offer SHALL record, in the existing candidate record, the reason, the acting authenticated GitHub identity, the `via` label when one is given, the PR and the exact head. An actor that cannot be resolved SHALL fail the command. The chat coordinator SHALL run these commands only after an explicit user decision naming the PR, SHALL NOT bypass an unexpired claim, and SHALL report the command result truthfully.

#### Scenario: Head changed between report and decision
- **WHEN** the user says continue and the PR head differs from the head in the report
- **THEN** the command refuses naming both heads and nothing is written

#### Scenario: Attributed resume
- **WHEN** an operator resumes an operationally escalated candidate
- **THEN** the candidate record shows reason, actor, the given via, PR and exact head
- **AND** the same round is offered again without spending budget

### Requirement: Escalations leave one human-readable GitHub indication

When the coordinator first publishes `blocked-escalation` for an exact head and reason, and when it first observes an exhausted post-merge obligation, it SHALL post one human-readable PR comment stating the reason, evidence links and the permitted actions or the human decision needed, idempotent per PR, head, state, red gate and attempt counters of that escalation round. A successful stage SHALL post nothing. A failure to post SHALL be raised after the transition is published and SHALL fail the run visibly, without a second channel or a swallowed error. Final Requirement closure SHALL keep using the existing close of the Requirement Issue.

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

### Requirement: Chat coordinator role is a repository-defined observer and exception operator

The repository SHALL define the chat coordinator role in `docs/engineering/chat-coordinator.md`, reachable from the `AGENTS.md` concern table. The role SHALL be observer and exception operator only: normal review, repair and merge continue without it; it SHALL state facts only from the overview and GitHub; it SHALL NOT approve material findings, retry fictitiously, change OpenSpec or business decisions, bypass required checks or claims, or touch another agent's state; and unknown SHALL remain unknown. It SHALL NOT require a persistent chat, a second state store, a separate dispatcher model or a new user step on the happy path.

#### Scenario: Role assigned in a new session
- **WHEN** the user assigns a new session the chat coordinator role and asks what is going on
- **THEN** the session reads the role document, runs the overview and answers with stages, blockers and next steps with links

#### Scenario: Material finding
- **WHEN** an item is escalated for a material finding
- **THEN** the session shows the finding and asks the user for the decision
- **AND** it does not run `resume`
