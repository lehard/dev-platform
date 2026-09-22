# Verification: add-platform-health-review-notifications

## Scope of this receipt

This records what was actually run for the code-complete implementation of
this change, as the last of four stacked sibling tasks
(#165 architecture-health cloud execution -> #166 combined trigger
orchestration -> #167 combined durable report -> #169 this change,
notifications). Live-channel verification (a real Telegram send, a real
webhook send, or any real GitHub Actions dispatch of
`.github/workflows/platform-health-review.yml`) is **deliberately deferred**
to a later, single, coordinated round across all four changes, after a human
supervises that round. This is not a completed OpenSpec verification and
this file does **not** assert `OpenSpec-Verify: PASS`.

## Sibling merge

Ran, from inside this worktree only:

```
git merge agent/add-platform-health-review-report
```

Result: clean fast-forward (`fb912d2..50d8ca3`, "Fast-forward (no commit
created; -m option ignored)"). No conflicts. Confirmed present afterward:

- `.github/workflows/platform-health-review.yml`
- `.github/workflows/architecture-health-review.md` / `.lock.yml`
- `.github/workflows/weekly-process-backlog-review.md` / `.lock.yml`
- `scripts/publish_platform_health_review_report.py`

## What was implemented

1. `scripts/notify_platform_health_review.py` (new): reads
   `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `NOTIFY_WEBHOOK_URL` only from
   its own process environment, sends a short summary + report-Issue-link
   notification to whichever channel(s) have their required secret(s)
   present, silently skips any channel with a missing secret, and delivers
   to each channel independently (one channel failing never blocks the
   other). Error text is deliberately reduced to exception type / safe HTTP
   status only (`_safe_error_detail`), never the raw exception string, so a
   secret embedded in a URL can never reach stdout/stderr even in a
   worst-case client error message.
2. `.github/workflows/platform-health-review.yml`: added a `notify` job
   (`needs: publish-report`, `if: always() && needs.publish-report.result ==
   'success'`) that invokes the script as a plain Actions step, with
   `secrets.TELEGRAM_BOT_TOKEN` / `secrets.TELEGRAM_CHAT_ID` /
   `secrets.NOTIFY_WEBHOOK_URL` passed via `env:`. These three secrets do not
   yet exist in the live repository -- referencing an unset secret is valid
   GitHub Actions YAML and yields an empty string at runtime, which the
   script treats as "not configured."
3. `scripts/publish_platform_health_review_report.py`: extended (not
   redesigned) so the existing `publish-report` job can hand the `notify`
   job what it needs without re-deriving it: added `render_summary()` (a
   short, few-line summary, never the full report body),
   `write_github_output()` (writes `report_issue_number` /
   `report_issue_url` / `report_summary` to `$GITHUB_OUTPUT` when that env
   var is present), and wired both into `publish()`'s result / `main()`. The
   `publish-report` step gained `id: publish` and the job gained an
   `outputs:` block exposing those three values to `notify`.
4. Confirmed no channel secret is read from or written to
   `dev-platform/capabilities.toml` or `.dev-platform.toml` (see Secret scan
   below); enablement is implicit (whichever secrets are present at runtime),
   with no new capability-config layer added, matching the change's
   constraints ("does not build a new operator-config layer for these
   secrets").

## Commands run and results

```
python3 -m compileall -q template/scripts scripts
```
-> exit 0, no output (clean compile).

```
python3 scripts/managed_projects.py validate
```
-> `Managed project registry: OK (3 managed, 0 candidate, 0 excluded)`

```
python3 scripts/run_test_groups.py --all
```
-> `DEV_PLATFORM_TEST_AGGREGATE: {"failed_groups": [], "group_count": 13,
"group_seconds_total": 945.115, "jobs": 4, "jobs_source": "auto-capped",
"mode": "all", "outcome": "success", "slowest_group_seconds": 153.333}`
(1190 discovered tests across 13 groups, all passed; run in the background
per this repo's own no-busy-poll rule, then read out to completion). Note:
`dev-platform/checks.toml`'s `test_groups.fast-a` had to be updated to add
`test_notify_platform_health_review` -- the runner refused an unbalanced
run otherwise ("Declared test groups are not equivalent to the discovered
mandatory suite").

```
python3 template/scripts/openspec_lifecycle.py check
```
-> `OpenSpec lifecycle hygiene: OK`

```
openspec validate add-platform-health-review-notifications --strict --no-interactive
```
-> `Change 'add-platform-health-review-notifications' is valid`

```
python3 scripts/validate_agentic_workflows.py
```
-> `Compiled 3 workflows: 3 succeeded, 0 warnings`; `Agentic workflow
sources and locks match gh-aw v0.85.4.` (the `platform-health-review.yml`
orchestrator, including the new `notify` job, is plain non-agentic Actions
YAML and is not one of the 3 compiled gh-aw workflows; this check confirms
the merged/unchanged agentic workflow sources still compile cleanly.)

```
python3 -m unittest tests.test_agentic_workflows -v
```
-> 12/12 passed, including
`test_platform_health_review_jobs_do_not_depend_on_each_other` and
`test_platform_health_review_publishes_one_combined_report`, both still
green after adding the `notify` job.

New focused unit tests added and run:

- `tests/test_notify_platform_health_review.py` (new): both channels
  configured; only Telegram configured; only webhook configured; a partial
  Telegram secret (token without chat id) treated as not-configured; neither
  configured (clean no-op, exit 0, "No notification channel configured...");
  one channel's send failing does not block the other (both directions);
  and secret-redaction tests -- `_safe_error_detail` never returns raw
  exception text, a `ChannelResult.error` never contains a fake secret even
  when the underlying fake transport's exception message embeds one, and a
  full `main()` run with fake secrets in the environment produces stdout
  that contains none of the configured secret values. All use an injectable
  `FakeSender`; no real network call is made.
- `tests/test_publish_platform_health_review_report.py` (extended): added
  `RenderSummaryTests` (summary is short, excludes findings detail, and is
  present on `publish()`'s result) and `WriteGithubOutputTests` (writes
  parseable `key=value` lines plus the multiline `<<delimiter>>` form for
  `summary`, and appends without clobbering existing file content).

All of the above pass; combined with the full `run_test_groups.py --all`
run above.

Secret scan:

```
grep -rn "TELEGRAM_BOT_TOKEN\|NOTIFY_WEBHOOK_URL" dev-platform/capabilities.toml .dev-platform.toml
```
-> no matches (exit 1). Also checked more broadly with `grep -rl
"TELEGRAM_BOT_TOKEN" . --include="*.py" --include="*.yml" --include="*.yaml"
--include="*.md"`: only appears in `scripts/notify_platform_health_review.py`
(read via `os.environ`), `.github/workflows/platform-health-review.yml`
(referenced via `secrets.*`), and `tests/test_notify_platform_health_review.py`
(fake test fixtures only, clearly named `FAKE_SECRET` /
`FAKE-SUPER-SECRET-TOKEN-123`, never a real credential).

## Routing

```
python3 scripts/dogfood_task.py route-claude --profile standard --rationale "..." --evidence "..."
```
-> refused: `Model routing blocked: model routing requires exactly one
materialized managed OpenSpec change in this task checkout; found 4`. This
is the expected, already-known consequence of the stacked sibling merges
(both prior sibling tasks #166/#167 hit and recorded the same block). Not
forced.

## Deliberately not done in this round

- **Not exercised**: sending a real Telegram message or a real webhook call
  with a live secret. `tasks.md`'s corresponding checkbox is left unchecked
  on purpose; it requires real external calls / live secrets that are out of
  scope for this round.
- **Not dispatched**: no GitHub Actions workflow was run or dispatched in
  the live repository from this change.
- No push, no PR, no `openspec_lifecycle.py archive`, no `dogfood_task.py
  finish`, no `agent_friction.py checkpoint` (per explicit instruction --
  this task is not finished, pending the coordinated live round).

## Conclusion

Code-complete and locally committed on `agent/add-platform-health-review-notifications`.
`OpenSpec-Verify: PASS` is intentionally **not** asserted here. Full
semantic/live verification (including the notification's real-channel
exercise) is deferred to the single, later, human-supervised round covering
#165 -> #166 -> #167 -> #169 together.
