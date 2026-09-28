# Proposal: Align lifecycle task counting with upstream checklist markers

## Why

`openspec_lifecycle.task_state` counts only `-` bullets whose checkbox is exactly `[ ]`, `[x]` or `[X]`. Items written as `+ [ ] task`, `1. [ ] task`, `1) [ ] task` or `- [~] partial` are ignored, so a tasks.md whose only open work uses those forms is reported complete. `require_ready`, `require_static_archive_readiness` and `completed_active_changes` then accept a change that still has unfinished tasks. Upstream OpenSpec 1.13.1 fixed the same gap in its apply progress.

## What changes

Task counting adopts the upstream OpenSpec task-line semantics: `-`, `*`, `+`, `N.` and `N)` list markers are recognized, a checkbox is complete only when its content is `x` or `X`, and any other recognized checkbox content is incomplete. Managed delivery provenance and shared Requirement integration, which duplicated the old pattern, use the same rule.

## Success evidence

Regression tests prove each marker form and the unknown-content rule; existing `-` checkbox counting is unchanged; template and dogfood helpers stay identical.

## Constraints and non-goals

No change to the tasks.md authoring format, OpenSpec itself, or existing tasks.md files.
