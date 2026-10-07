## Why
`archive <change>` runs `select_checks.py --execute`, whose standard mapping includes `openspec_lifecycle.py check`. That hygiene check treats the completed-but-not-yet-moved archive target as a violation, so a verified change cannot archive itself. Reproduced downstream (Forma223, Harness 1.8.2) and recorded as friction lehard/dev-platform#267.

## What Changes
- `archive` scopes an archive-target context to the single validation subprocess run that executes the selected checks; the hygiene check exempts only that exact change.
- The exemption is validated fail-closed: the target must be a completed active change; a missing, malformed or non-completed target blocks hygiene with an explicit error.
- The context is never persisted; any later ordinary `check` sees the change again.
- The standard check mapping is unchanged and the template lifecycle is the single implementation shared by source and rendered projects.

## Capabilities
### Modified Capabilities
- `completion-lifecycle`: archive-scoped hygiene exemption for the exact archive target.

## Impact
`template/scripts/openspec_lifecycle.py` (source `scripts/openspec_lifecycle.py` is its adapter), tests, `docs/engineering/openspec-workflow.md` and its template counterpart.

## Outcome and Evidence
A completed verified change archives through the real standard check mapping; a second completed active change, an invalid target, or a failed archive still block.

## Non-goals
No removal of the hygiene check from check groups, no global skip, no weakening of verification/review/evidence gates, no change to upstream OpenSpec, no BR-353 finalization redesign.
