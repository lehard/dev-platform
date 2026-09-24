# Proposal: Derived Requirement board state

## Why

Read-through aggregation exists, but the human-facing Project card can remain Ready while execution is active, or appear Done before shared delivery. The board must reflect authoritative evidence without becoming a competing lifecycle.

## What changes

Add a deterministic Project Status projection and reconciliation entrypoint for Requirements. It reads the current pre-authoring stage, linked-child observations and protected integration terminal evidence. It updates only the parent Requirement card; children remain internal. Unknown or contradictory inputs fail closed.

## Success evidence

Tests cover every meaningful stage, drift repair and the terminal merge gate. Live #164 dogfood proves that Done follows merged protected publication and local reconciliation, never a handoff or child receipt alone.

## Constraints

Reuse existing Project and Requirement adapters. Do not store another independent status ledger or hide missing evidence.
