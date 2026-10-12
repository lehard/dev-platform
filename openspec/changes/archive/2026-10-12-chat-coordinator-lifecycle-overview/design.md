## Context

- The candidate lifecycle is already derived from GitHub (`candidate_lifecycle.derive_candidate`): PR head, checks, labels and versioned marker comments, plus head-bound job claims and result receipts (`lifecycle_workers`). `publication_queue.py status --pr/--requirement` renders it; `requirement_intake.py aggregate` projects Requirement progress; `pr_review_gate.reoffer` implements `resume` and `switch-provider` with strict preconditions.
- Workers discover candidates as open PRs plus one bounded page (50) of the most recently updated closed merged PRs. Older merges offer no obligation from there.
- The CI "publication coordinator" (the App running `publication-queue`) is a different actor from the conversational role of this change; the new artifacts call the latter the **chat coordinator**.
- BR-610/BR-433 own executor liveness. At authoring time no platform-readable liveness signal exists in the repository.

## Decisions

1. **Compose, do not store.** `lifecycle_overview.py` is a thin read-only composer over existing derivations. It writes nothing (no file, comment, label), keeps no cache, and every figure it prints carries its GitHub source (PR/comment/run/Issue link or the marker field). A new chat reproduces the same output from GitHub alone.
2. **Same candidate set as the workers.** Candidate discovery moves into `lifecycle_workers.candidate_prs` used by both `main()` and the overview, so the overview shows exactly what workers can act on. The bounded closed-PR page is reported as a stated limitation, not hidden. Requirements are discovered from open `type:requirement` Issues in the Development Backlog (read through `aggregate`); their candidate PRs are matched by the `br-N` branch identity in the summary and by `requirement_status` in the Requirement drill-down. Independent GitHub reads run in a small bounded thread pool.
3. **Delivery stages are a derived projection.**
   - `in-development`: a Requirement with no PR and no linked technical child visible from this checkout (pre-authoring state is machine-local).
   - `handed-off`: developer handoff recorded, no job claimed yet and below the unclaimed threshold.
   - `delivering`: a lifecycle job is claimed or queued/integrating and no exception applies.
   - `merged-open-obligations`: PR merged but `post_merge_job` still names retrospective/terminal/cleanup, or the Requirement is not `Done`.
   - `closed`: PR merged with no obligation, Requirement `Done`.
   - `needs-intervention`: any exception finding below.
   - `unknown`: a required source is unreadable or contradictory (fails closed, never healthy).
   The chain view lists review → repair → re-review → finalize → integration → retrospective → terminal → cleanup with attempt counters from the candidate record. "Merged" and "Requirement Done" are separate lines.
4. **Executor attribution is claim fact only.** The overview prints the winning claim (worker identity, provider, `expires_at`, comment link) as "claimed by … until …" and `executor activity: not confirmed`. Only an explicit read-only signal bound to the exact job id and head may print `confirmed by <source>`; none exists yet, so BR-610/BR-433 can later add a source without changing the contract. A claim alone never means "running".
5. **Exception findings are defined by observable fields.**
   - *unclaimed-next-job*: a `next_job` exists, no valid claim, no completing result, and the record `at` is older than `[chat_coordinator] unclaimed_job_after_minutes` (required key; a missing or invalid key fails with a message naming it — no hidden default).
   - *expired-claim*: the latest claim for the exact job has `expires_at` in the past and no completing result.
   - *stale-head*: derivation reports a claim recorded on an earlier head, or checks bound to another head; such a result is discarded, not applied.
   - *provider-unavailable*: `blocked-retryable` with `retry_job_kind`, or a result outcome starting with `unavailable`; the finding names provider and the recorded limitation.
   - *escalated-operational* vs *escalated-finding*: `blocked-escalation` classified with the existing `OPERATIONAL_REPAIR_OUTCOMES`; finding-level covers proposed rejection, exhausted rounds and rejected review.
   - *post-merge-exhausted*: `post_merge_job` returns the exhaustion reason.
   - When a needed source cannot be read the finding is `unknown` with the failing source.
