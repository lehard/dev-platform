## Decisions

- **Explicit delivery evidence.** An empty child set alone is not accepted: it is also the state of a Requirement whose children were never materialized. The operator names the merged quick PRs; the tool verifies each is merged through `gh pr view` and records them, so the receipt says what was reviewed.
- **No new identity rule.** The identity (parent body digest and child list) is unchanged; `quick_prs` is receipt content, validated on read (non-empty, unique `owner/repo#N` strings when the child set is empty).
- **Explicit failure.** An unmerged or unreadable PR, an empty child set without `--quick-pr`, or a receipt with an empty child set and no quick PRs stops with the next action; nothing is substituted.
- **Scope.** Terminal reconciliation of a Requirement without managed children is not changed here.
