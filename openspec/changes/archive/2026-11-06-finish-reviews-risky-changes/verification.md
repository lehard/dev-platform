# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual walk of every scenario in the delta against the code and tests/test_independent_review.py; selected checks and strict `openspec validate` ran locally.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## What was checked

- Risk rule, generated files, source layout, missing, ambiguous and empty surface: `RiskyChangeTests`.
- Required predicate for quick and managed tasks, disabled repository: same tests and the existing managed review tests.
- Quick evidence: unchanged rerun launches nothing, changed content is reviewed again, nothing enters the tree.
- Material finding and a reviewer that cannot run stop with the cause and next commands: `RiskyChangeTests`, with a fake launcher.
- Live before this receipt: `independent_review.py preflight quick-task` refused with the expired CLI session, and passed with the OAuth token in the environment.
- Live: one `finish` launched the real reviewer (2 perspectives, 91 s) and stopped on a material finding: the finalize requirement was not in the delta. The delta now carries it; three advisory findings were fixed too.
- `--no-checks` not skipping the review was checked by reading `finish_task.py`; no test covers it.

## Not checked here

The live `finish` with a real reviewer happens after this receipt, on this same change. The non-risky live `finish` needs this code on main. Both are reported on the Requirement.