6. **One eligibility function.** The preconditions now inside `pr_review_gate.reoffer` (state, kind, finding-level refusal, live-claim refusal, open PR) move into a pure `reoffer_plan(candidate, claim, action)` returning either a plan (`kind`, whether a provider is required) or a refusal message. `reoffer` calls it; the overview calls it to list permitted actions and, on refusal, prints that same message as the human-decision text. The overview prints the exact command including `--expected-head <sha>`.
7. **Operator decisions are head-bound and attributed.** `publication_queue.py resume|switch-provider` accept `--expected-head SHA`; when given and different from the PR's current head the command refuses before any write. The re-offer event gains `actor` (authenticated GitHub login resolved through the API; an unresolved identity fails the command) and `via` (free text, e.g. `chat-coordinator`). Because the event lives in the existing candidate record comment, reason, actor, PR, exact head and time are durable on GitHub with no second store. The chat coordinator is told never to run these without a user's explicit instruction naming the PR.
8. **Attention comment, not a notification system.** When `_transition` publishes `blocked-escalation` (and re-observes it, which repairs a lost indication), and when the post-merge worker run ends with an exhausted obligation (`ensure_post_merge_attention`), the coordinator posts one human-readable comment: reason, evidence links, and the permitted actions or the human decision needed. Idempotence uses a hidden trusted marker keyed by PR, head, state, red gate and attempt counters (the reason text is deliberately not part of the key, so a rephrased reason on the same escalation round never reposts, while a resumed and re-escalated round, which changes the counters, does; only trusted authors suppress a repost). A failure to post is raised after the transition is published and fails the run visibly (no swallow, no retry with another channel). Successful stages post nothing. GitHub's native subscription notifications (PR author) deliver it to existing GitHub/macOS notifications. Provider-unavailable retries stay on-demand in the overview; they are automatic and would otherwise cascade.
9. **Role contract as a plain document.** `docs/engineering/chat-coordinator.md` states: the role is observer plus exception operator; normal review/repair/merge continues without it; sources are GitHub only; reports start from `lifecycle_overview.py`; allowed mutations are only the commands the overview lists, after an explicit user decision naming the PR; material findings, review/repair limits, disputed dispositions and OpenSpec/business changes are shown to the user and never retried or approved; unknown stays unknown. `AGENTS.md` gets one concern-table row. No provider skill/capability is created (avoids the capability eval lifecycle; the document is readable without enabling anything).
10. **Placement.** The script sits next to `publication_queue.py` in `template/scripts/` with a `scripts/` source adapter, as other lifecycle entrypoints; it requires the `[publication]` coordinator configuration and fails explicitly without it. It ships through the normal release and rollout; the platform manifest is regenerated.

## Rejected alternatives

- A persisted dashboard or status file: a second state store that can diverge from GitHub.
- Treating a live claim as "running": a claim proves intent, not execution; the acceptance forbids it.
- Notifying on every transition or provider retry: cascading notifications on successful or self-healing stages.
- A default unclaimed threshold in code: a masked missing config.
- A separate coordinator-only action path that re-implements resume/switch: would fork eligibility rules; the shared function removes the fork.
- A new Capability descriptor and live eval for the role: heavier lifecycle than a document pointer for no added behavior.

## Risks and mitigations

- *Wrong "healthy" classification when a signal is absent.* Every classifier returns `unknown` for unreadable/contradictory input; tests cover it.
- *API cost of scanning all PRs.* Only the worker candidate set is read; comments are fetched per candidate once; the output records the bound it used.
- *Terminology confusion with the CI publication coordinator.* New artifacts use "chat coordinator"; the document states the distinction.
- *Shared-function refactor changes re-offer behavior.* Existing `test_pr_review_gate` scenarios stay green; new tests assert the overview and `reoffer` agree on every state.
- *Config key added to a source repo file that downstream does not own.* The key is read only by `lifecycle_overview.py`, which is source-lifecycle; downstream without it gets an explicit error when invoked, nothing else changes.
