OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the documentation diff against the lifecycle-workers delta, proposal, design and tasks; every recorded value cross-checked against GitHub data; repository-owned selected checks on the committed head.
Automated-Checks-Evidence: automated-checks.json

Evidence sources actually read (2026-10-22): `gh run list --workflow lifecycle-workers.yml` from 2026-10-13 (441 runs); the job-summary outcome lines of all 306 non-cancelled runs created from 2026-10-19 to 2026-10-22 06:40 UTC (`gh run view --log`); the tracebacks of all 15 failed runs; job start/end times of the 19 `job-reviewed` runs; the `dev-platform-lifecycle-claim:v1`/`result:v1` and queue `admit` comments on PRs #628, #668, #669, #676, #681, #685, #687, #688, #690 and #691; the repository variable `DEV_PLATFORM_HOSTED_KINDS` (`review`); the commit that introduced the triggers (2026-10-13) and the #636 commit that fixed the friction failure. No synthetic job was created.

Completeness against the delta "The hosted pilot ends in a recorded placement decision":
- Prerequisite proven: `review` is recorded as hosted with observed constraints (runtime and credentials, credential boundary, workspace check, durations, trigger volume, duplicate claim, moved head, expired claim, advanced `main`, failure causes) and four real PR reviews by a `gha-` worker after the developer handoff with no manual command (#668, #669 twice, #687).
- Prerequisite unprovable: Requirement composition review, `repair`/`integration-repair` and the post-merge kinds stay on the local operator node with the BR-433 basis named; `finalize` is recorded as not enabled and not evaluated, by owner decision.
- Value not observable: per-job cost is recorded as unobserved with the reason; rate limits as not observed.
- Local fallback not widened: the comparison table and the closing sentence grant no merge or `main` authority.

Task 2.3: the observation exposed one open defect (the hosted worker claims a Requirement composition review it cannot complete and holds the job until the 30-minute claim expires). It was not fixed here; it is recorded as friction d8bba446017b and routed to the platform friction Issue. A second, already-fixed defect (friction recording without Backlog configuration) is recorded with its fixing PR #636. A managed-start friction seen while starting this task is recorded as a37b3242d988.

Execution: the documentation and tasks.md were written by the delegated Claude executor (haiku) under the delegated-child plan, from the supervisor-gathered evidence; the delegation was recorded with a clean containment postcheck. An earlier supervisor-written draft was withdrawn by a restore commit before the delegation opened (friction recorded).

Coherence: the design's "observe, do not stage" and "truthful limits" decisions hold; no job, claim, result, marker or queue format changed; the only edited platform file is `docs/engineering/hosted-lifecycle-workers.md`.

Not verified: provider cost and rate limits (no source); a hosted job running while `main` advanced (did not occur); hosted `finalize` (not enabled).

Checks actually run: `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/hosted-lifecycle-workers-placement-decision/automated-checks.json` on the committed head (results in automated-checks.json).
