# Design: Read-through Requirement stage projection

## Inputs

Aggregation reads the Requirement's local pre-authoring state and the already authoritative linked-child lifecycle observations. It derives a display stage and machine-readable reason; it does not persist a new business status.

## Precedence

Unreadable, stale, contradictory, or explicitly blocked sources win over optimistic stages. Before children exist, a valid current orchestrator state distinguishes active evidence/pre-authoring, design/human decision, and ready-to-materialize. Once a child exists, its real implementation lifecycle determines implementation and completion. All required children complete produces done; any unresolved blocked/unknown source remains visible.

## Compatibility

Existing child-only aggregation stays available, with the new projection additive and documented. The mapping stays provider-neutral and avoids Project-field mutations.
