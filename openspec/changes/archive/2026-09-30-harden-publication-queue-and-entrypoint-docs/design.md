# Design: Queue trust boundary and scoped token

## Trust boundary

`pull_request_target` runs the workflow definition from the base branch and checks out the base branch by default, so the worker and its helpers are always the reviewed `main` copy. The worker never executes code from the PR head: it reads PR metadata through the API and uses `git fetch`, `git merge-base` and `git diff` on the PR head as data. The label filter on `publication:queued` is kept, re-keyed to the `pull_request_target` event name. The `schedule` and `workflow_dispatch` triggers already run default-branch code and are unchanged. No step checks out `github.event.pull_request.head` or the merge ref.

## Token scope

`actions/create-github-app-token` receives `owner: ${{ github.repository_owner }}`, `repositories` set to the current repository name and only the permissions the coordinator exercises: `permission-contents: write` (branch update, squash merge) and `permission-pull-requests: write` (queue comments and labels, PR reads and merge). The App keeps Metadata read implicitly. Workflows write is not requested: the coordinator never authors workflow content. Checks and statuses permissions are not requested because the App is not granted them and required-check state is already read with the granted permissions. The repository name comes from a preceding step that derives it from `GITHUB_REPOSITORY` (the `repo_name` output pattern used by rollout), not from `github.event.repository`, because `schedule` event payloads may carry no repository object and an empty `repositories` value would widen the token to every installed repository. The job-level `GITHUB_TOKEN` stays `contents: read`.

## Residual risk

If GitHub requires the workflows permission to update a PR branch whose merge from main carries workflow-file changes, the coordinator reports the refused update as a block with its reason; the operator can widen the permission deliberately rather than carrying it by default.

## Entrypoint docs

The CLI is left unchanged (no dual-position `--id`), because the documented form is the defect. The canonical and template surfaces use `orchestrate_pre_authoring.py --id requirement-N status`. A test extracts every `orchestrate_pre_authoring.py` command line from the instruction surfaces and parses it with the real argument parser so the docs and CLI cannot drift again.
