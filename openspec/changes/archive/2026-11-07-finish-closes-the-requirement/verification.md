# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual walk of every scenario in the delta against the code and tests/test_finish_closes_requirement.py and tests/test_worktree_hygiene.py; selected checks and strict `openspec validate` ran locally.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## What was checked

- Last child closes the Requirement and reports it: `ParentClosureTests`, `FinishClosureTests`.
- Open children are named and nothing closes; an unreadable child status is an error: `ParentClosureTests`.
- Closure prevented, cause and retry named, merge stated as standing: `FinishClosureTests`.
- Retry closes, and a second retry on a closed Issue reports only that it is closed: `FinishClosureTests`.
- The notice before publication prints a gap, stays silent otherwise, and a failed check is reported without stopping publication: `NoticeTests`.
- Status obligation pending, warning, absent: `StatusTests`.
- A later finish consumes earlier deferred records, keeps its own and an unsafe one, names each: `test_a_later_finish_consumes_earlier_records_and_keeps_its_own_and_the_unsafe_one`, `EarlierCleanupOutputTests`.
- The GitHub retry path that skips publication for a merged PR was read in `finish_task.py`; it is existing behaviour and no new test covers it.

## Not checked here

The live closure happens after this receipt, on this same Requirement, and is reported on the Requirement.
