# Proposal: Mandatory platform-launched independent review gate

## Why

Independent review evidence is already modeled (two perspectives, candidate identity, truthful unavailability, material-finding disposition), but it is opt-in, the platform never launches a reviewer, and fresh-context/read-only properties are only self-attested. An agent therefore has to remember to obtain review, and nothing proves the review was independent. A Requirement cannot run to merge from Codex or Claude Code without manual reminders about review.

## What changes

- The platform launches each review perspective itself as a fresh, non-resumable process through a provider adapter: Codex `exec` in its read-only sandbox, Claude Code headless print mode restricted to read-only tools with session persistence disabled. Reports carry platform-observed launch evidence; hand-written reports no longer satisfy a required review.
- Read-only execution is proven by the runtime-enforced surface and a before/after content postcheck of the task worktree and integration checkout; an unprovable property yields an unavailable report that blocks.
- Evidence binds to the task-content identity of the candidate, excluding only lifecycle receipts/review evidence and archive-derived spec materialization, so archive bookkeeping and irrelevant main merges keep it valid while any other change invalidates it.
- Reviewer reports stay immutable; material findings are rejected with rationale in a separate disposition record or fixed through a fresh review of the new candidate.
- When review is required, archive preflight automatically runs a missing or stale review before expensive validation, finish re-validates it before publication, and task status plus Requirement advance report the next review step from file-backed evidence.
- dev-platform requires review for managed changes; quick tasks without managed provenance are exempt; the downstream template default stays opt-in.

## Success evidence

Automated tests cover both adapters' argv and failure modes (missing binary, timeout, malformed output, workspace mutation), candidate invalidation versus accepted archive/merge transitions, disposition handling, archive auto-run and finish gating, quick-task exemption, and resume reporting. This change's own completion is gated by a real platform-launched review.
