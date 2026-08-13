# Proposal: Harden evolving task scope coordination

## Why

File-level admission now prevents two tasks from claiming the same file at start, but task scope is not static. Dogfood showed both false rigidity (no supported way to acknowledge a manually verified same-file independent edit) and late under-enforcement (a new factual overlap discovered at finish is only advisory).

## What Changes

- Keep file-level hard overlap as the default admission blocker.
- Add a bounded explicit acknowledgment for a known same-file overlap so agents do not under-declare scope.
- Persist that acknowledgment as coordination evidence tied to the concrete task pair/paths.
- Re-evaluate factual scope before costly protected validation/publication and block on new unacknowledged hard overlap while the sibling task remains active.
- Keep soft overlap advisory and reuse existing board/claim/Project-status lifecycle.

## Impact

- Modified specification: `worktree-coordination`.
- Expected surfaces: `agent_board.py`, `start_task.py` admission, pre-validation/publication scope checks, managed Project blocker/resume integration, docs and regression tests.
