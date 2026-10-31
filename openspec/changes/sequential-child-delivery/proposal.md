## Why

When the owner decides that a Requirement's children ship one at a time, every merge moves main, the evidence snapshot goes stale and every downstream artifact must be rebuilt and re-approved by hand before the next child, even when nothing in the approved design changed (BR-897: eight children, the full chain rebuilt each time).

## What Changes

- Intent set: optional `delivery` object `{"mode": "sequential", "order": [intent ids]}`; validation requires every intent exactly once, each ready. Absent, delivery is unchanged.
- `execute_requirement.advance` for a sequential Requirement: children follow the declared order; only the first not-Done child is materialized, started or handed off through the single-child path; the next starts after it is Done; after the last, the existing post-merge or retrospective path.
- Rebind: `orchestrate_pre_authoring.rebind` re-anchors snapshot, ADD, intents and handoffs to current main and records a receipt, when the stale state is explained by own delivered children or by commits outside the remaining children's sources; the approval is carried from the approved content digest.
- Explicit stop naming paths, commits and the re-approval step when a foreign commit touched a source of a remaining child, or the Requirement, ADD material content, intents or a handoff no longer match.
- `advance` reading a handoff's intents fails explicitly on an unreadable file (a missing handoff stays legal).

## Impact

- `template/scripts/{execute_requirement,orchestrate_pre_authoring,add_intents}.py`, tests, task-intake docs, manifest.
- Spec: agent-workflow (requirements added).
