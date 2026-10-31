## Why

Every developer re-handoff on 2026-10-31 (#809, #817, #828, #832; friction lehard/dev-platform#834) needed manual steps: the board claim deleted at the first admission had to be recreated with `agent_board.py start`, overlap acknowledgments lost with it had to be repeated, the friction checkpoint had to be rewritten at the reconciled head, and a retained execution had to be recorded because the first handoff did not run the routing gate that a later path enforces.

## What Changes

- Admission marks the developer's claim handed off instead of deleting it: the board item keeps its identity and acknowledgments, records the handed-off head and PR, and claims no scope.
- The scope gate in preflight writes nothing and accepts this worktree's handed-off item as its claim only when the exact PR's latest coordinator state is one of `READMISSION_STATES` and HEAD descends from the handed-off head; every other case refuses with the command, as today.
- Only the re-handoff entry (`finish` developer handoff, also through `execute_requirement.py advance`) reactivates the item, at handoff; admission then marks it handed off again at the new head.
- The developer handoff accepts the friction checkpoint by the managed task-content proof instead of the exact head, and runs the archive routing gate (`require_managed_routing_evidence`) before publication.

## Capabilities

### Modified Capabilities

- `completion-lifecycle`: handoff checkpoint by task content; routing gate at handoff.
- `worktree-coordination`: handed-off developer claim.

## Impact

`template/scripts/agent_board.py`, `finish_task.py`, `pr_review_gate.py`, `worktree_cleanup.py` (handed-off records are not active), tests, docs. Coordinator decisions D1=A, D2=A (amended: preflight is read-only), 2026-10-31.
