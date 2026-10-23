## Context

Attribution today: `default_attribution` returns the explicit task, else the current branch, else `(None, "unattributed")` for `unknown`/`main`/`master`/configured main. `event_identities` reads branch, `run.source_issue` and an explicit attribution record. `ambiguous_attribution_events(since)` returns task-less events with no identities inside a 14-day window. `integration_contour` blocks the automated task and Requirement retrospectives on any of them since the candidate's admission or Requirement start. The manual checkpoints only report them.

## Decisions

- **No-task is a classification, not an absence.** `no-task` is set at record time for an event outside a task, derived on read for a legacy `unattributed` event whose branch is a non-task name, or appended explicitly by `attribute --no-task`. The event log stays append-only; explicit attributions stay in the existing attributions file with `"no_task": true` and no `task`.
- **Precedence.** Explicit task attribution > explicit no-task (conflict between the two fails) > recorded task/branch identity > automatic no-task. An automatic no-task event explicitly attributed to a task becomes that task's signal.
- **Ambiguity is what is left.** An event is ambiguous only if it has no task, no identity and no no-task classification (for example a legacy line without a branch). The existing window and `since` bounds stay.
- **One refusal rule.** Manual and automated checkpoints share `ambiguous_attribution_events`; the manual ones raise before writing a receipt with the ids and the commands `attribute --id ID --task owner/repo#N --reason TEXT` or `attribute --id ID --no-task --reason TEXT`.
- **Visibility.** No-task events are excluded from every task's mandatory signals and from ambiguity; `review-path` and checkpoint output list the recent ones under `no_task_events`. They remain in the local log and the shared friction routing/review unchanged.

## Risks

- An event recorded from an integration checkout that really belongs to a task is no longer forced into a decision. Mitigation: it is listed as `no_task_events` in that task's review-path and can be attributed explicitly; the owner accepted this trade-off with variant A.
