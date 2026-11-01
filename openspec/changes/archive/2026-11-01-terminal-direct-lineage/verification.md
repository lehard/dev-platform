OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the publication-queue delta, proposal, design and tasks; unit tests; a read-only live walk of the private Backlog; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Coordinator decision D1=B with conditions, as amended on 2026-11-01:
  - only open Issues are walked;
  - an explicit page cap applies;
  - only trusted-author markers count;
  - a trusted successful terminal result exits idempotently;
  - no handle is logged or posted.
- `run_terminal` sends a managed candidate without BR branch identity to `run_direct_terminal`. That function runs `terminal_recorded`, then `direct_source` (archived handle at the merged head, then `private_lineage.issue_for_handle`), then `reconcile_child`.

## Completeness

- `DirectLineageWalkTests`:
  - one trusted marker resolves after `require_handle`;
  - an Issue with more comments than one page is read in full;
  - an untrusted marker is ignored;
  - a marker for another change or several markers stop;
  - the page cap is an explicit error that never names the handle.
- `PostMergeJobTests`:
  - a direct candidate resolves through the handle and reconciles, with receipt `task-recorded: Issue #960`;
  - a recorded result exits before the walk;
  - an unprovable lineage blocks;
  - `terminal_recorded` trusts only trusted successful results.
  - These replace the earlier test that expected a direct candidate to stay blocked.
- A read-only live walk against the private Backlog resolved the archived handles of `split-long-requirements-part-2` to Issue 948 and of `split-long-requirements-part-3a` to Issue 960.

## Independent review

- First round: ready, five advisories.
  - Fixed:
    - `tasks.md` had been truncated by an editing slip and is restored;
    - the archive is matched exactly as `YYYY-MM-DD-<change>`, so `-<change>` lookalikes no longer match;
    - a failed GraphQL read reports only the `gh` exit status, so GitHub text that names the private repository never reaches a public receipt.
  - Kept, by coordinator decision: an Issue closed while its result comment was lost stops explicitly with "no open Issue carries this handle (already closed or missing)" instead of walking closed Issues.

## Not verified / limits

- No live terminal job ran. The live acceptance (#948 and #960 closed by the terminal job) waits for merge and a coordinator re-offer of those post-merge jobs.
- Existing behaviour, reported but not changed: the Requirement-child path's `reconcile_child` failure message names the full private Issue reference.
