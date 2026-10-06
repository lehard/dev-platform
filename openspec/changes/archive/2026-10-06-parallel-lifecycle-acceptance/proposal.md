## Why
BR-353 acceptance requires several parallel PRs, main movement, at least one repair and successful merges, without manual completion passes.

## What Changes
- A reproducible scenario in a disposable repository sandbox with a local fake GitHub surface that runs several parallel candidates through review, repair, finalization and sequential integration with main movement.
- A dogfood evidence template describing what a real run must record; the real dogfood run itself is deferred to lehard/development-backlog#391 after BR-353 merges.
- Portability notes for the separate downstream rollout Requirement.

## Capabilities
### Modified Capabilities
- `disposable-repository-sandbox`: lifecycle acceptance scenario.

## Impact
Sandbox scenario script and tests, docs.

## Outcome and Evidence
The scenario passes repeatably, including an integration repair of an already finalized managed candidate that is re-reviewed against its archive and finalized again; the evidence template and portability notes exist. No real dogfood run is claimed by this change.

## Non-goals
Downstream rollout. The real dogfood run (deferred to lehard/development-backlog#391).
