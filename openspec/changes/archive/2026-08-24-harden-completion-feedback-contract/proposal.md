# Proposal: Harden completion feedback contract

## Why

The terminal lifecycle allowed an avoidable archive retry because the canonical central verification-receipt guidance lagged the enforced/template contract, and the post-task retrospective then accepted `none` despite real lifecycle failures. Completion should expose its own high-signal failures and make the required verification contract actionable without creating another state system.

## What Changes

- Align central/template verification receipt guidance around the enforced automated-checks evidence marker.
- Make archive/preflight diagnostics point to the canonical required contract before mutation.
- Feed existing bounded lifecycle non-success evidence into the retrospective disposition gate.
- Prevent `checkpoint --result none` when meaningful lifecycle failures remain unclassified.
- Preserve deduplication and low ceremony for clean successful tasks.
