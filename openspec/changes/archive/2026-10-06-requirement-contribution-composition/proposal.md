## Why
Children currently run one at a time and are archived individually before assembly; findings that only appear across children (BR-341) are found late, and per-child archives of the same capability conflict.

## What Changes
- Each child is a contribution PR targeting the Requirement integration branch and passes its own checks, verification, review and repair; independent children run in parallel, dependent ones start from the integration branch after predecessors are integrated.
- The coordinator merges reviewed contributions into the integration branch.
- The Requirement PR to main receives composition-only review of cross-child properties, one finalization/archive of all children, then the integration queue. A single-child Requirement uses its child PR against main.

## Capabilities
### Modified Capabilities
- `platform-lifecycle`: shared candidate model.

## Impact
`execute_requirement.py`, `requirement_integration.py`, coordinator contribution merge, review composition mode.

## Outcome and Evidence
Fixture with three children (two independent, one dependent) runs in parallel where allowed, composes, gets one composition review and one finalization, merges once.

## Non-goals
Changing Requirement fixation or pre-authoring.
