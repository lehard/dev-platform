## Where the failure is caught

Failures happen in places a step-level hook cannot reach: the `plan` job, per-project steps before platform tooling exists, a cancelled run. The only point that sees all of them is a job that depends on both rollout jobs and always runs. `alarm` runs from the workflow's own ref (a plain checkout, like `plan`), not from the release tag, so the alarm code is the reviewed main code even when the requested release is old or invalid.

## Inputs

- `GITHUB_REPOSITORY`, `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT`, `GITHUB_EVENT_NAME`, `GITHUB_TRIGGERING_ACTOR` (all required; a missing one fails the job).
- `needs.plan.outputs.version` when `plan` resolved it; otherwise the release is named the same way `plan` would: the `version` input, or `v<VERSION>` from the workflow-ref checkout. A `plan` failure before resolution therefore still names the requested release.
- `inputs.repository` (empty means all managed projects).

## Reading the run

`gh api --paginate repos/{repo}/actions/runs/{run_id}/attempts/{attempt}/jobs --jq '.jobs[]'` gives one JSON object per job. The `alarm` job excludes itself by name. Classification by `conclusion`:

- `success`: fine;
- `skipped`: fine only when `plan` failed (the matrix never expanded) or the job had no work; otherwise a failure;
- anything else (`failure`, `cancelled`, `timed_out`, `action_required`, `startup_failure`, `null` for a job that never finished): a failure.

For each failed job: its first step with `conclusion == failure` (or "no failed step recorded" stated explicitly) and its failure-level annotations from `repos/{repo}/check-runs/{job_id}/annotations` (the `::error` messages, which carry for example "repository ... not found" or the rollout blocker). When a failed job has no failure annotation, the alarm says so and links the job log; it never invents an error text.

The `plan` job is reported as stage `plan`; per-project jobs are reported by target repository, parsed from the job name `<owner/repo> -> <tag>`.

## Alarm record

One open issue per release tag, title `Managed rollout failed: <tag>`, label `rollout-alert` (bootstrapped with `gh label create --force`, the same idempotent method as the streak tracker). A first failure creates it; a later failing run for the same tag comments on it. Each body/comment is a table of failed stage or target, failed step and error, plus run URL, attempt, event, triggering actor and requested scope. The script also prints `::error title=Managed rollout failed::...` and appends to the step summary.

A fully successful run creates nothing. If an alarm issue for that tag is open, it gets a comment that run N succeeded for its scope; the issue stays open because a single-repository retry does not prove every listed target recovered. Closing it remains an operator decision.

Exit status: 0 when the alarm was delivered or none was needed; non-zero with a message naming the failed GitHub call otherwise. The run is already red when an alarm is raised, so `alarm` does not need to fail to make the run red.

## Streak tracker

The three broad `except Exception` handlers are removed. `TrackerError` and unexpected errors reach `main`, which prints `rollout_failure_streak: <command> failed: <error>` and exits 1. Evidence that does not prove recovery is still a normal outcome of `reconcile` (alert stays open, exit 0); a missing `ROLLOUT_PROJECT_TOKEN` is now a failure because it is a missing required input, not evidence.

In `rollout.yml` the failure step's condition becomes `failure() && steps.prepare.outcome == 'failure'`: the streak counts rollout preparation failures, as the spec states; earlier failures are covered by the release alarm. The step reads `rollout-diagnostic.json` without `|| echo unknown`; a missing or unreadable diagnostic fails the step with that reason. `rollout_diagnostic.py ... || true` in the preparation step is left untouched because the spec requires the preparation step to preserve its original exit code.

## Alternatives rejected

- Alarm from `publish-version.yml` by waiting for the dispatched run: does not cover manual dispatch, which is now the only path.
- Moving streak recording into the `alarm` job: the per-project diagnostic lives in the matrix leg, and matrix job outputs cannot carry per-leg values.
