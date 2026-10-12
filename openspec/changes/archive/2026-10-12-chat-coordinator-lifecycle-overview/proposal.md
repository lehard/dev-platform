## Why

Publication candidates, lifecycle jobs and Requirements already carry durable state on GitHub, but a human cannot see the whole delivery path in one request. A PR labelled `publication:queued` may sit on a `reviewing` claim; a green workflow run with state `waiting` is not a merge; a merged PR still has open retrospective, terminal and cleanup obligations. Today the owner must keep a developer session alive or reconstruct this by hand from `publication_queue.py status`, `requirement_intake.py aggregate` and PR comments, and an exception (unclaimed job, expired claim, unavailable provider, exhausted repair) is only discoverable by looking.

BR-610 (hosted lifecycle workers) and BR-433 (local fallback) make the normal flow run without a session. This change gives the owner a fresh Codex or Claude chat that can be assigned the **chat coordinator** role, report the true state from GitHub alone, name exceptions, and apply only the already-supported, validated recovery commands after an explicit user decision.

## What Changes

- A read-only `scripts/lifecycle_overview.py` (summary of all open lifecycle work, drill-down by PR or Requirement, `--json`). It composes the existing derivations (`candidate_status`, `requirement_status`, `requirement_intake aggregate`, job claims and result receipts) and adds no state store.
- Human-facing delivery stages (`handed-off`, `delivering`, `merged-open-obligations`, `closed`, `needs-intervention`, `unknown`) and the full stage chain review → repair → re-review → finalize → integration → retrospective → terminal → cleanup with the current attempt/round.
- Named exception findings: unclaimed `next_job`, expired or stale claim, claim on an earlier head, unavailable provider/auth, exhausted repair/post-merge attempts, dangerous stale head. Absent or unreliable signals are reported as `unknown`; a live claim is never presented as confirmed execution.
- Permitted next actions derived from the same eligibility rules as the operator commands (one shared function used by `pr_review_gate.reoffer` and the overview). Finding-level escalations list no action and instead name the human decision that is needed.
- `publication_queue.py resume` and `switch-provider` gain a required-by-the-chat-flow `--expected-head` guard and always record the acting GitHub identity next to the existing reason, head and result.
- One idempotent, human-readable "needs attention" PR comment per exact escalation (`blocked-escalation`, exhausted post-merge obligation). The happy path posts nothing; Requirement closure keeps using the existing GitHub issue-close notification.
- A short role contract `docs/engineering/chat-coordinator.md` and a concern pointer in `AGENTS.md`, so any new session can take the role from the repository.

## Capabilities

### New Capabilities

- `chat-coordinator`: overview, exception detection, safe operator decisions, attention comment and role contract.

## Impact

New `template/scripts/lifecycle_overview.py` with its `scripts/` source adapter; `template/scripts/pr_review_gate.py` (shared eligibility, actor in the re-offer event), `template/scripts/publication_queue.py` (`--expected-head`, attention comment, shared candidate discovery), `template/scripts/lifecycle_workers.py` (candidate discovery reused, not duplicated), `.dev-platform.toml` (explicit `[chat_coordinator]` threshold), `docs/engineering/chat-coordinator.md`, `AGENTS.md` pointer, platform manifest and tests. No new service, storage, scheduler, LLM dispatcher or UI.

## Non-goals

A dashboard, desktop/web application, scheduler, second queue, LLM prioritisation, chat-to-chat messaging; automatic resolution of material findings; bypassing required CI, claims or branch protection; executing normal review/repair/merge stages from the chat; the worker liveness signal itself (BR-610/BR-433 own it, this change only reports it when present and `unknown` otherwise).
