# Design: Managed project rollout

## Overview

The central platform owns release identity and rollout orchestration. Downstream repositories continue to own their application code, project-specific rules and final merge decision.

The rollout path is:

`VERSION merge -> immutable release -> workflow_dispatch rollout -> managed registry -> source/target GitHub App tokens -> exact Copier update -> local validation -> rollout PR -> downstream CI -> human/agent merge`

## Registry

Use a dependency-free JSON file in the central repository. Each entry contains:

- `repository`: exact `owner/name` repository identity;
- `state`: `managed`, `candidate`, or `excluded`;
- `default_branch`;
- optional note explaining the state.

The registry is intended to be comprehensive for the user's known project repositories so omission does not become an accidental fourth state.

- `managed` enters the rollout matrix and is eligible for cross-repository writes.
- `candidate` is a software/project repository that still requires reviewed adoption; it grants no mutation authority.
- `excluded` is intentionally outside Dev Platform adoption/rollout (for example content-only or empty placeholder repositories); it grants no mutation authority and records why it is excluded.

Registry validation fails on duplicate repositories, malformed names, unsupported states, missing branches or an empty managed set when rollout is requested.

## Authentication

Cross-repository access uses a dedicated GitHub App. The workflow references:

- repository variable `DEV_PLATFORM_APP_CLIENT_ID`;
- repository secret `DEV_PLATFORM_APP_PRIVATE_KEY`.

The App is installed on the central `dev-platform` repository and on repositories intentionally eligible for platform management. Because platform-managed updates can include `.github/workflows/*`, the installation grants repository metadata/read plus Contents read/write, Pull requests read/write and Workflows read/write. Each rollout job then creates two separately down-scoped short-lived tokens:

1. **source token** — scoped only to `dev-platform` with Contents **read** permission, used only so Copier can fetch the private template/version;
2. **target token** — scoped only to the current managed downstream repository with Contents **write**, Pull requests **write** and Workflows **write**, used for checkout/push/PR operations, including platform-managed GitHub Actions workflow changes.

This separation prevents the write-capable target token from also having write access to the central source repository. The source token is passed to Copier only through process environment Git URL rewriting and is not printed or committed.

The GitHub-owned `actions/create-github-app-token` action is SHA-pinned. No PAT is required in the normal path.

## Release trigger

`publish-version.yml` remains responsible for immutable tag/release creation. After successful publication it dispatches `rollout.yml` using `workflow_dispatch`, because GitHub deliberately suppresses most workflow chains caused by the repository `GITHUB_TOKEN`, while `workflow_dispatch` is explicitly allowed.

The rollout workflow also exposes manual dispatch with an optional version/repository filter for retries. Before building a rollout matrix, it confirms that the requested tag is an actually published immutable GitHub Release; syntactically valid but unpublished/non-immutable tags are rejected.

## Per-project algorithm

For each managed repository:

1. Generate a read-only source token for private `dev-platform` template access and a separate write-capable target token for the current managed repository.
2. Check out the downstream default branch into an isolated directory with target App credentials.
3. Confirm `.copier-answers.yml` exists and points to `lehard/dev-platform`.
4. Read the current `_commit`; if it already equals the target tag, report a no-op.
5. Refuse downgrade by normal SemVer ordering.
6. Refuse to overwrite an existing deterministic rollout branch. If an open PR for that branch already exists, report it as already pending and succeed without mutation.
7. Create `dev-platform/rollout-vX.Y.Z` from the freshly fetched default branch.
8. Run Copier `9.17.0` with `update --trust --defaults --vcs-ref vX.Y.Z --conflict rej`, supplying the read-only source token only to Git fetches of the private template.
9. Fail if `.rej` files or Git conflict markers remain, if `_commit` did not become the exact target tag, or if no platform diff exists unexpectedly.
10. Run generated `platform_doctor.py` and `select_checks.py` when present.
11. Commit and push the automation branch without force using the target token.
12. Open a normal, non-draft PR using the target token. Do not auto-merge.

If a project fails before push, its default branch is untouched. Matrix jobs use `fail-fast: false` so one blocked repository does not stop clean upgrades for others.

## Adoption boundary

Automatic rollout does not perform first-time adoption. Existing software repositories without valid Copier metadata remain `candidate` until a reviewed adoption PR lands. Promotion from `candidate` to `managed` is an explicit central registry change. An `excluded` repository must first be deliberately reclassified to `candidate` before adoption work is expected.

## Testing

- Pure unit tests validate registry parsing/filtering, answers metadata parsing, version checks, deterministic branch naming and conflict scanning.
- Platform CI validates the registry and compiles rollout tooling.
- Existing Copier upgrade smoke remains the compatibility test for actual template updates.
- Workflow contract tests assert SHA pinning, split source/target token scopes including workflow-write capability, no auto-merge, exact-version Copier invocation, published-release validation and release dispatch wiring.

## Rollback

Rollout PRs are ordinary reviewed PRs. A blocked or unwanted rollout is closed without changing the downstream default branch. Published platform tags remain immutable; rollback means either leaving a project on its prior `_commit` or publishing a new corrective platform version.
