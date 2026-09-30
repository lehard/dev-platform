## Why

The first full dogfood of the mandatory independent review gate confirmed the gate itself but exposed repeatable sources of artificial rework that would distort the upcoming measurement window:

- the reviewer runtime (CLI binary, CLI login, or the configured model for the logged-in account) is discovered unavailable only when the review is launched at archive time (process friction #223, #224);
- the reviewer diff includes lifecycle-generated evidence (previous review request/reports, dispositions, automated checks, verification receipt), so a fresh reviewer raises findings about the evidence itself and forces another cycle, although the review identity already treats those paths as non-candidate content (#227);
- a failed shared-delivery attempt leaves the lifecycle's own ready-for-integration receipt for a superseded head, and the next advance refuses until an operator moves it aside by hand (#236).

## What Changes

- Add a reviewer runtime readiness preflight to the independent review runner. Before any perspective launches, it resolves the provider, the exact selected model and the CLI binary, then performs one small headless probe with that exact model. A failure yields unavailable reports carrying the CLI's own bounded error and an actionable next step, without launching the perspectives. Expose the same check as `python3 scripts/independent_review.py preflight [change]`. No fallback model or provider is ever selected.
- Build the reviewer's candidate diff from exactly the task-owned content that the review task-content identity binds: lifecycle receipts, review evidence and archive-derived spec materialization are excluded from the diff, and the prompt tells the reviewer these paths are lifecycle evidence, not candidate content.
- Let the ready-for-integration receipt writer supersede its own receipt for the same Requirement, child Issue, change and source branch when the recorded head is a strict ancestor of the new head in the child's repository. A receipt with a different identity, an unrelated or divergent head, or one that cannot be proven remains a blocker.
- Add a representative happy-path regression: an unchanged final candidate gets exactly one platform-launched review round across archive, evidence commits and finish, and a repeated advance after head advancement needs no manual cleanup.

## Impact

Central dev-platform lifecycle scripts (`template/scripts/independent_review_runner.py`, `template/scripts/independent_review.py`, `template/scripts/requirement_integration.py`, with thin `scripts/` wrappers where needed), their tests, and the engineering workflow documentation that describes the review gate. Downstream-managed template files change only through the same shared scripts; the downstream default for independent review stays disabled. Existing publication, verification, independent-review and terminal-reconciliation guarantees are unchanged.

## Non-goals

Silent model/provider fallback, weakening the mandatory review, optimising unconfirmed hypotheses, or any telemetry/database/dashboard.
