## Why

BR-772 removes hidden fallbacks from gates and checks. In the select-checks and finish path an `ImportError` stub makes `select_checks` silently skip the scope-conflict Project status, and the board release in `finish` swallows an unreadable board (`JSONDecodeError` -> no claim) and ignores a failed release except in one path.

## What Changes

- `template/scripts/select_checks.py`: import `block_for_scope_conflict` from `managed_project_status` directly; remove the compatibility stub.
- `template/scripts/finish_task.py`: `find_board_id` raises a named `SystemExit` for an unreadable board, a non-object board or a non-list `items`; an absent board file or a worktree without a claim is an explicit "no claim". `finish_board` fails on a failed release in every caller, naming the rerun command; the `required` switch is removed.

## Impact

- `template/scripts/select_checks.py`, `template/scripts/finish_task.py`.
- Spec: gate-fail-explicit (one added requirement).
- Tests: finish board release, select-checks import.

Deferred: the silent skip of the private-reference guard in finish when its script is absent. The accepted completion-lifecycle requirement runs the guard unconditionally, while every downstream project configures `[development_backlog]` without shipping the guard; the applicability rule is a contract decision returned to the requester.
