# Managed project rollout

Managed rollout removes the human step of remembering which Copier-managed projects need a new Dev Platform release.

The operating model is:

`platform release -> managed registry -> exact Copier update -> Harness validation -> rollout PR -> downstream CI/review -> merge`

Ordinary rollout never performs first-time adoption and never auto-merges by default. First-time onboarding is handled by the separate **Adopt Project** workflow.

## Registry

Managed rollout is an optional operator capability. Its project inventory and
cross-project write allowlist live in an external operator-owned registry; the
public core does not ship one. `--registry` is an explicit command-line
override. Otherwise commands read `rollout.registry_path` from the external
operator TOML selected only by an enabled project `[operator]` table. A global
environment variable alone cannot enable the operator layer.

States:

- `managed` — adopted and eligible for rollout PRs opened by a dispatched **Roll Out Platform** run;
- `candidate` — active software/project repository awaiting Dev Platform adoption;
- `excluded` — known repository intentionally outside adoption/rollout, with a required explanatory note.

Only `managed` enters the ordinary rollout matrix. `candidate` and `excluded` are non-mutating during rollout. Explicit human-triggered **Adopt Project** onboarding is allowed to promote an adopted candidate/excluded repository because that workflow itself is the intentional reclassification action.

Validate locally with:

```bash
python3 scripts/managed_projects.py --registry /secure/operator/managed-projects.json validate
python3 scripts/operator_doctor.py
```

Explicit promotion is also available for recovery:

```bash
python3 scripts/managed_projects.py promote --repository owner/name --default-branch main
```

### CI resolution: a private operator repository

A GitHub Actions runner has no access to an operator's local filesystem, so
**Adopt Project**, **Roll Out Platform** and **Reconcile Stale Managed
Rollouts** each resolve the registry from a dedicated, private
operator-owned GitHub repository instead — never from `lehard/dev-platform`
itself. The public core must never hold `managed-projects.json`: committing
it there would mean every future promotion permanently records the fleet's
real repository names in `lehard/dev-platform`'s public history.

Set the non-secret repository variable `DEV_PLATFORM_OPERATOR_REPOSITORY`
(for example `your-org/dev-platform-operator`) on the public repo to name that
private repository generically — it is never hardcoded in workflow or Python
source. Each workflow then:

1. fails closed if `DEV_PLATFORM_OPERATOR_REPOSITORY` is unset, with the same
   explicit message pattern as the GitHub App configuration check;
