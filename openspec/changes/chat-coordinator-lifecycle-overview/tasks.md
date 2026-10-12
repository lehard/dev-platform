## 1. Shared building blocks

- [ ] 1.1 Extract `reoffer_plan(candidate, claim, action)` from `pr_review_gate.reoffer`; `reoffer` calls it; add the `actor`/`via` fields to the re-offer event and resolve the actor from the authenticated GitHub identity (fail if unresolved).
- [ ] 1.2 Extract the worker candidate discovery into one function in `lifecycle_workers.py` and use it from `main()` and the overview.
- [ ] 1.3 Add `--expected-head` to `publication_queue.py resume` and `switch-provider`, refusing before any write on a head mismatch.

## 2. Overview

- [ ] 2.1 Implement `template/scripts/lifecycle_overview.py` (`summary`, `show --pr`, `show --requirement`, `--json`) and its `scripts/` source adapter: delivery stage projection, stage chain with attempts, merged-vs-Done separation, claim-only executor attribution, exception findings, permitted actions via `reoffer_plan`, `unknown` on unreadable sources.
- [ ] 2.2 Add the required `[chat_coordinator] unclaimed_job_after_minutes` setting to `.dev-platform.toml` with explicit failure when missing/invalid.

## 3. Exception indication

- [ ] 3.1 Post the idempotent human-readable attention comment on first `blocked-escalation` per exact head/reason and on first observed exhausted post-merge obligation; surface posting failure loudly after the transition is published.

## 4. Role contract

- [ ] 4.1 Write `docs/engineering/chat-coordinator.md` and the `AGENTS.md` concern-table pointer; keep `AGENTS.md` pointer-only; link check passes.

## 5. Tests

- [ ] 5.1 Fixture-based tests for each stage and each exception finding (including unknown on unreadable input and claim-not-running), the merged-not-Done case and head-moved/live-claim refusal.
- [ ] 5.2 Agreement test: for every candidate state, the overview's permitted actions equal what `reoffer` accepts; finding-level escalations list no action.
- [ ] 5.3 Attention comment: posted once per exact escalation, not on successful stages, failure is not swallowed; actor recorded on resume/switch.
- [ ] 5.4 New-session scenario: a fixture-driven run from a cold checkout reproduces the same overview from GitHub snapshots only.

## 6. Verification and delivery

- [ ] 6.1 Regenerate the platform manifest; required platform checks; truthful semantic verification; archive; retrospectives; publication.
