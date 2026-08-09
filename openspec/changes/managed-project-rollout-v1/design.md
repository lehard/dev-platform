# Design: Managed project rollout

## Overview

The central platform owns release identity and rollout orchestration. Downstream repositories continue to own their application code, project-specific rules and final merge decision.

The rollout path is:

`VERSION merge -> immutable release -> workflow_dispatch rollout -> managed registry -> per-project GitHub App token -> exact Copier update -> local validation -> rollout PR -> downstream CI -> human/agent merge`

## Registry

Use a dependency-free JSON file in the central repository. Each entry contains:

- `repository`: exact `owner/name` allowlist value;
- `state`: `managed` or `candidate`;
- `default_branch`;
- optional note.

Only `managed` entries enter the rollout matrix. `candidate` documents observed repositories that still require reviewed adoption but grants no mutation authority.

Registry validation fails on duplicate repositories, malformed names, unsupported states, missing branches or an empty managed set when rollout is requested.

## Authentication

Cross-repository writes use a dedicated GitHub App installation token. The workflow references:

- repository variable `DEV_PLATFORM_APP_CLIENT_ID`;
- repository secret `DEV_PLATFORM_APP_PRIVATE_KEY`.

The App should be installed only on repositories intentionally eligible for platform management and needs only repository metadata/read, Contents read/write and Pull requests read/write. The rollout workflow requests only contents/pull-request permissions from the installation token.

The GitHub-owned `actions/create-github-app-token` action is SHA-pinned. No PAT is required in the normal path.

## Release trigger

`publish-version.yml` remains responsible for immutable tag/release creation. After successful publication it dispatches `rollout.yml` using `workflow_dispatch`, because GitHub deliberately suppresses most workflow chains caused by the repository `GITHUB_TOKEN`, while `workflow_dispatch` is explicitly allowed.

The rollout workflow also exposes manual dispatch with an optional version/repository filter for retries.

## Per-project algorithm

For each managed repository:

1. Generate a repository-scoped GitHub App installation token.
2. Check out the downstream default branch into an isolated directory with App credentials.
3. Confirm `.copier-answers.yml` exists and points to `lehard/dev-platform`.
4. Read the current `_commit`; if it already equals the target tag, report a no-op.
5. Refuse downgrade by normal SemVer ordering.
6. Refuse to overwrite an existing deterministic rollout branch. If an open PR for that branch already exists, report it as already pending and succeed without mutation.
7. Create `dev-platform/rollout-vX.Y.Z` from the freshly fetched default branch.
8. Run Copier `9.17.0` with `update --trust --defaults --vcs-ref vX.Y.Z --conflict rej`.
9. Fail if `.rej` files or Git conflict markers remain, if `_commit` did not become the exact target tag, or if no platform diff exists unexpectedly.
10. Run generated `platform_doctor.py` and `select_checks.py` when present.
11. Commit and push the automation branch without force.
12. Open a normal, non-draft PR. Do not auto-merge.

If a project fails before push, its default branch is untouched. Matrix jobs use `fail-fast: false` so one blocked repository does not stop clean upgrades for others.

## Adoption boundary

Automatic rollout does not perform first-time adoption. Existing repositories without valid Copier metadata remain `candidate` until a reviewed adoption PR lands. Promotion from `candidate` to `managed` is an explicit central registry change.

## Testing

- Pure unit tests validate registry parsing/filtering, answers metadata parsing, version checks, deterministic branch naming and conflict scanning.
- Platform CI validates the registry and compiles rollout tooling.
- Existing Copier upgrade smoke remains the compatibility test for actual template updates.
- Workflow contract tests assert SHA pinning, no auto-merge, exact-version Copier invocation and release dispatch wiring.

## Rollback

Rollout PRs are ordinary reviewed PRs. A blocked or unwanted rollout is closed without changing the downstream default branch. Published platform tags remain immutable; rollback means either leaving a project on its prior `_commit` or publishing a new corrective platform version.
