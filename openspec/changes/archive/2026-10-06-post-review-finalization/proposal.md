## Why
Archive before external review forces reopen mechanics when review demands changes. Archive belongs after review/repair. Parallel archives of the same capability create artificial conflicts in `openspec/specs/*`.

## What Changes
- A finalize job runs the archive lifecycle on the candidate with trusted code, using reused evidence, and moves the candidate to ready; content changes afterwards return it to review.
- The completed-but-active rule moves from publication to integration admission and merge.
- Archive-derived current-spec paths are re-derived on the actual integration base by re-applying the candidate's archived deltas; a successful re-application is bookkeeping only and never replaces integration checks or hides contract conflicts.

## Capabilities
### Modified Capabilities
- `completion-lifecycle`: completed-change rule at integration; finalize placement.
- `publication-queue`: admission requires finalization; derived spec re-application.

## Impact
`openspec_lifecycle.py`, coordinator finalize/admission, platform CI lifecycle check.

## Outcome and Evidence
Fixture: two candidates extending the same spec integrate sequentially without manual conflict resolution; a semantic conflict still fails checks; finalize keeps review evidence valid.

## Non-goals
Integration repair (autonomous-integration-contour).
