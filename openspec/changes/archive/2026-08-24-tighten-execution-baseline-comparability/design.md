# Design: Decision-quality execution baseline

## Decisions

1. **Verified is the comparison gate.** `sufficient` requires at least 15 verified managed executions; launched-only observations remain visible but do not satisfy the decision gate.
2. **Coverage stays explicit.** The report exposes missing verification and sparse/incompatible efficiency fields; 15 is not treated as a magical guarantee when coverage is unusable.
3. **Semantic identity before normalization.** A canonical `model_request_count` (or equivalent final name) may be populated only when the adapter can prove one counted event means one model request. Provider-specific turns/messages may be retained separately but are not automatically compared.
4. **Historical compatibility.** Existing `request_count` records remain readable and source-attributed; they are not retroactively relabelled as a stronger semantic.
5. **Durable verification lookup.** Verification evidence for durable routing records must be resolved from the integration-owned active/archive lifecycle rather than depending on a disposable task worktree.
6. **No policy action.** This change only improves measurement truthfulness; it does not enforce budgets or switch runtimes.
