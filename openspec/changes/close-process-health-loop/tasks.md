## 1. Add process-evidence linkage to managed authoring

- [x] 1.1 Define the minimal canonical representation for zero-or-more process evidence references on a managed task.
- [x] 1.2 Add repeatable evidence input to managed-task authoring and validate repository/issue/process-label eligibility.
- [x] 1.3 Reconcile linked open evidence idempotently to `process:managed` with one bounded backlink.
- [x] 1.4 Add focused tests for multiple evidence issues, invalid/non-process references, repeat invocation and partial-linkage recovery.

## 2. Resolve linked evidence only after terminal managed success

- [x] 2.1 Extend terminal completion to read the canonical evidence linkage after existing delivery authority is established.
- [x] 2.2 Close linked still-open evidence with `completed` reason and bounded task/implementation provenance.
- [x] 2.3 Keep failed/blocked/cancelled/non-terminal work from resolving evidence.
- [x] 2.4 Prove completion/reconciliation is idempotent and recurrence after closure creates a new open friction issue.

## 3. Make Weekly Process Backlog Review freshness-aware

- [x] 3.1 Record review timestamp, exact current `main` SHA and previous-review boundary in every report.
- [x] 3.2 Read bounded managed-task and recently merged/closed context since the previous review.
- [x] 3.3 Classify open process evidence as unmanaged, managed, likely resolved/superseded, needs evidence or ready for human decision.
- [x] 3.4 Cluster multiple symptom issues by root cause before recommending managed work.
- [x] 3.5 For likely resolved/superseded candidates, inspect current repository evidence instead of relying only on stale issue prose.
- [x] 3.6 Preserve the advisory safety boundary: no automatic managed-task creation, source-issue closure or code changes from review.

## 4. Promote the bounded contract downstream

- [x] 4.1 Add the accepted process-health workflow/labels/config to the managed-project template without per-project forks.
- [x] 4.2 Preserve project-local friction routing and central `scope=platform` routing.
- [x] 4.3 Validate template rendering/adoption and ordinary platform rollout compatibility.
- [x] 4.4 Update `docs/engineering/chatgpt-project-protocol.md` with the concise shared Process Health Review contract; keep project-specific instructions as thin trigger/parameter adapters.

## 5. Reconcile current evidence and verify

- [x] 5.1 Run one bounded current-state review of the existing dev-platform process backlog against exact current `main`. Evidence: `process-health-review.md` records the exact SHA, boundary and bounded query.
- [x] 5.2 Backfill only unambiguous current managed relations; leave ambiguous historical evidence untouched. Evidence: no open source process evidence was found, so no issue was mutated.
- [x] 5.3 Confirm already-completed linked work can be represented/resolved without creating duplicate remediation tasks. Evidence: no linked source evidence exists in the current bounded backlog; terminal resolution is covered by focused idempotency tests.
- [ ] 5.4 Run the authoritative risk-selected lifecycle/agentic workflow checks and strict OpenSpec validation once for the final behavior change.
- [ ] 5.5 Archive through the normal managed lifecycle with the review report as acceptance evidence.
