# Verification: add-platform-health-review-notifications

OpenSpec-Verify: PASS

Verification-Method: local deterministic validation (unit tests for the notification script and the extended report script against fakes/mocks, full platform test-group suite, OpenSpec structural + hygiene validation, gh-aw compile drift check) both before and after reconciling with the merged `main`; live gh-aw cloud dispatch of the notify job (and a real Telegram/webhook send once secrets are provisioned) is an explicit documented post-merge follow-up, not performed pre-archive

Automated-Checks-Evidence: automated-checks.json

## Scope of this receipt

This is the last of four stacked sibling tasks (#165 architecture-health
cloud execution -> #166 combined trigger orchestration -> #167 combined
durable report -> #169 this change, notifications). All three prerequisite
siblings, plus two follow-up bug-fix quick tasks they surfaced via their own
post-merge live-dispatch verification (insufficient job `permissions:`;
`gh api` defaulting to POST for a read-only list call), have since merged to
`main`. Per the user's decision applied consistently across the whole chain,
the one `tasks.md` live-verification item is reworded as an explicit
**post-merge** follow-up rather than a pre-archive gate (see `design.md`'s
"Verification note"). Every other item, and everything verifiable
pre-merge, was actually run and passed, so this change is archive-ready on
that basis.

## Sibling merge, then reconcile with merged main

`git merge agent/add-platform-health-review-report` from inside this
worktree originally fast-forwarded cleanly (`fb912d2..50d8ca3`). After #165,
#166, #167, and the two follow-up fixes all actually merged to `main`,
`python3 scripts/dogfood_task.py reconcile` was run to replace that
provisional local merge with real history; it stopped at merge conflicts in
5 files: `.github/workflows/platform-health-review.yml`,
`dev-platform/checks.toml`, `scripts/publish_platform_health_review_report.py`,
`tests/test_agentic_workflows.py`, and
`tests/test_publish_platform_health_review_report.py` (expected: this
branch's own commit already added the `notify` job / `render_summary()` /
`write_github_output()` on top of pre-fix content, while `main` had since
gained the job-permissions fix, the `--method GET` fix, and their respective
regression tests). Resolved by hand-combining both sides in every case
(kept this task's `notify` job, `render_summary`/`write_github_output`
additions, and its own new tests, while also keeping `main`'s permissions
fix, `--method GET` fix, and their regression tests) -- no content was
dropped from either side. Also removed three now-stale duplicate pre-archive
OpenSpec change directories (`add-architecture-health-cloud-review`,
`add-platform-health-review-orchestration`, `add-platform-health-review-report`)
that were leftover artifacts of the original local stacked-branch merges --
confirmed via `git show origin/main:<path>` that `main` never contained them
at their active (non-archived) location. Confirmed afterward:
`dogfood_task.py status` reports `task freshness: ahead relative to
origin/main` (no longer diverged), and the full validation suite (below) was
re-run against this reconciled state and passed.

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
-> 13/13 passed post-reconcile, including
`test_platform_health_review_jobs_do_not_depend_on_each_other` and
`test_platform_health_review_publishes_one_combined_report` (still green
after adding the `notify` job) and
`test_caller_job_permissions_cover_every_nested_job_in_the_called_workflow`
(picked up from `main` via the reconcile).

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
  `summary`, and appends without clobbering existing file content). 31/31
  tests pass post-reconcile, including `GhClientCommandTests` (picked up
  from `main` via the reconcile, covering the `--method GET` fix).

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

Recorded cleanly (`R2`, routine profile) after the reconcile removed the
three stale duplicate OpenSpec directories, leaving exactly one materialized
change (`add-platform-health-review-notifications`) in this worktree.
`report-claude-execution` recorded a clean containment postcheck.

## Post-merge follow-up (not a pre-archive gap)

- **Live dispatch of the `notify` job in `lehard/dev-platform`.** Documented
  in `tasks.md` and `design.md` as an explicit post-merge follow-up: the job
  (and every reusable workflow the orchestrator calls) must exist on `main`
  before `workflow_dispatch` recognizes it at all. To be performed once this
  change merges, alongside confirming a clean no-op (no channel secrets are
  configured in this repository yet).
- **Real Telegram/webhook message delivery.** Requires the user to
  provision `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` and/or
  `NOTIFY_WEBHOOK_URL` as real GitHub Actions repository secrets -- entering
  credentials is outside what an automated agent does. Deferred until the
  user chooses to configure and test a real channel.

## Conclusion

This is the fourth and final change in the #165 -> #166 -> #167 -> #169
stack. All prerequisite siblings and their follow-up fixes are merged to
`main`; this change is reconciled against that real history, fully
validated pre-merge, and archive-ready. The two remaining items -- live
dispatch of the `notify` job to confirm its clean no-op, and a real
Telegram/webhook send once the user provisions secrets -- are explicit,
documented post-merge follow-ups, not pre-archive gaps.
