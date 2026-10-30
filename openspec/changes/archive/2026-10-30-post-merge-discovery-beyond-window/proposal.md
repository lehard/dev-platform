## Why

`lifecycle_workers.candidate_prs` offers merged candidates from one page of the 50 most recently updated closed PRs (`MERGED_DISCOVERY_PAGE`). A merged PR whose post-merge obligation is still open silently leaves that window as newer PRs close: on 2026-10-28 lehard/dev-platform#678 and #681 were already outside it and invisible to both the post-merge worker and `lifecycle_overview.py`, and #685 was 50th. `work-next --pr N` only filters the same list, so it cannot reach such a PR either. This is silent loss of work, against the fail-explicit rule.

## What Changes

- Merged discovery adds, beyond the unchanged recent window, every closed PR labeled `lifecycle:merged` (the label the coordinator projects on its merged record) that is not labeled `post-merge:settled`. The label listing is read completely (paginated); any read failure fails the command naming the read instead of returning a truncated list.
- `work-next` marks a merged candidate whose post-merge chain is settled (no next job, no exhausted obligation) with `post-merge:settled` (not in `--dry-run`), so it is not re-read by later discovery. A failed label write fails the run. An exhausted or still-open obligation is never marked.
- `work-next --pr N` reads each named PR directly (`pulls/N`) instead of filtering the listing, so it works for any merged PR with a lifecycle record whatever its position. `lifecycle_overview.py show --pr N` already reads directly and stays so.
- The overview states the new bound.

## Impact

- `template/scripts/lifecycle_workers.py`, `template/scripts/lifecycle_overview.py`, tests, `docs/engineering/chat-coordinator.md`, platform manifest.
- Specs: lifecycle-workers (added: complete post-merge discovery, shared by the overview through its existing "same candidate set" rule).
- One-time cost: the first runs read every unsettled `lifecycle:merged` PR (about 110 on lehard/dev-platform); afterwards only unsettled ones are read.
- No change to post-merge steps, attempt limits or the recent window itself.

Note on the Requirement: it says `lifecycle_overview.py show --pr N` cannot see an out-of-window PR; `show_pr` already reads `pulls/N` directly, so only the summary and `work-next --pr` were affected.
