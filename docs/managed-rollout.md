# Managed project rollout

Managed rollout removes the human step of remembering which Copier-managed projects need a new Dev Platform release.

The operating model is:

`platform release -> managed registry -> exact Copier update -> project checks -> rollout PR -> downstream CI/review -> merge`

Rollout never performs first-time adoption and never auto-merges by default.

## Registry

`managed-projects.json` is the central project inventory and cross-project write allowlist.

States:

- `managed` — adopted and eligible for automatic rollout PRs;
- `candidate` — active software/project repository where reviewed Dev Platform adoption is still required;
- `excluded` — known repository intentionally outside Dev Platform adoption/rollout, with a required explanatory note.

Only `managed` enters the rollout matrix. `candidate` and `excluded` are both non-mutating states. Keeping excluded repositories explicit prevents omission from becoming an accidental state that someone has to remember later.

Promote a project to `managed` only after its default branch contains a valid `.copier-answers.yml` pointing at `lehard/dev-platform`, platform doctor/checks pass, and the adoption PR has been reviewed and merged. Reclassify an `excluded` repository to `candidate` first if its role changes and software adoption becomes appropriate.

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
   - **Workflows: Read and write** — required because Dev Platform can update downstream `.github/workflows/*` files
   - Metadata remains read-only as required by GitHub.
5. Do not grant organization/account permissions that rollout does not use.
6. Install the App on **`dev-platform` itself** plus repositories intentionally participating in rollout. Initially select `dev-platform` and `planner-agent-lab`; add a downstream repository only when its reviewed adoption is complete and it is being promoted to `managed`.
7. Generate a private key for the App.
8. In `lehard/dev-platform` repository settings add:
   - Actions variable `DEV_PLATFORM_APP_CLIENT_ID` = the App **Client ID**;
   - Actions secret `DEV_PLATFORM_APP_PRIVATE_KEY` = the full generated private key including BEGIN/END lines.

Never commit the private key or a long-lived installation token.

Although the App installation has the permissions above, each rollout job creates **two separately down-scoped short-lived tokens**:

- a `dev-platform` source token with **Contents: read** only, used by Copier to fetch the private template/tag;
- a target-repository token with **Contents: write**, **Pull requests: write** and **Workflows: write**, used to push the rollout branch, including managed workflow-file changes, and create the PR.

This avoids giving the write-capable target token write access to the central platform source. The source token is supplied to Copier through process-only Git configuration and is not written into the project or committed.

The rollout workflow uses the SHA-pinned GitHub-owned `actions/create-github-app-token` action. No PAT is required.

## Automatic release rollout

`publish-version.yml` publishes the immutable release and then dispatches `.github/workflows/rollout.yml` with that exact tag.

Before any cross-repository token is created, rollout confirms the requested tag is an actually published **immutable** GitHub Release. A manually entered but unpublished version is rejected.

For every `managed` repository, rollout:

1. obtains a read-only source token for private `dev-platform` access and a separate write-capable token scoped to the target repository;
2. checks for an already-open PR for `dev-platform/rollout-vX.Y.Z`;
3. checks out the current configured default branch;
4. validates Copier ownership/source/version metadata;
5. runs Copier `9.17.0` against the exact `vX.Y.Z` tag with `--conflict rej`, using the read-only source token only for private template fetches;
6. blocks on `.rej`, Git conflict markers, downgrade attempts, unexpected template source or validation failure;
7. runs `scripts/platform_doctor.py` and selected project checks;
8. commits and pushes a deterministic rollout branch without force using the target token;
9. opens a normal PR using the target token;
10. stops. Merge remains governed by downstream CI/review.

Matrix rollout uses `fail-fast: false`: one blocked project does not prevent clean managed projects from receiving PRs.

## Manual retry

GitHub Actions -> **Roll Out Platform** -> **Run workflow**.

Inputs:

- `version` — exact immutable published tag such as `v1.2.0`; empty uses current `VERSION`;
- `repository` — optional exact `owner/name` to retry only one managed project.

A `candidate` or `excluded` repository is rejected by the registry tool even when manually specified.

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

1. Ensure the repository is represented in `managed-projects.json`; active software projects normally start as `candidate`.
2. Adopt Dev Platform in a dedicated project branch/worktree using `docs/adoption.md`.
3. Review project-specific `AGENTS`, OpenSpec, CI/check mappings and `.gitignore`; do not blindly overwrite them.
4. Merge the clean adoption PR.
5. Install/extend the Dev Platform GitHub App installation to include that repository.
6. Change the central registry entry from `candidate` to `managed` in a reviewed Dev Platform PR.
7. From then on, stable platform releases can create rollout PRs automatically.
