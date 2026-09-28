# Decision registry

This registry preserves the reasons behind consequential Dev Platform decisions across agent runtimes and conversations. Read a record when its scope reaches the work at hand; the index is a map, not universal prompt context.

| ID | Decision | Scope | Status |
| --- | --- | --- | --- |
| [DEC-0001](0001-teamai-substitution.md) | TeamAI substitution after the v0.25.0 pilot | External agent infrastructure | Current |

## Record contract

Record a decision when losing its rationale or reconsideration conditions would materially affect later platform work. Minor implementation choices belong in the relevant OpenSpec change. Each record states:

- a stable ID, title, scope, decision date and repository revision;
- its status and the accepted current choice;
- rejected-for-now and deferred/watch alternatives, with reasons;
- evidence and source links rather than copied transcripts;
- exact events or evidence that trigger reconsideration;
- `Supersedes` and `Superseded by` links, using `None` when absent.

When a decision changes, create a new record with a new ID and a `Supersedes` link. Add only the new ID to the earlier record's `Superseded by` field; preserve its dated conclusion, rationale and evidence. Update this index to identify the current record. A revisit trigger prompts a new evaluation; it does not itself authorize implementation.

This registry is historical decision context. [OpenSpec](../../openspec/specs/) and active deltas define accepted executable behavior. Business Requirements and Backlog track work; task-local ADD files support pre-authoring. If a record disagrees with an accepted behavior contract, follow the contract and resolve the discrepancy through the managed change lifecycle.
