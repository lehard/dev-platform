## Why

Composition, contribution conflicts, `absorb-main` and post-merge recovery have the longest unverified list in recent delivery reports. They only ran on live Requirements.

## What Changes

- Scenarios for a Requirement with two children through composition, a contribution conflict after a sibling merge, main movement with `absorb-main`, and post-merge with late friction to terminal.
- Sandbox Requirement Issues and a sandbox Project, so no scenario writes to the real Backlog.
- Sandbox checks call real `npx`, covering composition full checks.
- A coverage list maps each live-unverified item to a scenario or a reason.

## Impact

- Runner scenarios, fixture checks, `docs/engineering/live-scenarios.md`, tests, manifest.
- Spec: new `live-requirement-scenarios`.
