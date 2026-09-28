# Design: Upstream task-line pattern

Port the upstream OpenSpec 1.13.2 `TASK_LINE_PATTERN` (`dist/utils/task-progress.js`) to Python verbatim:

`^\s*(?:[-*+]|\d{1,9}[.)])\s*\[(?:\s*([^\]\s]?)\s*\](?![(\[])|\s+\])`

A matched line is a task; it is complete only when the captured content lowercases to `x`. Empty or any other single-character content (`~`, `-`, `/`, ...) is incomplete. The negative lookahead keeps Markdown links such as `- [x](url)` from counting as tasks, matching upstream.

The rule lives in one pure helper, `openspec_lifecycle.count_tasks(text) -> (total, incomplete)`. `task_state` keeps its `(total, incomplete)` contract on top of it, so every lifecycle caller (`require_ready`, `require_static_archive_readiness`, `completed_active_changes`) inherits the fix without change.

Two other delivery gates duplicated the old `-`-only pattern and had the same gap: `managed_task._task_completion` (managed delivery provenance) and the archived-tasks check in `requirement_integration` (shared Requirement candidate). Both now delegate to the same helper instead of carrying their own regex, so there is exactly one task-counting rule. The dogfood `scripts/openspec_lifecycle.py` is a `source_adapter` shim over the template helper, so the two copies cannot diverge.

The Requirement child-list parser (`requirement_intake.CHILD_ITEM_RE`) is a platform-written machine block, not authored tasks.md content, and is out of scope.

Compatibility: a downstream tasks.md that previously looked complete only because open items used unrecognized markers will now correctly block readiness. That is the intended correction, not a regression.
