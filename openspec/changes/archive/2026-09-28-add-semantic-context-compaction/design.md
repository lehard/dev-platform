# Design: Compact at useful boundaries, not arbitrary fullness

## Dependencies and baseline

This change follows #131 and #132. Cold observations keep exact large evidence out of hot context, and verified reducer receipts reduce noisy log payload. Compaction then addresses the remaining live conversation/history at safe semantic boundaries.

The existing agent-workflow contract already says a durable handoff is unnecessary when same-context compaction is sufficient. This change defines that same-context behavior without creating a second handoff format.

## Decisions

1. **Semantic opportunities.** V1 recognizes a small bounded set such as completion of a plan/subtask and transition into a verification phase. Runtime adapters may expose equivalent boundaries without changing canonical semantics.
2. **Economic gate.** At an opportunity, estimate whether expected future replay avoided is materially larger than the cost/risk of rebuilding a compact context. The gate uses simple inspectable inputs; no learned optimizer in v1.
3. **No threshold-only policy.** Context fullness may be an input but is not sufficient by itself.
4. **Truth-preserving compact state.** Preserve exact managed task/OpenSpec identity, verified facts with canonical references, unresolved assumptions/blockers and next intent. Do not copy large cold evidence when a valid handle/reference is sufficient.
5. **Evidence remains external.** Compact prose is navigation state, not authority over repository/OpenSpec/test evidence.
6. **Fail open.** Unsupported/failed compaction continues with current context; it does not corrupt managed state.
7. **Dogfood before enforcement.** Record opportunities, decisions, before/after deterministic payloads and subsequent replay where observable. Runtime token/cache fields remain exact-only.
8. **No durable handoff duplication.** Cross-session/provider/person continuation remains owned by the existing interoperable handoff contract.
9. **Cheaper first.** At each opportunity, identify whether repeated instructions, eagerly loaded rarely used capability definitions, or avoidable prompt-boundary churn account for the payload. Record this bounded assessment and prefer an available safe static reduction before evaluating compaction for the remaining live history. This is an advisory check, not a general prompt optimizer or a prerequisite to implementing runtime capability loading.
10. **Resume validation.** Before relying on a recorded compact continuation, recheck each repository digest and cold-observation handle against current exact sources. A stale continuation reports its reason and yields no ready continuation.

## Verification

Controlled runs must demonstrate both gate outcomes, continuation after a successful compact, safe no-op/fallback, preservation of blockers and exact evidence references, and rejection/surfacing of stale referenced evidence.
