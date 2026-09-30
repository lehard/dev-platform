# Proposal: Harden publication queue trust boundary and fix pre-authoring entrypoint docs

## Why

`.github/workflows/publication-queue.yml` triggers on `pull_request: labeled`. For that event GitHub checks out the PR merge ref, so `python3 scripts/publication_queue.py worker` runs PR-controlled code while `GH_TOKEN` is a Dev Platform GitHub App token that is not scoped beyond the App's installation permissions (contents, pull requests and workflows write). A pull request could therefore run arbitrary code with merge and workflow-write power. Separately, AGENTS.md and the engineering docs show `orchestrate_pre_authoring.py status --id requirement-N`, which the CLI rejects because `--id` belongs to the top-level parser (friction lehard/dev-platform#184); the wrong form would propagate to every managed project on the next release.

## What changes

- The queue workflow uses `pull_request_target` so every trigger runs workflow and worker code from the protected default branch, and the App token step names `owner`, `repositories` and only `permission-contents: write` and `permission-pull-requests: write`.
- The documented pre-authoring command becomes `orchestrate_pre_authoring.py --id requirement-N status` in every canonical and template surface.
- Regression tests cover the workflow trust boundary and token scope, and parse every documented pre-authoring command with the real CLI.

## Success evidence

Regression tests fail on the old workflow and docs and pass after; queue tests and the full suite stay green.

## Constraints and non-goals

Queue admission, ordering, exact-head guard, required checks and absence of bypass or force are unchanged. No release, routing, independent-review or downstream-enablement change, no new subsystem.
