# Managed project rollout

Managed rollout removes the human step of remembering which Copier-managed projects need a new Dev Platform release.

The operating model is:

`platform release -> managed registry -> exact Copier update -> project checks -> rollout PR -> downstream CI/review -> merge`

Ordinary rollout never performs first-time adoption and never auto-merges by default. First-time onboarding is handled by the separate **Adopt Project** workflow.

## Registry

`managed-projects.json` is the central project inventory and cross-project write allowlist.

States:

- `managed` — adopted and eligible for automatic rollout PRs;
- `candidate` — active software/project repository awaiting Dev Platform adoption;
- `excluded` — known repository intentionally outside adoption/rollout, with a required explanatory note.

Only `managed` enters the ordinary rollout matrix. `candidate` and `excluded` are non-mutating during rollout. Explicit human-triggered **Adopt Project** onboarding is allowed to promote an adopted candidate/excluded repository because that workflow itself is the intentional reclassification action.

Validate locally with:

```bash
python3 scripts/managed_projects.py validate
python3 scripts/managed_projects.py status
```

Explicit promotion is also available for recovery:

```bash
python3 scripts/managed_projects.py promote --repository owner/name --default-branch main
```

## Template ownership boundary

Copier creates the initial repository contract, but not every generated file remains platform-owned forever.

The following files are **project-owned after initial creation** and are preserved on later Copier updates:

- `.gitignore` — repository-specific generated/runtime/editor ignores; mature projects keep their existing rules;
- `AGENTS.md` — project/root agent contract and any project-specific workflow additions;
- `README.md` — product/repository documentation;
- `dev-platform/checks.toml` — project-specific check selection and acceptance commands;
- `openspec/config.yaml` — project/domain context and OpenSpec guidance;
- `docs/engineering/project-rules.md` — project-specific engineering invariants.

Shared executable lifecycle scripts, self-contained CI and shared workflow documentation remain platform-managed. For mature `harness_mode=project` repositories, project-specific Git/task harness collision points listed in `copier.yml` are also preserved during guarded recopy. If a project needs an extra file to be required by platform doctor, declare it in `.dev-platform.toml` as `project_required_files = ["..."]` instead of editing `scripts/platform_doctor.py`.

Generated agent integrations do not require platform edits to a mature project's `.gitignore`: `python3 scripts/dev.py ready` records those machine-local patterns in the clone's `.git/info/exclude`.

After Copier renders or updates a stable release, `scripts/platform_bootstrap.py` synchronizes `.dev-platform.toml` `platform_version` from `.copier-answers.yml` `_commit`. Managed rollout and platform doctor both reject a stable-tag state where those two version records disagree.

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
6. Install the App on **`dev-platform` itself** plus repositories intentionally participating in onboarding/rollout. When using **Selected repositories**, adding the target repo is the one normal manual security gate before onboarding.
7. Generate a private key for the App.
8. In `lehard/dev-platform` repository settings add:
   - Actions variable `DEV_PLATFORM_APP_CLIENT_ID` = the App **Client ID**;
   - Actions secret `DEV_PLATFORM_APP_PRIVATE_KEY` = the full generated private key including BEGIN/END lines.

Never commit the private key or a long-lived installation token.

Each cross-repository job creates separately down-scoped short-lived tokens: read-only platform source access, target-repository write access, and when onboarding needs registry promotion, a `dev-platform` Contents-write token. No PAT is required.

## Adding a new project

Normal path:

1. If the App uses **Selected repositories**, add the target repository to the Dev Platform Bot installation.
2. In `lehard/dev-platform`, run **GitHub Actions -> Adopt Project** and enter `owner/name`.

That is the human-facing process. The workflow auto-detects the repository:

- a `fresh` repo is rendered, OpenSpec-initialized, validated, merged and promoted to `managed` automatically;
- an `existing` repo gets a reviewed adoption PR and is not auto-merged; merge it after review, then rerun **Adopt Project** once to perform the mechanical `managed` promotion;
- an already adopted repo is promoted without recopying.

The detector and exact behavior are documented in `docs/adoption.md`.

## Automatic release rollout

`publish-version.yml` publishes the immutable release and then dispatches `.github/workflows/rollout.yml` with that exact tag.

Before any cross-repository token is created, rollout confirms the requested tag is an actually published **immutable** GitHub Release. A manually entered but unpublished version is rejected.

For every `managed` repository, rollout:

1. obtains a read-only source token for private `dev-platform` access and a separate write-capable token scoped to the target repository;
2. checks for an already-open PR for `dev-platform/rollout-vX.Y.Z`;
3. checks out the current configured default branch;
4. validates Copier ownership/source/version metadata and current version coherence;
5. runs Copier `9.17.0` against the exact `vX.Y.Z` tag with `--conflict rej`;
6. requires post-update version coherence and blocks on `.rej`, Git conflict markers, downgrade attempts, unexpected template source or validation failure;
7. runs `scripts/platform_doctor.py` and selected project checks;
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
token or mutation for `candidate` or `excluded` entries.

Matrix rollout uses `fail-fast: false`: one blocked project does not prevent clean managed projects from receiving PRs.

## Manual retry

GitHub Actions -> **Roll Out Platform** -> **Run workflow**.

Inputs:

- `version` — exact immutable published tag such as `v1.4.2`; empty uses current `VERSION`;
- `repository` — optional exact `owner/name` to retry only one managed project.

A `candidate` or `excluded` repository is rejected by ordinary rollout even when manually specified; use **Adopt Project** for first-time onboarding/reclassification.

## Repeated-failure alerting

A single blocked rollout attempt is surfaced per-run: an `::error::` annotation, a step-summary blocker, and a `rollout-diagnostic.json` artifact (see `rollout-diagnostic-<project>-<version>`). None of that persists across runs, so a project that keeps failing the same way on every release looked, from the platform's point of view, identical to a project that failed once — that gap let `lehard/cuby` fail 8 consecutive releases before anyone noticed.

`scripts/rollout_failure_streak.py` closes that gap by keeping a durable, cross-run streak count per managed project:

- on every terminal blocked attempt, it opens or updates a `rollout-failure-streak`-labeled issue on `lehard/dev-platform` (one per actively-failing project), incrementing `consecutive_failures` and recording the latest diagnostic category/reason;
- once `consecutive_failures` reaches **3**, it adds a `rollout-alert` label and emits a distinct `::warning::` annotation naming the project, the streak length, and the tracking issue;
- the next time that project's rollout preparation succeeds, the tracking issue is closed with a resolution note (it is not deleted, so it remains a searchable history);
- an unreadable or missing prior state escalates rather than silently resetting to zero — ambiguity is never treated as "clean."

This runs with the workflow's own default `GITHUB_TOKEN` (`issues: write`), not the cross-repository App token, because it only writes to `lehard/dev-platform` itself. It is strictly additive and best-effort: a failure inside the tracker is surfaced as a warning but never changes the rollout attempt's own pass/fail result, and never pushes, retries, or merges anything.

## Failure handling

The system is intentionally fail-closed.

If an onboarding or rollout job is blocked:

- do not edit `.copier-answers.yml` by hand;
- do not force-push deterministic automation branches;
- inspect the failed job and project ownership conflict;
- resolve project/template ownership in a normal project branch or adoption/update PR;
- rerun the same workflow.

If an open rollout PR already exists for the same version, rollout reports it as already pending and does not rewrite the branch. If the target project is already on the requested version, rollout reports a no-op only when platform version records are coherent.
