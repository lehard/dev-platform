## Context

- `_advance_contributions` calls `ensure_integration_branch` (create-or-read, push on create) and only later `publish_composition`, whose `already_merged` branch calls `reconcile_composition`.
- The post-merge `terminal-reconciliation` job already calls `reconcile_composition` for a merged composition (`integration_contour`), so advance is not needed to finish a merged composition.

## Decisions

- **Refuse before any branch work.** The check runs first in `_advance_contributions`, using the same `gh pr list --state all --head <branch> --base main` inventory the single-child path uses, bounded at 100; any merged PR of the branch refuses. This removes the advance-side `merged-and-reconciled` route for a deleted branch; terminal delivery of a merged composition belongs to the post-merge jobs.
- **The refusal says what to do.** It names the merged PR, that advance would recreate the integration branch and break the post-merge jobs, and the supported steps: the coordinator's post-merge jobs (`work-next --kinds retrospective,terminal-reconciliation,cleanup --pr N`) and read-only `publication_queue.py status --pr N`.
- **Spec relation, recorded.** The accepted "interrupted run is resumed" scenario resumes an exact PR without duplication and blocks unsafe transitions with an actionable diagnostic; a merged composition is now such a blocked transition. The added requirement states it.

## Risks

- A Requirement that needs another composition round after a merged composition is refused; that path is not supported today either (it would recreate the branch on a different base).