2. mints a short-lived GitHub App token scoped only to that repository
   (`contents: read` for rollout/reconcile's read-only matrix planning,
   `contents: write` for Adopt Project's promotion write);
3. checks it out to a local `operator/` path in the job;
4. passes `--registry operator/managed-projects.json` to every
   `scripts/managed_projects.py` invocation, and to every
   `scripts/rollout_supersession.py reconcile` invocation (that subcommand
   independently requires `--registry` to confirm a repository is managed
   before closing any of its PRs). A job that calls `reconcile` on a runner
   separate from its own `plan` job repeats this checkout itself, since job
   outputs do not carry a prior job's checked-out working tree.

The private operator repository needs no special structure: it is not a fork
of Dev Platform and not a second platform, only `managed-projects.json` (this
same schema) plus, optionally, an `operator.toml` mirroring the local one
described above. A local checkout of `lehard/dev-platform` resolves the same
registry by cloning that private repository once and pointing
`rollout.registry_path` in the local external operator TOML at the clone's
`managed-projects.json` — no code change is needed for the local path, since
`--registry`/`registry_path` already accept an arbitrary filesystem path.

## Template ownership boundary

Copier creates the initial repository contract, but not every generated file remains platform-owned forever.

The following files are **project-owned after initial creation** and are preserved on later Copier updates:

- `.gitignore` — repository-specific generated/runtime/editor ignores. The template seeds the baseline only at initial creation; every existing `.gitignore` is preserved byte-for-byte on later Copier updates, regardless of harness mode;
- `AGENTS.md` — project/root agent contract and any project-specific workflow additions;
- `README.md` — product/repository documentation;
- `dev-platform/checks.toml` — project-specific check selection and acceptance commands;
- `openspec/config.yaml` — project/domain context and OpenSpec guidance;
- `docs/engineering/project-rules.md` — project-specific engineering invariants.
- `docs/context/` — reviewed project/domain context.

Shared executable lifecycle scripts, self-contained CI and shared workflow documentation remain platform-managed. For mature `harness_mode=project` repositories, project-specific Git/task harness collision points listed in `copier.yml` are also preserved during guarded recopy. If a project needs an extra file to be required by platform doctor, declare it in `.dev-platform.toml` as `project_required_files = ["..."]` instead of editing `scripts/platform_doctor.py`.

Generated agent integrations do not require platform edits to a mature project's `.gitignore`: `python3 scripts/dev.py ready` records those machine-local patterns in the clone's `.git/info/exclude`.

After Copier renders or updates a stable release, `scripts/platform_bootstrap.py` synchronizes `.dev-platform.toml` `platform_version` from `.copier-answers.yml` `_commit`. Managed rollout and platform doctor both reject a stable-tag state where those two version records disagree.

## Downstream CI runner selection

Platform-rendered GitHub Actions jobs (`platform-ci` in `dev-platform.yml` and `provision` in `process-health-labels.yml`) take their `runs-on` from two recorded Copier answers instead of a hand edit:

- `ci_runner`: `github-hosted` (default, renders `runs-on: ubuntu-latest`) or `self-hosted`. Asked only when `scm_provider` is `github`; a GitLab project is not asked and records neither answer.
- `ci_runner_labels`: asked only for `self-hosted`; comma-separated runner labels. One label renders `runs-on: <label>` when YAML reads it as a string (it starts with a letter and is not a word such as `yes`, `on` or `null`) and quoted otherwise (`runs-on: "123"`); several render a JSON-style flow list such as `runs-on: ["a", "b"]`. Each label must match `[A-Za-z0-9._-]+`, with no empty entries or duplicates.

For `self-hosted`, `platform-ci` also runs `python3 scripts/shared_workspace.py fix` before `platform_doctor`. The label-provisioning job calls the GitHub REST API with `curl` for both runner kinds, so it needs no `gh` CLI on the runner. Copier records the answers in `.copier-answers.yml` and preserves them on update. `platform_doctor` fails explicitly when `ci_runner` is missing, the labels are malformed, or the committed `platform-ci` runner or repair step, or the `provision` runner in `process-health-labels.yml` (which must exist), disagrees with the answers. The committed runner must keep its exact rendered form, and so must the repair step (no changed command or added condition) before `platform_doctor`.

A project that previously hand-edited `runs-on` in these platform-owned workflows needs no manual preparation. When a rollout targets the first release that asks `ci_runner` for a GitHub project whose `.copier-answers.yml` has no `ci_runner`, the rollout first reads the committed `runs-on` of `platform-ci` and `provision`, for both `harness_mode=platform` and `harness_mode=project`, on the rollout branch and before `copier update`:

- All present runners are `ubuntu-latest`: the ordinary update runs and records `ci_runner: github-hosted`; no new step.
- The same simple labels in every present job (a plain label, a quoted label or a flow list such as `[self-hosted, linux]`; each label valid under the rule above) and each file otherwise equal to the render of the project's current release: the rollout records `ci_runner: self-hosted` and `ci_runner_labels`, restores only the `runs-on` value to the baseline, and commits both as one `chore:` commit on the rollout branch. Copier then applies the new render (the runner from the answers plus the shared-workspace repair step) with no `.rej` and no guarded recopy, and `platform_doctor` agrees with the answers.
- Anything else that is not `ubuntu-latest` (an expression such as `${{ vars.RUNNER }}`, a list in block form, a `group`/`labels` mapping, jobs that disagree, an invalid or duplicate label, or other edits in the same workflow file): the rollout stops with `Managed rollout: BLOCKED: <repository>: <file>: <what was found> ... Next action: ...` before it updates anything. It never records `github-hosted` for such a project, and the project's default branch is not changed because the work happens on the ephemeral rollout branch.

After a stop, make the named workflow equal to the platform render except for a simple `runs-on` (move other edits out of the platform-owned file), or record `ci_runner: self-hosted` and `ci_runner_labels: <labels>` in `.copier-answers.yml` on the default branch and resolve the file by hand, then rerun the rollout. A project whose `.copier-answers.yml` records no `scm_provider` also stops (record `scm_provider: github` or `gitlab` and rerun) once the target release asks `ci_runner`. The preflight does not run for GitLab projects, which are not asked the runner questions, nor for a target release that does not ask `ci_runner`. `ci_runner_labels` is validated at the Copier question by the same rule as `platform_doctor` (no empty entry, no duplicate, each label within `[A-Za-z0-9._-]`; whitespace around an entry is ignored, whitespace inside is rejected).

## One-time GitHub App setup

The repository `GITHUB_TOKEN` is intentionally scoped to `dev-platform`, so cross-repository onboarding and rollout use a dedicated GitHub App.

Create a private GitHub App owned by the `lehard` account, for example **Dev Platform Bot**.

Recommended setup:

1. GitHub account **Settings -> Developer settings -> GitHub Apps -> New GitHub App**.
2. Use a descriptive name and the `dev-platform` repository URL as the homepage URL.
3. Webhooks are not required for this workflow; disable webhook delivery unless another use is deliberately added later.
4. Repository permissions:
   - **Contents: Read and write**
   - **Pull requests: Read and write**
   - **Workflows: Read and write** — required because Dev Platform can update downstream `.github/workflows/*` files
   - Metadata remains read-only as required by GitHub.
5. Do not grant organization/account permissions that rollout does not use.
6. Install the App on **`dev-platform` itself**, the **private operator repository** (see [CI resolution](#ci-resolution-a-private-operator-repository) above), plus repositories intentionally participating in onboarding/rollout. When using **Selected repositories**, adding the target repo is the one normal manual security gate before onboarding.
7. Generate a private key for the App.
8. In `lehard/dev-platform` repository settings add:
   - Actions variable `DEV_PLATFORM_APP_CLIENT_ID` = the App **Client ID**;
   - Actions secret `DEV_PLATFORM_APP_PRIVATE_KEY` = the full generated private key including BEGIN/END lines;
   - Actions variable `DEV_PLATFORM_OPERATOR_REPOSITORY` = the private operator repository, `owner/name`.

Never commit the private key or a long-lived installation token.

The publication coordinator proves this configuration before it observes any candidate: `python3 scripts/publication_queue.py preflight --mode ci|local --phase inputs|runtime|all` (both flags required). The `publication-queue` workflow runs the `inputs` phase before minting the App token, passing only boolean presence flags for `DEV_PLATFORM_APP_CLIENT_ID` and `DEV_PLATFORM_APP_PRIVATE_KEY` so the key never reaches the preflight process, and the `runtime` phase after it (token, App slug, trust configuration, installation scope and write permission). A failure exits 2 naming the input, for example an unset variable, an empty App slug or a slug that contradicts `[publication] coordinator_app`; it prints no credential value. `worker --mode ci|local` runs the full preflight itself.

Each cross-repository job creates separately down-scoped short-lived tokens: read-only platform source access, target-repository write access, and read/write access to the private operator repository's registry as each workflow needs it. No PAT is required.

## Adding a new project

Normal path:

1. If the App uses **Selected repositories**, add the target repository to the Dev Platform Bot installation.
2. In `lehard/dev-platform`, run **GitHub Actions -> Adopt Project** and enter `owner/name`.

That is the human-facing process. The workflow auto-detects the repository:

- a `fresh` repo is rendered, OpenSpec-initialized, validated, merged and promoted to `managed` automatically;
- an `existing` repo gets a reviewed adoption PR and is not auto-merged; merge it after review, then rerun **Adopt Project** once to perform the mechanical `managed` promotion;
- an already adopted repo is promoted without recopying.

The detector and exact behavior are documented in `docs/adoption.md`.

## Bridging a pre-cutover legacy baseline

`copier update` resolves a managed project's template source (`_src_path` in
its `.copier-answers.yml`) itself, independent of the workflow's own
`platform/` checkout, and clones/caches it locally to compute the 3-way diff
against the project's recorded baseline tag (`_commit`). A fresh-history
canonical repository (see `docs/public-cutover.md`) never contains a
pre-cutover tag, so a project still on one fails rollout with `invalid
reference: <tag>` until that tag is bridged in.

Set the optional, non-secret repository variable
`DEV_PLATFORM_LEGACY_REPOSITORY` (for example `your-org/dev-platform-legacy`,
never hardcoded) to the repository holding the preserved pre-cutover history.
When configured, `rollout_project.py --legacy-repository owner/name`:

1. resolves Copier's own local mirror cache for the project's template
   source (the same cache Copier itself uses, keyed by that source URL);
2. narrows that cache's `origin` fetch refspec to exactly what the current
   rollout still needs from the real canonical remote (branches plus the
   exact version being rolled out), so Copier's own periodic `git remote
   update --prune` refresh of that cache cannot delete a tag it doesn't
   recognize as origin's;
3. fetches only the project's recorded baseline tag from the legacy
   repository into that same cache.

The combined objects live only in the ephemeral CI runner's local cache; no
history is rewritten, no old tag is ever pushed to or published from the
canonical repository, and a project already on a post-cutover baseline never
triggers a legacy fetch at all. The same optional flag applies to the
baseline-equivalence comparison guarded recopy falls back to when a Copier
update leaves reject files on genuinely unchanged platform paths.

## Release rollout

Rollout is manual on this installation: since 2026-10-28 the variable described below is not `true`, so a release opens no rollout PR. A project is updated on request by dispatching **Roll Out Platform** with `repository=owner/name` (one managed project) or without it (every managed project); see [Manual retry](#manual-retry) for the inputs. The steps below are the same for a dispatched run.

`publish-version.yml` publishes the immutable release and then, if the operator has set the repository **variable** (not a secret) `DEV_PLATFORM_MANAGED_ROLLOUT_ENABLED` to `true`, dispatches `.github/workflows/rollout.yml` with that exact tag. Managed rollout is an optional operator capability: without the variable `scripts/rollout_dispatch_gate.py` reports `dispatch=false` and the release is published without dispatching rollout.

Before any cross-repository token is created, rollout confirms the requested tag is an actually published **immutable** GitHub Release. A manually entered but unpublished version is rejected.

For every `managed` repository, rollout:

1. obtains a read-only source token for private `dev-platform` access and a separate write-capable token scoped to the target repository;
2. checks for an already-open PR for `dev-platform/rollout-vX.Y.Z`;
3. checks out the current configured default branch;
4. validates Copier ownership/source/version metadata and current version coherence;
5. runs Copier `9.19.1` against the exact `vX.Y.Z` tag with `--conflict rej`;
6. requires post-update version coherence and blocks on `.rej`, Git conflict markers, downgrade attempts, unexpected template source or validation failure;
7. runs only Dev Platform Harness validation (`.rej`/diff hygiene and `scripts/platform_doctor.py`); product/application checks are owned by the downstream rollout PR's normal CI;
8. commits and pushes a deterministic rollout branch without force;
9. opens a normal PR;
10. stops. Merge remains governed by downstream CI/review.

After a validated exact-version rollout PR exists, the workflow reconciles older
bot-owned rollout PRs. A PR is eligible only when its head is exactly
`dev-platform/rollout-vX.Y.Z`, its target is stable SemVer, its base matches the
managed registry, and its author is the configured rollout GitHub App. Titles
never establish ownership. Older eligible PRs are closed only after that newer
PR exists; a rollout preparation failure therefore preserves the prior pending
PR. Branch deletion happens only after GitHub confirms close and is warning-only.

For accumulated debt, run **Reconcile Stale Managed Rollouts** first with
`mode=dry-run`. Its artifacts record every proposed closure for the three
currently managed repositories. Review that exact list, then run
`mode=apply` with `confirm_apply=SUPERSEDE_STALE_ROLLOUTS`. The workflow creates
the same down-scoped GitHub App token per managed target and never creates a
token or mutation for `candidate` or `excluded` entries. When the committed
base is behind, maintenance retains the newest eligible bot-owned rollout PR as
the validated replacement and closes only its older eligible predecessors.

Matrix rollout uses `fail-fast: false`: one blocked project does not prevent clean managed projects from receiving PRs.

## Downstream adoption at task start

A clean rollout PR deliberately stops at review; it does not auto-merge. Left
alone, that PR can sit open indefinitely and a later coding session can start
on the older platform version without anyone noticing.

`template/scripts/rollout_preflight.py` closes that gap on the consumer side.
Every platform-owned `start_task.py` invocation (including through
`start_managed_task.py`) reconciles a pending rollout before creating a new
task branch/worktree:

1. after the ordinary `project_sync.py` fetch, it looks for open PRs whose
   head matches the reserved `dev-platform/rollout-vX.Y.Z` branch contract
   against the configured base branch;
2. ownership is confirmed the same way central rollout automation confirms
   it -- exact repository, base branch, and the automation identity recorded
   in `.dev-platform.toml`'s `[tools.rollout] bot_login` -- never by PR title
   or body;
3. a rollout PR whose required checks are green is merged through ordinary
   non-bypass GitHub policy (`gh pr merge --match-head-commit`, the same
   exact-head guard `project_publish.py` uses for task PRs), then local `main`
   is fast-forwarded before the task branch/worktree is created;
4. pending/failed checks, a conflict, a changed head, or an unconfirmed
   automation identity blocks new work with an explicit, resumable state
   instead of silently starting on the older platform layer.

`tools.rollout.bot_login` is rendered into every project's `.dev-platform.toml`
by the Copier template (it is the same platform-wide GitHub App login used by
central rollout automation, not a secret). An existing project only gains this
field once it adopts the rollout carrying it.

`harness_mode=project` repositories keep their own task/worktree entrypoint;
`agent_doctor.py` still reports pending-rollout state there (read-only) so the
prerequisite is visible without the platform replacing that entrypoint.

## Manual retry

This is also the ordinary way to roll out a release on this installation.

GitHub Actions -> **Roll Out Platform** -> **Run workflow**.

Inputs:

- `version` — exact immutable published tag such as `v1.4.2`; empty uses current `VERSION`;
- `repository` — optional exact `owner/name` to retry only one managed project.

A `candidate` or `excluded` repository is rejected by ordinary rollout even when manually specified; use **Adopt Project** for first-time onboarding/reclassification.

## Failed-run alarm

Every **Roll Out Platform** run ends with an `alarm` job (`needs: [plan, rollout]`, `if: always()`). It covers a run dispatched by the release workflow and a manual dispatch, for all managed projects or one `repository`. It runs `scripts/rollout_alarm.py` from the workflow's own ref with the default `GITHUB_TOKEN` (`actions: read`, `checks: read`, `issues: write`).

The script reads the current run attempt's jobs. A failed, cancelled, timed-out or unfinished `plan` job or per-project job opens one issue per release, `Managed rollout failed: <tag>`, labeled `rollout-alert`, or comments on the open one. The issue lists each failed stage (`plan`) or target repository with its failed step and the error text from the job's failure annotations (for example `repository '...' not found`), plus the run link, attempt, event, triggering actor and requested scope. A failed job without a failure annotation is listed as such, with its log link. Per-project jobs skipped because `plan` failed are not listed separately.

A fully successful run raises no alarm. If an alarm for that release is open, the run adds a success note for its scope and leaves the issue open: a one-repository retry does not prove that every listed target was delivered. Close the issue once every listed target has its rollout PR or is up to date.

If the alarm cannot be delivered (the run's jobs cannot be read, or the label, issue or comment cannot be written), the `alarm` job fails with an `::error::` naming what failed. It never retries, repairs, pushes or merges anything.

## Repeated-failure alerting

A single blocked rollout attempt is surfaced per-run: an `::error::` annotation, a step-summary blocker, and a `rollout-diagnostic.json` artifact (see `rollout-diagnostic-<project>-<version>`). None of that persists across runs, so a project that keeps failing the same way on every release looked, from the platform's point of view, identical to a project that failed once — that gap let `example-org/example-service` fail 8 consecutive releases before anyone noticed.

`scripts/rollout_failure_streak.py` closes that gap by keeping a durable, cross-run streak count per managed project:

- on every failed rollout preparation, it opens or updates a `rollout-failure-streak`-labeled issue on `lehard/dev-platform` (one per actively-failing project), incrementing `consecutive_failures` and recording the latest diagnostic category/reason;
- once `consecutive_failures` reaches **3**, it adds a `rollout-alert` label and emits a distinct `::warning::` annotation naming the project, the streak length, and the tracking issue;
- the next time that project's rollout preparation succeeds, the tracking issue is closed with a resolution note (it is not deleted, so it remains a searchable history);
- **Reconcile Stale Managed Rollouts** also observes each managed project's default branch on its daily schedule or during confirmed `apply` mode and closes an open alert when its coherent Copier and `.dev-platform.toml` version records prove recovery at or beyond the issue's last failed release. The scheduled run only plans stale-PR supersession; it never applies it. Unreadable, inconsistent, or stale evidence leaves the alert open and emits a bounded diagnostic.
- an unreadable or missing prior state escalates rather than silently resetting to zero — ambiguity is never treated as "clean."

This runs with the workflow's own default `GITHUB_TOKEN` (`issues: write`), not the cross-repository App token, because it only writes to `lehard/dev-platform` itself. Failures before preparation (for example a missing App installation for one target) are not counted in the streak; the failed-run alarm reports them. A failure inside the tracker fails its step with an `::error::` naming what failed: a missing `rollout-diagnostic.json` after failed preparation, a GitHub error, or a missing `ROLLOUT_PROJECT_TOKEN` in reconciliation. It is never downgraded to a warning, and the tracker never pushes, retries, or merges anything. The success record runs after the branch push, PR creation and supersession steps, so a tracker failure fails the job only after the rollout PR exists. Reconciliation evidence that does not prove recovery is not a failure: the alert stays open.

## Failure handling

The system is intentionally fail-closed.

If an onboarding or rollout job is blocked:

- do not edit `.copier-answers.yml` by hand;
- do not force-push deterministic automation branches;
- inspect the failed job and project ownership conflict;
- resolve project/template ownership in a normal project branch or adoption/update PR;
- rerun the same workflow.

If an open rollout PR already exists for the same version, rollout reports it as already pending and does not rewrite the branch. If the target project is already on the requested version, rollout reports a no-op only when platform version records are coherent.
