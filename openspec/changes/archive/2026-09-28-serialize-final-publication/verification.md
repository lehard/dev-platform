# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the accepted Requirement, proposal, design, delta scenarios and implementation, plus automated checks below.
Automated-Checks-Evidence: automated-checks.json

The source queue admits exact validated PR heads with GitHub comment ordering. One Actions concurrency group selects the oldest queued PR; every merge uses the actual head, required checks and an expected-head guard. The worker detects changed task heads, relevant main path overlap, failed checks and unprovable recovery. A second invocation resumes from GitHub markers and PR state. The existing finish path still handles local and managed-task terminal reconciliation. The workflow is activated only after its bootstrap PR reaches main.

Checks performed before this receipt: `python3 -m compileall -q template/scripts scripts`; `python3 -m ruff check scripts template/scripts tests`; `python3 scripts/managed_projects.py validate`; `python3 scripts/run_test_groups.py --all` (15 groups, all passed); `python3 scripts/run_test_groups.py --verify-coverage` (1,421 tests discovered at that run, no gaps); `python3 template/scripts/openspec_lifecycle.py check`; `openspec validate serialize-final-publication --strict`; `git diff --check`. The additional two-agent test was run separately after the full suite and passed, bringing the current queue test module to 14 cases; archive checks will run on the committed final candidate.

The GitHub-hosted coordinator cannot execute on this branch before its workflow is merged into main. Live App permission and protected-merge behavior will first be exercised by the next admitted source PR; a denied mutation remains visible in the workflow run and does not claim Done.
