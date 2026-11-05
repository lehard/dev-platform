## Why

Managed delivery, red CI and integration repair are the paths where recent dead ends appeared. Without a result on the candidate head, working deliveries remain the first real test of new queue code.

## What Changes

- Scenarios for a managed task through review, finalize and queue, a red CI and its exit, and a conflict with main through integration repair.
- Scripted review and repair executors behind the worker `--llm-command` path, so findings and repairs reproduce on every run.
- A run on a candidate head writes a receipt bound to task content.
- Handoff of a queue or lifecycle change is refused without a receipt or with a new red scenario.

## Impact

- Runner scenarios, receipt, the handoff gate, `docs/engineering/live-scenarios.md`, tests, manifest.
- Spec: new `live-queue-scenarios`.
