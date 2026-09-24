# Proposal: Merge overlapping verified Requirement children

## Why

#164's exact child deltas overlap accepted spec and integration code that landed on main after the children were verified. Exact patch replay correctly fails but cannot complete the delivery.

## Change

Provide a bounded merge-backed candidate for an exact sequential child chain. The candidate starts at current main and merges the final child head, whose ancestry proves every prior child head. Conflict resolution is explicit and reviewed in an isolated worktree. Exact parents, receipts, manifest and full checks precede protected publication. Prior candidate generations remain untouched.

## Success

The shared #164 candidate preserves current main and child behavior, passes relevant/full checks, merges through one protected PR, and only then reconciles children and Requirement.
