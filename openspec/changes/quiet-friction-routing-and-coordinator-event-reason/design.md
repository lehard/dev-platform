## Context

`route-pending` routes every locally retained unrouted event, including coordinator events mirrored into the local log by `append_coordinator_event` and the `lifecycle-validation-failure` events recorded by `finish_task`. `route_body` publishes category, observation, hypothesis and proposal only; evidence stays local by design (it may contain raw output). For coordinator events the observation is a fixed sentence per kind, so the published occurrence has no cause.

## Decisions

1. **Remove, do not background, the retry.** Doctor and finish drop the call entirely. A detached background retry would still race GitHub and hide failures; the explicit `route-pending` command already exists and reports JSON counts. The accepted scenario "event remains pending for later routing retry" is preserved.
2. **Structured `reason` and `candidate` fields** rather than publishing `evidence`. `reason` is a bounded (240 chars) sanitized cause supplied by the producer: the transition detail for coordinator transitions, and `failure_class` plus the failing check/command name from the selector descriptor for validation failures. `candidate` is `{task, number?, head}`. Both are passed through `sanitize_for_route` when rendered.
3. **Producers fail explicitly.** `emit_friction` raises `QueueError` when the detail is empty; `record` rejects `--reason` without a candidate task and vice versa for coordinator categories. No default reason text is substituted.
4. **Router withholds faceless coordinator events.** The coordinator category set is `coordinator-review-repair`, `coordinator-retry`, `coordinator-integration-repair`, `lifecycle-blocked-escalation`, `lifecycle-validation-failure`, plus any event with `attribution == "coordinator"`. Without both fields the route is persisted as `{"status": "withheld", "detail": "coordinator event lacks <field>"}`; `route_pending` skips `withheld` routes and reports `withheld` separately. Legacy faceless events already in local logs therefore stop producing comments; they remain locally inspectable.
5. **Overlap with lehard/dev-platform PR 619.** That PR edits `read_events`, `read_state`, `destination_for`, `process_label`, `platform_repository` and checkpoint code in `agent_friction.py`. This change touches `cmd_record`, the event construction in `append_coordinator_event`, `route_body`, the head of `route_event`, `route_pending` and the `record` parser only.

## Risks

- A downstream harness older than this change keeps calling its own rendered retry; it updates with the release.
- Withheld legacy events are never published; this is the intended behavior for faceless events.
