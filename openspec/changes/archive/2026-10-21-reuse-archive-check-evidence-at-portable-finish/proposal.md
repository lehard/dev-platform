## Why

In the `portable` lifecycle a managed task runs its full selected local check set twice for the same content. `openspec_lifecycle.py archive` executes `select_checks.py --base origin/main --execute --evidence <change>/automated-checks.json` for a platform-owned, non-coordinator change. `finish_task.py` then verifies that evidence with `require_automated_evidence`, but afterwards calls `run_checks(work, remote_main, ...)` unconditionally on the ordinary PR path, which executes `select_checks.py --execute` again. A downstream managed task on 2026-10-19 recorded a successful 10-command set in which one project check command alone took 810 s; the second run repeats that work for content that has not changed. The existing evidence already binds the managed checkout and the task content (`managed_checkout`, `gate_task_content`, `selected_checks`, `executed_commands`), so the duplicate run is not needed when that evidence proves the same tree passed the same required checks.

## What Changes

- `finish_task.py`, on the `portable` lifecycle and only for a managed delivery whose evidence already passed `require_automated_evidence`, decides once whether the archive evidence can stand for the required validation. Reuse requires all of:
  - the evidence carries `managed_checkout` and `gate_task_content` (version 2 evidence) and matches the current managed checkout and task content (the existing `require_automated_evidence` / `evidence_matches_checkout` proof, including the archive-only materialization rule);
  - the recorded `gate_task_content.base` equals the current merge base of `HEAD` with the remote main that finish validates against, and `HEAD` contains that remote main, so the validated tree is the tree being published apart from lifecycle-only paths;
  - the selection finish requires now (`select_checks.py --base <remote main> --json`, same mode) is `ready`, and every command it selects appears in `executed_commands` with outcome `success`, with evidence `outcome` `success` and the command count matching the recorded selection.
- When reuse holds, finish prints `DEV_PLATFORM_CHECK_REUSE: reused` with the evidence path, validated head, base and command list, and does not start `select_checks.py --execute`. When it does not hold, finish prints `DEV_PLATFORM_CHECK_REUSE: not-reusable` with the named reason and runs `run_checks` exactly as today. Unreadable, failed or mismatched evidence still stops publication through the existing `require_automated_evidence` gate before this decision.
- The coordinator lifecycle (source checkout), non-managed or unarchived delivery, `--no-checks` handling, GitLab delivery, OpenSpec hygiene, the private-reference recheck, the completion preflight blockers and the final PR CI are unchanged.

## Capabilities

### Modified Capabilities

- `completion-lifecycle`: portable finish reuses archive selected-check evidence for the exact validated tree.

## Impact

- `template/scripts/finish_task.py` (rendered into managed projects) and a reuse-decision helper next to the existing evidence functions in `template/scripts/openspec_lifecycle.py`; `select_checks.py` is called read-only (`--json`) and not changed.
- Tests: unit tests of the decision and an integration test that counts full local check executions over `archive -> finish` in a rendered `portable` project, before and after.
- Agent workflow documentation of the reuse line.
