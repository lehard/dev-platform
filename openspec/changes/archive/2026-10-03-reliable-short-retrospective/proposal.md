# Proposal: Reliable short task retrospective

## Why

During delivery of Requirement development-backlog#284 the Requirement retrospective needed an operator reminder. The first parent checkpoint said `none` although a manual archive repair, a repeated evidence cycle and a stale-receipt recovery had happened, and a browser friction occurrence was recorded with `task=null` while `branch` and `source_issue` were available, so task-only selection never saw it. Existing checkpoints join signals to a task only by exact `task == branch` equality and only accept a signal by linking a new finding.

## What Changes

- Friction events record a resolvable attribution: an explicit task, otherwise the current non-integration branch; events with neither are marked unattributed.
- Retrospective selection also attributes legacy `task=null` events by their recorded `branch` or `run.source_issue` without rewriting history, and reports events that cannot be attributed as an explicit gap instead of dropping them or assigning them to another task.
- Mandatory signals (high-signal lifecycle failures plus recorded workaround/override/recurrence/drift) must each be linked as a finding or classified `resolved-in-task`, `already-recorded` or `expected-behavior`; a known-recurrence occurrence is never dismissable.
- Unreadable or partial evidence sources are named in the review and must be explicitly accepted before `none`.
- The Requirement retrospective uses the same signal set, including events attributed to the Requirement during pre-authoring and between children.
- `review-path` prints a short shared template and up to five project-owned questions from `dev-platform/retrospective.toml`, applied by changed path.

## Impact

`template/scripts/agent_friction.py`, `template/scripts/requirement_retrospective.py`, the template and central workflow docs, a project-owned `dev-platform/retrospective.toml` shipped skip-if-exists through Copier, and tests. No new store, queue, policy language, model gate or product-test requirement.
