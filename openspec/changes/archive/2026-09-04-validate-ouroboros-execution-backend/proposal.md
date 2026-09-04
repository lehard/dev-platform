# Proposal: Validate Ouroboros as a Dev Platform execution backend

## Why

Ouroboros overlaps materially with Dev Platform's generic agent-runtime concerns and may let us stop maintaining parts of runtime adaptation, retry/recovery and execution observability ourselves. Its current development pace and recent runtime regressions make a production switch unjustified without direct compatibility evidence.

## What Changes

- Run one bounded Ouroboros compatibility pilot behind the existing external agent-runtime boundary.
- Keep managed task identity, OpenSpec, assigned workspace, verification, publication, release and rollout authoritative in Dev Platform.
- Replay two already-completed representative changes from their historical pre-change bases: `development-backlog#94` and `#30`.
- Translate the existing canonical OpenSpec/task contract into the minimum Ouroboros execution input without creating a second editable specification.
- Evaluate the produced result with the current Dev Platform verification/acceptance path.
- Record a single evidence-backed decision: `adopt-next-step`, `watch-only`, or `reject-for-now`, including the concrete maintenance that further adoption could remove.

This change does not authorize a production runtime switch or downstream rollout.
