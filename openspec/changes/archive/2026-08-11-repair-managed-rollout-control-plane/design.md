# Design: repair managed rollout control-plane regressions

## Root causes, read from the actual failing run

The `v1.4.21` rollout run failed identically for `cuby`, `Jara_Fin`, and `planner-agent-lab` at the "Detect already-pending rollout PR" step, before "Prepare exact-version Copier update" (the step `allow-safe-reclaimed-rollout-recopy` owns) ever executed. The raw step log shows:

```
gh pr list --repo "$REPOSITORY" --state open --head "$branch" \
  --json number,url,headRefName,baseRefName,author \
  --jq --arg branch "$branch" --arg base "$BASE_BRANCH" --arg bot "${APP_SLUG}[bot]" \
  '[.[] | select(.headRefName == $branch and .baseRefName == $base and .author.login == $bot)][0] // {}'
unknown flag: --arg
```

`gh pr list --jq` takes one jq *expression string*; it does not forward additional `--arg NAME VALUE` pairs to an embedded jq invocation the way running `jq` directly would. `gh`'s own flag parser rejects `--arg` outright. This is a hard failure, not a jq-expression bug -- the expression itself is never reached.

Auditing every `python3 <path>` reference inside the `rollout` job against its actual checkout layout (`platform/` = immutable release checkout, `target/` = downstream project checkout, no plain root checkout in this job) found a second, not-yet-triggered defect: `Supersede older validated rollout PRs` and `Reconcile rollout PRs already adopted by downstream base` both invoke bare `scripts/rollout_supersession.py`, which resolves to nothing at the job's working directory. `rollout_project.py`, `rollout_diagnostic.py`, and `rollout_failure_streak.py` are correctly invoked as `platform/scripts/...` a few steps earlier in the same job -- this is an inconsistency within one file, not a systemic misunderstanding.

The `Record rollout failure streak` step also surfaced `could not add label: 'rollout-failure-streak' not found`: `gh issue create --label rollout-failure-streak` fails outright if that label does not already exist on the tracker repository, and nothing in the platform ever created it.

## Why this stayed green until a real rollout ran

`tests/test_rollout_supersession.py` and the (not-yet-existing) failure-streak tests exercise the *Python* functions directly -- `reconcile()`, `eligible_rollout_prs()`, `next_state_on_failure()` -- with mocked `gh_api`/`subprocess.run` runners. That is correct and valuable coverage of the *logic*, but nothing in the suite ever asserted that the actual shell/CLI text embedded in the workflow YAML is syntactically valid `gh` usage, or that a bare `scripts/...` reference resolves under the job's real multi-checkout layout. `openspec_lifecycle.py check` and `openspec validate --strict` do not parse GitHub Actions shell blocks either. The gap is specifically "does the *orchestration glue* actually work," which unit tests of the Python it calls cannot prove by themselves.

## Fix 1: structured pending-PR detection, reusing the existing trust boundary

`scripts/rollout_supersession.py` already has exactly the primitives needed: `list_open_prs(repository, base_branch)` (structured `gh api --paginate --slurp` JSON, no text scraping) and `eligible_rollout_prs(prs, *, repository, base_branch, expected_bot)` (exact reserved-branch regex + base + bot identity match, never PR title). Add:

```python
def find_exact_pending_rollout_pr(
    repository: str, base_branch: str, expected_bot: str, version: str,
) -> RolloutPR | None:
    eligible = eligible_rollout_prs(
        list_open_prs(repository, base_branch),
        repository=repository, base_branch=base_branch, expected_bot=expected_bot,
    )
    return next((pr for pr in eligible if pr.version == version), None)
```

This is the same trust boundary supersession already relies on, so "pending" cannot be spoofed by an unrelated PR that merely has a similar title or branch prefix.

## CLI reshape: explicit subcommands

`rollout_supersession.py`'s CLI becomes two subcommands under one parser: `reconcile` (existing flags, existing behavior, unchanged) and `find-pending` (`--repository --base-branch --expected-bot --version --registry --output`, writes `{"found": bool, "url": str|null, "number": int|null, "branch": str|null}`). Both workflow files that invoke this script are updated in the same change:

- `.github/workflows/rollout.yml` `rollout` job: `Detect already-pending rollout PR` now runs `python3 platform/scripts/rollout_supersession.py find-pending ...` and reads the three JSON fields into `$GITHUB_OUTPUT` -- the only remaining shell is trivial JSON-field extraction, not GitHub-state filtering logic. The two existing supersession call sites become `python3 platform/scripts/rollout_supersession.py reconcile ...` (path fixed to `platform/`, matching every other platform-owned helper call in this job).
- `.github/workflows/reconcile-stale-rollouts.yml` `reconcile` job: single plain root checkout, so its call site becomes `python3 scripts/rollout_supersession.py reconcile ...` (bare path stays correct for that job's layout; only the subcommand keyword is added).

## Fix 2: path-correctness is proven by a regression test, not just fixed by hand

A static test reads `.github/workflows/rollout.yml`, isolates the `rollout:` job body (not `plan:`, which has its own plain root checkout and legitimately uses bare `scripts/managed_projects.py`), and asserts every `scripts/<known-root-script>.py` reference within it is prefixed `platform/`. This directly encodes "the actual Actions filesystem layout" as an executable check instead of a one-time manual audit, so a future call site added inside that job without the prefix fails CI immediately.

## Fix 3: idempotent, least-privilege label bootstrap

```python
def ensure_label(repo: str, name: str, color: str, description: str) -> None:
    run_gh(["label", "create", name, "--repo", repo, "--color", color, "--description", description, "--force"])
```

`gh label create --force` creates the label if absent or updates color/description if present -- idempotent by construction, no separate list-then-create race. Called once for `TRACKING_LABEL` and once for `ALERT_LABEL` at the start of `cmd_record_failure` (before `find_tracking_issue`/`issue create --label` can reference either), inside the same top-level `try/except Exception` that already makes this entire command best-effort. A bootstrap failure is therefore indistinguishable, from the caller's perspective, from any other tracking-layer failure: a warning is printed, `0` is returned, and the rollout attempt's own result is untouched -- matching the existing "tracking layer itself fails" contract already in `platform-rollout` spec.

No repository permission beyond the `issues: write` the rollout job already declares is required; label management is covered by that same scope.

## Test strategy

- Pure-function tests for `find_exact_pending_rollout_pr` (found; absent; wrong bot; wrong base; wrong branch pattern -- reusing the `pr()` fixture builder already in `tests/test_rollout_supersession.py`).
- A workflow-text regression test: no `--jq` immediately followed by `--arg` in any `gh` invocation anywhere in `.github/workflows/*.yml`; every `scripts/<name>.py` reference inside `rollout.yml`'s `rollout:` job body is `platform/`-prefixed.
- `rollout_failure_streak.py` tests: `ensure_label` is called before the first label reference; calling it twice does not raise; a simulated "label create fails" still lets `cmd_record_failure`/`cmd_record_success` return `0` without raising.
- No new GitHub Actions runner integration test is added -- consistent with "no large workflow-engine rewrite," the static text-layout assertions plus the existing mocked-`gh` unit-test style are the proportionate level of coverage here.

## Rollout of this change itself

This is central platform tooling with no template/rendering surface change (no `template/` file is touched), so no Copier upgrade-smoke, factory-render, or downstream-consumer-facing compatibility risk is introduced. Validation is the standard local contract plus, after merge and the next normal release, the real managed-rollout evidence described in the proposal's success criteria.
