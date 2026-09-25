# Proposal: Complete the single-change Requirement flow

## Why

The current supervisor rejects direct handoffs and one ready child, while terminal parent delivery is owned only by shared integration. This leaves the common N=1 path and delivered historical parents unfinished.

## Outcome

One Requirement with one technical child moves through handoff, managed execution, exact merge, parent Done and cleanup without an exception. Multiple children still use shared integration only when needed. Terminal reconciliation can recover previously delivered parents.

## Success evidence

Real orchestrator-to-executor regression scenarios cover deterministic and bounded direct handoff plus multi-child flow. Exact merge evidence gates parent Done. Historic Requirements #154, #157 and #158 reconcile without manual Done. Central and downstream guidance agree.

## Constraints

Preserve protected publication, required CI, managed provenance and other agents' work. Do not release Dev Platform or add a second status ledger.
