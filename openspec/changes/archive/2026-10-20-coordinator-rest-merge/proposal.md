## Why

With the `main` ruleset (rules `update`, `deletion`, `non_fast_forward`; single bypass actor: the coordinator GitHub App in `pull_request` mode) enabled on 2026-10-20, every queue run refused a green, mergeable PR (#647) with gh's client message "the base branch policy prohibits the merge … add the `--auto` flag … `--admin` flag". `gh pr merge` refuses on the client when `mergeStateStatus` is `BLOCKED`, which GitHub reports for a ruleset-restricted ref even when the viewer is a bypass actor, so the request never reaches the merge API where the bypass applies. The ruleset was rolled back to unblock the queue.

## What Changes

- The coordinator's protected merge uses the REST merge endpoint `PUT repos/{repo}/pulls/{number}/merge` with `merge_method=squash` and `sha=<expected head>` (the same expected-head guard as `--match-head-commit`).
- A refusal keeps the existing `waiting` outcome with the API's bounded error message; the merged fact is still read back from the PR.
- Tests assert the exact REST call and that a 405/409 refusal is reported as a waiting reason without a merge.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `publication-queue`: the protected merge request is a REST merge with an expected-head guard evaluated by GitHub.

## Impact

`template/scripts/publication_queue.py`, `tests/test_publication_queue.py` (and other tests that fake the merge call), regenerated platform manifest. Downstream coordinator copies receive the same merge call through the normal release.

## Non-goals

Changing `project_publish.py`; changing required checks or classic protection; issuing App tokens locally; applying the ruleset (operator step).
