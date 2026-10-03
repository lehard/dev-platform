# Proposal: Early draft shared PR for multi-child Requirements

## Why

A shared Requirement candidate is assembled and published only after every mandatory child has a ready receipt, so CI and integration problems surface at the end of the sequential chain. Part of the result is verified long before then and could be integration-checked earlier.

## What changes

- A shared candidate may be *incomplete*: it carries the exact verified children so far plus the full list of expected mandatory changes. An incomplete candidate is published only as a draft PR, which GitHub cannot merge and which cannot be queued or auto-merged.
- Appending a ready child extends the same branch with new commits (fast-forward push) and the same committed manifest path; the manifest remains digest-bound and append-only.
- `execute_requirement.py advance` opens or updates the draft candidate after each child is ready and then continues with the next child.
- Marking ready, arming merge, queueing and terminal reconciliation require a complete manifest, the Requirement retrospective checkpoint and full checks on the exact final head.
- Release and managed rollout stay on the existing release-policy path and run after the merge.

## Impact

Affects `template/scripts/requirement_integration.py`, `execute_requirement.py`, `project_publish.py`, `requirement_terminal.py`, their tests, `docs/engineering/task-intake.md` and the accepted `agent-workflow` and `platform-lifecycle` specs. No change for single-child Requirements or ordinary managed tasks.
