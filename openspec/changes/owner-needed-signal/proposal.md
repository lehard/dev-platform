# Proposal: Owner-needed signal

## Why

A session that waits for the owner is visible only as `waiting-input` without the question, and a stuck agent is otherwise found through claims, heartbeat staleness or friction events, often hours later. The owner and the coordinator need the question, the project and the task as soon as the agent is blocked.

## What changes

Add one platform command with which an agent raises and resolves an owner-needed signal for its own task. The platform stores the signal on the task's agent-board entry, collapses repeats of the same question, rejects a missing, finished or foreign task explicitly, and `lifecycle_overview.py` shows open signals in an "Owner needed" section that the coordinator reads.

## Success evidence

Tests prove raise, repeat, resolve and re-raise, the explicit rejections, task-end cleanup with the board entry, and the overview section in text and JSON, including the unconfigured and unreadable board lines.

## Constraints

No fallbacks: a missing board capability, board file or task fails with a named error. No new configuration key or operator path. The signal decides and answers nothing; owner-reserved decisions are unchanged. Notifications and rendering stay with the board application.
