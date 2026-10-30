## Why

The owner made the chat coordinator the delivery orchestrator on 2026-10-28 (variant A). The accepted spec still defines it as observer and exception operator that runs `resume`/`switch-provider` only after an explicit owner decision per PR, so a new coordinator session reading the spec refuses or asks the owner for every routine worker run. Practice already diverged: the coordinator runs `lifecycle_workers.py work-next`, drives PRs to merge and orders the streams.

## What Changes

- chat-coordinator spec: the role requirement becomes "Chat coordinator role is a repository-defined delivery orchestrator" with its authority (roadmap, at most two code streams unless the owner decides otherwise, launching review/repair/post-merge workers, draining LLM-free jobs, routine `resume`/`switch-provider`/`reoffer-post-merge`/`restore-gates` after technical failures), what stays with the owner (material findings, exhausted rounds, disputed rejections, business and OpenSpec decisions, words an executor's contract needs from the owner) and the unchanged red lines.
- `docs/engineering/chat-coordinator.md`: role text and a cycle runbook (overview, roadmap pick, streams, worker runs with their environment, owner escalations), the main-freeze rule during a re-handoff, session handover and cycle cadence.
- `lifecycle_overview.py`: the `unclaimed-next-job` hint for a post-merge job names the post-merge runner and the exact `work-next --pr` run-now command.
- `AGENTS.md` concern row and `docs/engineering/agent-workflow.md` hosted-kind placement (review, finalize, integration-merge) and the now-supported `finalize-pending` developer re-handoff.

## Impact

- `openspec/specs/chat-coordinator/spec.md` (via delta), `docs/engineering/chat-coordinator.md`, `docs/engineering/agent-workflow.md`, `AGENTS.md`, `template/scripts/lifecycle_overview.py`, `tests/test_lifecycle_overview.py`, platform manifest.
