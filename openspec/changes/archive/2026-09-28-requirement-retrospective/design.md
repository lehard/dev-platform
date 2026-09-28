# Design

Use the existing `agent_friction.py` event router for meaningful findings. Add a bounded Requirement checkpoint command and receipt scoped by exact parent identity and current linked child evidence. The receipt records `none` or known event ids and enough source identity to reject stale or ambiguous completion. Store local operational evidence beside existing machine-local Requirement state, not as a second durable task ledger. The parent terminal helper requires that checkpoint before setting Project Done or closing the Issue. The execution supervisor returns an actionable retrospective step when this is the only remaining gate.

The retrospective reviews the entire Requirement path: initial intent, evidence and ADD/intents where used, handoff, child execution interaction, and delivery. It classifies only new meaningful findings; child-specific findings already handled by child checkpoints are referenced, not duplicated. A new lifecycle stage must either route meaningful friction itself or be covered by its nearest enclosing retrospective.

## Risks

- A local receipt may be unavailable on a different machine. The terminal command must fail with a precise recovery instruction and allow a truthful rerun; it must never infer `none`.
- Current Requirement or child state may change after checkpoint. Bind the receipt to current authoritative identity and reject stale state at completion.
- The first delivered child of this Requirement introduces the gate during self-hosted delivery. Keep the checkpoint command usable before terminal integration of the parent.
