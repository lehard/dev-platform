# Design

## Relationship to existing rollout observability

`allow-safe-reclaimed-rollout-recopy` produces the stable `Managed rollout: BLOCKED:` / `DEV_PLATFORM_CHECK_COMMAND:` markers. `harden-rollout-diagnostics` (archived) turns those markers into a canonical per-attempt `rollout-diagnostic.json` envelope with `stage`/`category`/`reason`/`exit_code`/`retry_same_inputs`. Both are per-run: they describe *this* attempt and are discarded with the runner once the job ends (only a 30-day artifact remains, and nothing reads across artifacts).

This change adds a third, cross-run layer: a durable streak count per managed project, built from the terminal status (`blocked` vs. resolved) that rollout already computes on every attempt. It does not reclassify failures and does not reopen either prior change's scope.

## Why GitHub Issues as the durable store, not a committed file or `agent_friction.py`

Three storage options were considered:

1. **A committed JSON file in `dev-platform`** (e.g. `rollout-state/<repo>.json`), updated by a bot commit on every attempt. Rejected: it adds a commit to `main` on every rollout run (including successes), is not itself a human notification, and duplicates a tracking mechanism GitHub already provides.
2. **`template/scripts/agent_friction.py`** events. Rejected: friction logs are deliberately machine-local (`.claude/agent-friction.jsonl` inside a project working tree), written by interactive agent sessions and reviewed in batches by a human running that project's own CLI. A GitHub Actions runner's working tree is destroyed at the end of the job, so any friction event recorded there is unreadable by the time anyone would look; friction's own promotion path (`agent_friction.py promote`) is for sanitized *pattern* candidates surfaced by a human after repeated local evidence, not live per-run CI telemetry. Reusing it here would silently produce events nobody would ever see, recreating exactly the "invisible red run" gap this change exists to close.
3. **A GitHub Issue on `lehard/dev-platform`, one per project streak.** Chosen. It is durable across runs without a source commit, it is exactly the kind of thing humans already watch (issue notifications, issue lists, labels), it needs no new credential (default `GITHUB_TOKEN` already has write access to the repository the workflow runs in — this is same-repository, not the cross-repository App-token path `AGENTS.md` reserves for target-project writes), and closing it on resolution gives a naturally self-cleaning worklist instead of an ever-growing log.

## State shape

One open issue per actively-failing project, titled `Managed rollout repeatedly failing: <owner/repo>` and labeled `rollout-failure-streak`. The issue body carries a human-readable summary table plus a machine-parseable state block in an HTML comment so it renders cleanly and stays scriptable:

```
<!-- rollout-failure-streak-state
{"schema_version":1,"repository":"owner/repo","consecutive_failures":3,
 "first_failed_release":"v1.4.13","last_failed_release":"v1.4.20",
 "last_category":"copier_conflict","last_reason":"...","last_updated":"..."}
-->
```

Lookup uses the exact repository slug embedded in that marker (not GitHub's fuzzy issue search) so two similarly named projects can never cross-match.

On a terminal blocked attempt (`scripts/rollout_failure_streak.py record-failure`):

- no open tracking issue for this project -> create one, `consecutive_failures = 1`;
- an open tracking issue exists and its state block parses -> increment `consecutive_failures`, update `last_failed_release`/`last_category`/`last_reason`, append a comment with this attempt's diagnostic detail;
- an open tracking issue exists but its state block is missing or does not parse -> **fail closed toward alerting**: treat the streak as already at the threshold rather than resetting to 1. A record that failed to parse is evidence of a problem, not evidence of a clean history, and this change's whole purpose is to never let ambiguity read as "fine."
- whenever the resulting `consecutive_failures >= 3`, add the `rollout-alert` label (idempotent) and print a `::warning title=Repeated managed rollout failure::` annotation naming the project, the streak length, and the issue URL.

On a successful rollout preparation (`scripts/rollout_failure_streak.py record-success`):

- no open tracking issue -> no-op;
- an open tracking issue exists -> close it with a comment recording how many consecutive failures preceded the resolution and at which release it resolved. It is not deleted, so it remains a searchable historical record.

"Successful rollout preparation" is the `prepare` step exiting `0` (status `updated` or `up_to_date`), the same signal rollout already uses to decide whether to push a branch. It does not depend on downstream PR review or merge, which this workflow has no visibility into and this change does not add.

Threshold is fixed at 3 and exposed as a `--threshold` flag on the script for tests; the workflow does not need to override it.

## Fail-closed / non-interference guarantee

The streak tracker never influences rollout's own result:

- it runs only after `prepare`'s exit code is already fixed for this attempt (as an additional `continue-on-error: true` step, mirroring the existing diagnostic-artifact-upload step's posture);
- every entry point catches all exceptions, prints a `::warning::` line so a tracking-layer failure is still visible in the run log/summary instead of silent, and exits `0`;
- it never retries, pushes, merges, or edits anything outside its own tracking issue;
- an unreadable prior state escalates instead of silently resetting, so a corrupted or tampered tracking issue cannot be used to hide an ongoing streak.

## Compatibility and rollback

Purely additive: no existing marker, envelope field, workflow permission removal, or safety gate changes. Removing this change deletes the two new workflow steps and the script; any open tracking issues remain as an inert historical record and simply stop being updated.

## Validation

Unit tests cover: state-block round-trip parsing, increment-on-repeat-failure, reset-to-zero-on-success (no-op when nothing open), threshold-crossing escalation (label + annotation), and fail-closed handling of an unparseable prior state (escalates, does not reset). Workflow tests assert `issues: write` is present, the new steps are `continue-on-error: true` and scoped to the same `steps.pending.outputs.found != 'true'` guard as the rest of the per-attempt path, and that no new step can influence `steps.prepare.outputs.status`, push, or PR-creation conditions.
