## Why

Some Requirement acceptance depends on an action only the owner can take outside the repository (BR-730: a pool configuration on the owner's Mac). Today neither the child, the retrospective nor terminal reconciliation tracks it, so merging every child silently counts as full acceptance and the coordinator holds the close by hand.

## What Changes

- Requirement body section `## Operator acceptance`: one item per line, `- <id>: <owner action> Check: `<command>``; ids are unique slugs, the check command is required; a malformed section fails reads that use it, naming the line. `requirement_intake.py create` accepts it.
- Decision record: `dev-platform-requirement-acceptance:v1 {...}` comment on the Requirement Issue with item, `confirmed` or `waived`, actor (authenticated `gh` login), via, reason and time; only a trusted writer's marker counts; the latest per item wins.
- `requirement_terminal.reconcile_parent` refuses with `OwnerAcceptancePending` naming the open items before any mutation. The post-merge terminal job and the composition terminal path record `requirement-awaits-owner-acceptance: <ids>` as a completed outcome.
- `requirement_terminal.py accept --requirement R --item ID --decision confirmed|waived --reason TEXT [--via LABEL]`: refuses an unknown item and a closed Requirement; appends the decision; when no item is open, closes through `reconcile_parent` (children delivered and retrospective checkpoint still required); otherwise reports what waits.
- `lifecycle_overview.py`: Requirements with open items are listed as waiting for the owner with the check and the exact accept command; `chat-coordinator.md` names the command.
- Requirement Issue state reads in `execute_requirement._await_post_merge` and the closer fail explicitly unless the state is OPEN or CLOSED.

## Impact

- `template/scripts/{requirement_intake,requirement_terminal,integration_contour,requirement_composition,lifecycle_overview,execute_requirement}.py`, tests, docs (task-intake, chat-coordinator, requirement authoring), manifest.
- Spec: agent-workflow (requirements added).
