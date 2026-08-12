## Why

Source backlog issue: `lehard/development-backlog#18`
Prepared against: `lehard/dev-platform@5eb43498ec0ba996932adf9d0a46d1df5993e29a`

Recent managed-task deliveries exposed cross-task identity contamination after the provenance-completeness guard from Development Backlog #15 was merged. `lehard/dev-platform#166`, `#174`, and `#177` show terminal/status reconciliation for one task selecting another task's Development Backlog source.

The same contamination now blocks fresh intake before materialization. Integration `main` currently tracks `.managed-task-state.json` for backlog #15. `start_managed_task` creates a fresh task checkout from that baseline; `import_task` sees inherited task state and invokes resume-only canonical provenance resolution for backlog #18 before its OpenSpec change exists. The new task therefore cannot materialize through the normal path.

The missing guarantee is lifecycle-wide identity isolation: shared integration state from task B must never become authoritative identity for task A, either during fresh start/materialization or during terminal reconciliation.

## What Changes

- Distinguish fresh managed start from resume using exact task-local evidence rather than inherited integration state alone.
- Prevent stale task-specific integration state from forcing a new task through resume-only provenance guards before first materialization.
- Define bounded bootstrap/recovery for already contaminated integration state without creating a general manual bypass.
- Preserve one deterministic managed-task identity across execution, publication, remote merge, local reconciliation, Project-status update, and cleanup.
- Make task-local provenance / exact delivery identity authoritative for terminal side effects; integration state may cross-check but never replace it.
- Keep confirmed GitHub merge authoritative when later reconciliation fails and expose resumable pending reconciliation.
- Avoid a new task database or a second implementation plan; repository-local OpenSpec remains canonical after materialization.

## Capabilities

### Modified Capabilities

- `managed-task-intake`: fresh start/materialization is isolated from stale task-specific integration state, while genuine resume remains provenance-guarded.
- `platform-lifecycle`: terminal side effects use exact task identity and cannot mutate an unrelated Development Backlog item.

## Impact

Expected implementation touchpoints include managed task-state ownership/lifecycle, fresh-start versus resume detection, provenance/status discovery, and finish/publication reconciliation. Exact storage or helper placement is left to implementation preflight; the contract requires task identity locality and deterministic lifecycle semantics rather than a particular mechanism.
