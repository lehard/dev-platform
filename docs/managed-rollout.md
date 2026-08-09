# Managed project rollout

Managed rollout removes the human step of remembering which Copier-managed projects need a new Dev Platform release.

The operating model is:

`platform release -> managed registry -> exact Copier update -> project checks -> rollout PR -> downstream CI/review -> merge`

Rollout never performs first-time adoption and never auto-merges by default.

## Registry

`managed-projects.json` is the cross-project write allowlist.

States:

- `managed` — eligible for automatic rollout PRs;
- `candidate` — known project, but automatic mutation is forbidden until reviewed adoption is complete.

Promote a project to `managed` only after its default branch contains a valid `.copier-answers.yml` pointing at `lehard/dev-platform`, platform doctor/checks pass, and the adoption PR has been reviewed and merged.

Do not automatically discover and mutate every repository owned by the account. The explicit registry is a safety boundary.

Validate locally with:

```bash
python3 scripts/managed_projects.py validate
python3 scripts/managed_projects.py status
```

## One-time GitHub App setup

The repository `GITHUB_TOKEN` is intentionally scoped to `dev-platform`, so cross-repository rollout uses a dedicated GitHub App.

Create a private GitHub App owned by the `lehard` account, for example **Dev Platform Bot**.

Recommended setup:

1. GitHub account **Settings -> Developer settings -> GitHub Apps -> New GitHub App**.
2. Use a descriptive name and the `dev-platform` repository URL as the homepage URL.
3. Webhooks are not required for this workflow; disable webhook delivery unless another use is deliberately added later.
4. Repository permissions:
   - **Contents: Read and write**
   - **Pull requests: Read and write**
   - Metadata remains read-only as required by GitHub.
5. Do not grant organization/account permissions that rollout does not use.
6. Install the App only on the repositories intentionally participating in Dev Platform rollout. Initially that is `planner-agent-lab`; add a repository when its registry state is promoted to `managed`.
7. Generate a private key for the App.
8. In `lehard/dev-platform` repository settings add:
   - Actions variable `DEV_PLATFORM_APP_CLIENT_ID` = the App **Client ID**;
   - Actions secret `DEV_PLATFORM_APP_PRIVATE_KEY` = the full generated private key including BEGIN/END lines.

Never commit the private key or a long-lived installation token.

The rollout workflow uses the SHA-pinned GitHub-owned `actions/create-github-app-token` action and requests only Contents/Pull-request permissions for the single matrix repository being processed.

## Automatic release rollout

`publish-version.yml` publishes the immutable release and then dispatches `.github/workflows/rollout.yml` with that exact tag.

For every `managed` repository, rollout:

1. obtains a repository-scoped GitHub App token;
2. checks for an already-open PR for `dev-platform/rollout-vX.Y.Z`;
3. checks out the current configured default branch;
4. validates Copier ownership/source/version metadata;
5. runs Copier `9.17.0` against the exact `vX.Y.Z` tag with `--conflict rej`;
6. blocks on `.rej`, Git conflict markers, downgrade attempts, unexpected template source or validation failure;
7. runs `scripts/platform_doctor.py` and selected project checks;
8. commits and pushes a deterministic rollout branch without force;
9. opens a normal PR;
10. stops. Merge remains governed by downstream CI/review.

Matrix rollout uses `fail-fast: false`: one blocked project does not prevent clean managed projects from receiving PRs.

## Manual retry

GitHub Actions -> **Roll Out Platform** -> **Run workflow**.

Inputs:

- `version` — exact immutable tag such as `v1.2.0`; empty uses current `VERSION`;
- `repository` — optional exact `owner/name` to retry only one managed project.

A `candidate` repository is rejected by the registry tool even when manually specified.

## Failure handling

The system is intentionally fail-closed.

If a rollout job is blocked:

- do not edit `.copier-answers.yml` by hand;
- do not force-push the deterministic rollout branch;
- inspect the failed job and project ownership conflict;
- resolve project/template ownership in a normal project branch or adoption/update PR;
- rerun rollout for that exact repository/version.

If an open rollout PR already exists for the same version, the job reports it as already pending and does not rewrite the branch.

If the target project is already on the requested version, rollout reports a no-op.

## Adding a new project

1. Adopt Dev Platform in a dedicated project branch/worktree using `docs/adoption.md`.
2. Review project-specific `AGENTS`, OpenSpec, CI/check mappings and `.gitignore`; do not blindly overwrite them.
3. Merge the clean adoption PR.
4. Add/install the Dev Platform GitHub App on that repository.
5. Change the central registry entry from `candidate` to `managed` in a reviewed Dev Platform PR.
6. From then on, stable platform releases can create rollout PRs automatically.
