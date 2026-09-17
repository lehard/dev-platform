# Proposal: Upgrade OpenSpec compatibility baseline to 1.13.0

## Why

Dev Platform still tests OpenSpec 1.6.0. Stable 1.13.0 includes archive/delta correctness fixes relevant to the platform's source-of-truth guarantees, so this is a correctness-motivated compatibility bump rather than version churn.

## What Changes

- Validate the full managed OpenSpec lifecycle against stable 1.13.0.
- Add focused regression coverage for upstream archive/delta failure classes.
- If compatibility evidence is clean, update the supported/tested version contract and all matching fixtures/docs.
- Preserve semantic verification and platform-owned lifecycle guards unless evidence proves a specific guard is redundant.
