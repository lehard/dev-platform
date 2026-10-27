## Why

BR-772 removes hidden fallbacks from gates and checks. Three remain in the select-checks and finish path: an `ImportError` stub makes `select_checks` silently skip the scope-conflict Project status; `finish` silently skips the private-reference guard when its script is absent, even where private lineage requires it; and the board release in `finish` swallows an unreadable board (`JSONDecodeError` -> no claim) and ignores a failed release except in one path.

## What Changes

- `template/scripts/select_checks.py`: import `block_for_scope_conflict` from `managed_project_status` directly; remove the compatibility stub.
- `template/scripts/finish_task.py`: `observe_private_reference_blocker` applies only where `private_lineage.enabled(root)`; there a missing guard script is a blocker naming it; where it is disabled it returns no blocker by configuration, without probing for the file.
- `template/scripts/finish_task.py`: `find_board_id` raises a named `SystemExit` for an unreadable board, a non-object board or a non-list `items`; an absent board file or a worktree without a claim is an explicit "no claim". `finish_board` fails on a failed release in every caller, naming the rerun command; the `required` switch is removed.

## Impact

- `template/scripts/select_checks.py`, `template/scripts/finish_task.py`.
- Spec: gate-fail-explicit (one added requirement).
- Tests: finish board and private-reference tests, select-checks import.
