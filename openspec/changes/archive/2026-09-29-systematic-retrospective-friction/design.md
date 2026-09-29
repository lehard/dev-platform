# Design

Use the existing machine-local friction log and checkpoint receipts. A bounded review inventory should surface concrete task-path signals from existing evidence and require explicit disposition for meaningful candidates before `none`; it should not record command history or every harmless flag. The agent still judges semantic relevance and records high-signal findings with `agent_friction.py record`. Existing fingerprint routing must preserve repeated occurrences on an open process issue. Parent review covers intake through delivery and does not replace child reviews.

The review should be short for clean paths and fail closed only for concrete, task-attributed evidence. Unknown or external ownership is not a reason to discard an observed discrepancy. Avoid broad shell-history collection because it is incomplete and may contain secrets. Keep raw evidence local and sanitize routed occurrences.

Risks: over-reporting harmless deviations, leaking command detail, or blocking clean completion. Bound candidate types and redaction; use focused tests for clean path and #172-style recurrence/override/drift.
