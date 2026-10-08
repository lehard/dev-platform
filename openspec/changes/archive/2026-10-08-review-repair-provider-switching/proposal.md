## Why
Review and repair jobs are bound to the provider chosen when the first job was published, and every retry inherits it. Changing configuration affects only new publications, so an already-open candidate cannot move to another supported provider (for example when one provider's usage limit or login is unavailable) without closing the PR or hand-editing coordinator records. Workers cannot restrict themselves to jobs they can run, so an unrunnable job at the lowest PR number starves jobs of other providers and operators resorted to unrunnable hold-claims. A provider runtime failure during repair, or a refused harness push, moves the candidate to blocked-escalation, which has no documented exit.

## What Changes
- Add an operator command that re-offers a candidate's open review or repair job on an explicit ordered provider list. The switch is one appended coordinator record carrying the previous and new providers and the reason; gates, findings and attempt counters are preserved, so no retry or repair round is spent and no PR is closed.
- Add an operator command that resumes a repair job after an operational blocked-escalation (worker failure, harness rejection, no change) or an exhausted retry streak, recording the human reason and optionally a new provider.
- Let `work-next` restrict selection to given PRs and to providers whose runtime passed a bounded preflight in the worker's own scratch environment, so jobs of other providers are never claimed, held or blocked.
- Treat an unavailable provider runtime during repair like an unavailable review: record a named cause, stay blocked-retryable on the same round, and bound automatic retries.
- Name the provider-unavailable cause in review retry state.
- Document the operator path in the operating guide.

## Success Evidence
Regression tests cover: switching an open review and repair candidate with preserved gates, findings and attempts and recorded provenance; refusal under a live claim and for non-job states; selection by PR and by preflight-proven provider with an unrunnable job not blocking another; unavailable runtime during review and during repair giving a retryable, named, round-neutral state; resuming an operational escalation and refusing a finding-level escalation.

## Non-goals
Repairing the Claude login in the worker scratch HOME; automatic cheapest-provider selection or economy routing; changing review perspectives, repair containment, or merge authority; any change to who may decide to reject a material finding.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `completion-lifecycle`: provider retention, unavailable-runtime retry and operational escalation exit for review and repair jobs.
- `lifecycle-workers`: job selection by PR and by preflight-proven provider.
- `publication-queue`: operator re-offer and resume of review and repair jobs.

## Impact
Template `lifecycle_workers.py`, `pr_review_gate.py`, `publication_queue.py`, `candidate_lifecycle.py`, their tests and the agent-workflow operating guide. The new job field and attempt counter are additive and optional, so existing records stay valid. `work-next --run` for repair now requires an explicit `--repair-provider`.
