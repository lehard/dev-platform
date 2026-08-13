# Design: Minimal process-health lifecycle

## 1. Evidence remains the inbox

An open `process` issue is the durable sanitized evidence record. Repeated occurrences continue to deduplicate into the same open issue by the existing fingerprint contract. No new database or problem object is introduced.

Only one new lifecycle label is justified: `process:managed`. Closed GitHub issues are the archive. Duplicate, not-planned and superseded decisions use GitHub closure semantics rather than a parallel status taxonomy.

## 2. Explicit managed linkage

Managed-task authoring accepts zero or more explicit process evidence references. Each reference is validated as an accessible suitable process issue. The authoritative managed task stores a bounded canonical list of those references in a deterministic representation that completion can read directly; human-readable backlinks may accompany it.

After the managed issue/package has been safely created, linkage reconciliation is idempotent: each still-open evidence issue retains `process`, gains `process:managed`, and gets at most one bounded backlink to the Development Backlog task. Partial linkage failures are actionable/retryable and must not silently invent a second task.

The relation must not depend on GitHub full-text indexing of hidden comments as its only lookup path.

## 3. Resolution follows terminal delivery

A process issue is not resolved merely because a task was authored or started. After the exact managed task reaches the existing terminal-success authority (`MERGED` plus required local/Project reconciliation), the completion path reads its explicit evidence linkage and closes only linked still-open issues with `state_reason=completed` and one bounded resolution note identifying the backlog task and implementation provenance.

Failed, blocked, abandoned or not-yet-terminal work leaves evidence open. Re-running completion is idempotent. If an already-closed evidence issue is encountered, completion does not rewrite its historical reason unless an explicit repair/migration operation is being performed.

Because the friction router deduplicates only against open matching issues, a recurrence after a resolved issue naturally creates a new open record and is visible as a regression candidate.

## 4. Freshness-aware review

Each weekly report states `reviewed_at`, exact target `main` SHA, and a previous-review boundary. The workflow reads a bounded current set of open process issues plus enough Development Backlog/merged-PR/current-repository context since the previous boundary to distinguish:

- active/unmanaged;
- managed;
- likely resolved or superseded;
- needs more evidence;
- ready for human decision.

It clusters symptoms by likely root cause before recommending work. Counts of issues are not treated as counts of required changes.

For likely-resolved/superseded candidates the workflow must seek current-state evidence rather than trusting old issue prose. It remains advisory and read-only with respect to source process issues: it may create the dated review report, but it does not create managed work or close/remediate source issues on its own.

## 5. Downstream adoption

The central workflow remains the proving ground. Once the new central acceptance scenarios pass, the managed-project template exposes the same bounded project-level review capability and required label/config support. Project-level friction remains in the project repository; `scope=platform` continues to route centrally.

Do not introduce a mandatory cross-repository dashboard. A GitHub Project may later consume the same issue state as a presentation layer without becoming canonical.

The canonical ChatGPT Project protocol should define the same review semantics once, including exact-current-state/freshness requirements and the read-only-before-fixation boundary. Project-specific ChatGPT Instructions should remain a thin trigger/parameter adapter rather than copying the full procedure.

## 6. Bounded reconciliation of existing evidence

Acceptance includes one current-state reconciliation pass. It may backfill explicit linkage for currently open process issues already unambiguously covered by existing Development Backlog tasks, and may resolve those whose linked managed implementation is already terminally complete, but it must not mass-rewrite ambiguous historical issues. Uncertain cases remain evidence for human decision.
