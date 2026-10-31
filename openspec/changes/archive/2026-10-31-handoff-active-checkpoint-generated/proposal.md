## Why

A Requirement child was refused at publication as "diverged" after a 25-40 minute full run, and after reconcile its friction checkpoint went stale (friction lehard/dev-platform#818, BR-846 and BR-800). Both came from one path: the developer archived the change before the handoff. `openspec_lifecycle.py archive` accepts that for a coordinator candidate, but an archived task is no longer a candidate, so `execute_requirement.py advance` publishes it through the terminal `finish` path with the strict fresh-base gate. The checkpoint content proof then included the main-spec files the archive materialized and the declared generated `platform-manifest.json`, which main also changed. The accepted handoff contract already names the still-active change and the behind-mergeable contract.

## What Changes

- A non-finalize `openspec_lifecycle.py archive` of a coordinator candidate refuses before any review, check or mutation, naming the handoff command; the coordinator's finalize archives. The unreachable coordinator branch of the developer archive is removed.
- The friction checkpoint content proof of a managed task excludes files declared in `[[generated_files]]` at the merge base (as the quick-task proof does). Any other task-owned change still makes the checkpoint stale.
- docs/engineering/agent-workflow.md states that a candidate is handed off active.

## Capabilities

### Modified Capabilities

- `completion-lifecycle`: developer archive of a coordinator candidate is refused.
- `platform-lifecycle`: checkpoint content proof excludes declared generated files.

## Impact

`template/scripts/openspec_lifecycle.py`, `template/scripts/agent_friction.py`, `template/scripts/task_content_identity.py`, tests, docs. Owner decisions D1=A, D2=A (2026-10-31). A checkpoint recorded before this change carries generated paths in its proof and is re-recorded once.
