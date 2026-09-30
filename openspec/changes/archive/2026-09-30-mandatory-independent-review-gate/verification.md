# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the proposal, design, completion-lifecycle delta and implementation against the approved ADD and Requirement acceptance evidence; strict OpenSpec validation; automated platform checks; and a real platform-launched independent review (Claude Code headless reviewer, fresh read-only processes) of the committed candidate.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Semantic review

- Platform-launched reviewer: `independent_review.py run` launches one fresh process per perspective through the Codex (`exec --sandbox read-only --ephemeral`) or Claude Code (`-p --tools Read,Grep,Glob --no-session-persistence --strict-mcp-config`) adapter; reports carry `launch_evidence: platform-observed`, the enforced mechanism, selected model provenance and the output digest. Provider defaults to the task route; cross-provider only through `[independent_review] provider`.
- Proven read-only/fresh: before/after content snapshots of the task worktree and integration checkout; any mutation, missing binary, nonzero exit (with the CLI's own bounded error), timeout (whole process group killed) or malformed output yields an `unavailable` report that blocks.
- Candidate binding: review-scoped task-content identity excludes only lifecycle receipts/review evidence and, after archive, the own-capability `spec.md` materialization; tests prove invalidation on task change and on a pre-archive accepted-spec edit, and acceptance across archive move and an irrelevant main merge.
- Dispositions: separate record bound to the report digest; `fixed` refused; unresolved material findings block; imported reports cannot claim platform-observed launch.
- Gate and resume: archive runs a missing/stale review after cheap gates and before `select_checks`; finish re-validates before publication; `finish_task.py --status` and `execute_requirement.py advance` (implement-child) expose the derived state and next command. Quick tasks without managed provenance are exempt; template default stays opt-in.

## Independent review of this change

The first real runs were truthfully blocked: the bundled Claude CLI reported "Not logged in", and the Codex standard model was unsupported for the local account. Both surfaced as `unavailable` reports, as specified. After the operator logged in the Claude CLI, the review ran through `DEV_PLATFORM_CLAUDE_BIN` and returned 3 spec-fidelity and 5 engineering-quality findings, all advisory. Dispositions:

- Fixed after that review: the timeout now kills the reviewer's process group; own-capability spec exclusion is narrowed to `spec.md` and applies only after archive; `record` refuses reports claiming platform-observed launch. Each fix has a regression test. The fixes changed the candidate, so that first review is superseded and is not the cited evidence.
- Review evidence is not committed ahead of the candidate it describes: the cited `independent-review-request.json` and `independent-reviews/` reports are produced by the archive helper's review of the final candidate and enter the repository only with the archive commit. Archive cannot complete unless that review validates, so the archived reports, together with any `independent-review-dispositions.json`, are the authoritative record of its findings. A second review run on an intermediate commit correctly blocked on committed stale evidence and on this receipt's earlier wording, which anticipated its result; both were fixed rather than rejected.
- Accepted as documented limitations: central enablement lives in the machine-local, excluded `.dev-platform.toml` and is applied after merge (design "Scope and compatibility"); concurrent writes by other agents in the integration checkout fail closed as a false "mutated" report; review state is surfaced on the resume points (`implement-child`, task status) rather than every advance outcome; the runner uses internal helpers of sibling platform modules within the same template; the candidate diff is unbounded, and oversized reviews fail closed through timeout or malformed output.

## Observed checks

- `python3 -m unittest tests.test_independent_review tests.test_task_content_identity tests.test_shared_writer_guard` passed (40 tests).
- `python3 -m compileall -q template/scripts scripts` passed; `python3 scripts/managed_projects.py validate` passed.
- `DEV_PLATFORM_TEST_JOBS=3 python3 scripts/run_test_groups.py --all` on the earlier candidate: 14 of 15 groups passed; `fast-d` failed only on `test_shared_writer_guard`, whose reviewed-writer baseline lacked the runner's temporary-directory writes (introduced, fixed in the same change). The final candidate is validated by the archive helper's `select_checks` run, whose record `automated-checks.json` is likewise produced by archive.
- `openspec validate mandatory-independent-review-gate --strict` passed with OpenSpec 1.13.2.

## Post-archive integration fix

The first single-child finish after archive failed: the completion-evidence archive transition accepted a newly generated `automated-checks.json` but not the archive-produced review evidence (`independent-review-request.json`, `independent-reviews/`, dispositions), so it rejected the validated evidence as stale. `evidence_matches_checkout` now treats those files like the generated automated receipt, because `require_review_evidence` binds them to the task content separately; any other new archive file is still rejected. `tests.test_openspec_lifecycle` covers both cases (29 tests passed). Because the fix changed the candidate, the independent review was rerun on the archived change and automated evidence was refreshed afterwards; the committed reports and `automated-checks.json` are those runs.
