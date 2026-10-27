## Why

Requirement terminal reconciliation proves each child's delivery by finding its archived OpenSpec change with `verification.md` "on main". It reads that from the integration checkout's working tree. The post-merge `terminal-reconciliation` job and `execute_requirement.py advance` run in the integration root without first synchronizing it, so after a queue merge the local `main` is behind `origin/main` and the merged archive is not there: reconciliation stops with "has no archived verified contract on main" until an operator fast-forwards `main` by hand (seen 2026-10-22 on #699, #689, #696). Manual fast-forward of the integration main is itself forbidden outside `finish`.

Separately, post-merge `finish` of a queue-merged task must not depend on an agent-board claim (the claim is released at developer handoff). The current code reaches terminal reconciliation before the scope gate, but no test pins that.

## What Changes

- `template/scripts/managed_task.py`: a new read-only helper resolves a change's canonical lineage from a commit's tree (provenance and verification receipt read with git, private lineage authorized against the checkout's configuration), with the same matching and fail-closed rules as the checkout resolver.
- `template/scripts/requirement_terminal.py`: `reconcile_parent` fetches `origin/<main_branch>` once and requires each child's archived, verified contract in that commit.
- `template/scripts/execute_requirement.py`: `_done_child_is_delivered` uses the same fresh-main proof.
- Tests: terminal reconciliation succeeds when local `main` lacks the archive that `origin/main` has, and still refuses when `origin/main` lacks it; post-merge finish of a queue-merged task completes with an agent board that has no claim for the worktree.

## Impact

- `template/scripts/managed_task.py`, `template/scripts/requirement_terminal.py`, `template/scripts/execute_requirement.py`, tests, platform manifest.
- Spec: agent-workflow (modified "Requirement terminal state requires target delivery proof").
- The integration checkout is not modified: no fast-forward, no checkout, no worktree.
