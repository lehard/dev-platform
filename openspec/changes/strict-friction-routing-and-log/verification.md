OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the implementation diff against the strict-friction-routing-and-log delta, proposal, design and tasks; repository-owned selected checks on the candidate head
Automated-Checks-Evidence: automated-checks.json

Implementation: a delegated native Claude executor implemented tasks 1.1-3.1 in `template/scripts/agent_friction.py` with tests; the supervisor reviewed the full diff before commit.

Completeness: every proposal site is changed and covered by a test in `tests/test_friction_strict_log.py`:
- platform-scope destination without `[promotion].repo` stays a pending route whose detail names `[promotion].repo`, with no GitHub issue call; `platform_repository()` raises;
- `process_label()` propagates configuration read errors and rejects an empty or non-string value; an absent optional key keeps the documented default `process`;
- `read_events` raises `FrictionLogError` with `path:line` for invalid JSON, a non-object line or a missing `at`, and names the file when it is unreadable;
- `tolerate_local_gap()` is entered only by `review-path` (which reports the gap) and by checkpoints that explicitly accept `friction-log`;
- `_local_source_status` uses the same strict parser over the whole log;
- id-less lines get `legacy-<sha256[:16]>` content ids; positional `legacy-N` references in route state and attributions resolve to that id or fail with a named error.

Correctness: no new fallback is introduced. Beyond the design's file list, the executor also changed:
- `requirement_retrospective.py`: the Requirement checkpoint honours an accepted `friction-log` gap and turns `FrictionLogError` into its own error with the accept-gap hint;
- `integration_contour.py`: post-merge jobs turn `FrictionLogError` into `JobBlocked` instead of letting a `SystemExit` end the worker, keeping the previous blocked outcome for a degraded log;
- `template/dev-platform/platform-manifest.json`: regenerated.

Existing tests that encoded the removed behaviour were updated:
- two checkpoint fixtures without `at` gained a timestamp;
- an old malformed line is now a gap (`partial`);
- unreadable and partial log checkpoints now expect the named file/line error.

Coherence: the design decisions are implemented as written.

Known limits, stated plainly:
- The documented default for an absent optional `process_health.process_label` key is kept, as the Requirement targets read errors only.
- The legacy-schema `setdefault` normalisation (severity, triggers, run, classification, context) is unchanged.
- A malformed log now stops every command that reads events until it is repaired or the gap is explicitly accepted at a checkpoint. `doctor` and `finish` still report a failed `route-pending` retry as a warning, which is existing behaviour owned by a sibling Requirement.

Checks actually run:
- `python3 scripts/check_private_backlog_refs.py` passed before the run.
- Command: `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/strict-friction-routing-and-log/automated-checks.json`. It ran first on the head reconciled with `origin/main` 46a39c3 (compileall, ruff and `run_test_groups.py --all` passed in 1544 s). `main` then advanced with overlapping files (`dev-platform/checks.toml`, platform manifest), so the task was reconciled again with `origin/main` f3a52e7 (clean merge, manifest regenerated unchanged) and the command was rerun with the task freshness gate passed; the evidence file records this second run.
- `compileall` passed.
- `ruff` passed.
- `python3 scripts/run_test_groups.py --all` passed in 1426 s on the final run.
- Before reconcile, two `test_autonomous_integration_contour` tests failed on the stale base. They were dated fixtures already fixed on `main`. They passed after reconcile.
