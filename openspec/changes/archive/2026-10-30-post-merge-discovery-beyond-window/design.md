## Context

`candidate_prs(repo, include_merged)` returns open PRs (paginated) plus merged PRs from one unpaginated page of `pulls?state=closed&sort=updated&per_page=50`. `work-next` and `lifecycle_overview.overview` both use it; `work_next` filters by `only_prs`. A coordinator-merged candidate carries a coordinator record with `attempts["post-merge"] = 1` and the projected label `lifecycle:merged`; `candidate_lifecycle.post_merge_progress` derives its next post-merge job, or none when the chain is complete or the PR was merged without the coordinator.

## Decisions

- **Label-indexed discovery, self-settling.** Discovery reads `issues?state=closed&labels=lifecycle:merged` completely and adds each PR not already in the window and not labeled `post-merge:settled`, read through `pulls/N`. Items without `pull_request` are not PRs and are not candidates. `work_next` gets an optional `settle(number)` callback; it is called (outside the per-PR skip handling, so a failure fails the run) for a derived `merged` candidate with no `next_job`, no `post_merge_exhausted` and no settled label. `work-next` passes a callback posting the label unless `--dry-run`; the overview stays read-only and passes none. Absence of the label is the safe default: an unlabeled PR is always re-read. Rejected: paginating all closed PRs and reading every comment list each run (cost grows with history); GitHub search (index lag cannot prove completeness); a label set at merge and removed on completion (needs a backfill and fails open when the removal is missed).
- **Recent window kept.** The window still supplies merged PRs without the `lifecycle:merged` label (contribution integration) and keeps the current overview content; the change only adds candidates.
- **`--pr` reads directly.** With `only_prs`, `candidate_prs` returns each named PR from `pulls/N`: open always, merged when merged candidates are requested, closed-unmerged never (as the listing).
- **No fallback.** Every read goes through `_gh_json` (or the overview's cached read), which raises on failure; nothing substitutes a partial list.

## Risks

- The first runs after release read about 110 unsettled PRs; bounded and one-off, the read cache revalidates by ETag.
- A merged PR whose `lifecycle:merged` projection failed and that left the window stays invisible as before; the label projection is part of the merged transition.
