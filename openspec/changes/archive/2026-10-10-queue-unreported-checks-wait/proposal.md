## Why

The queue's integration step pushes a new head (GitHub `update-branch` merges current `main`) and reads that head's required checks at once. Until GitHub attaches the first check run, `gh pr checks <pr> --required --json ...` exits 1 with empty stdout. `publication_state._observe_required_checks` treats that as `unknown/malformed` whenever the base protection requires checks, so `publication_queue._integrate` raises `QueueError` and the candidate is blocked for human escalation, and `resume` does not cover a publication red gate. This happened to lehard/dev-platform#469: `validate` passed on the same head minutes later. #455, #461 and #468 passed the same step only by timing. The spec pins the defect ("gh reports no required checks while the base requires some" is unusable), and `tests/test_publication_state.py::test_no_required_checks_while_base_requires_some_is_malformed` locks it in. A contribution PR already treats a missing required row as pending, so the two base kinds also disagree.

## What Changes

- `publication_state._observe_required_checks`: for a main-targeted PR, gh exit 1 with empty stdout under a base that requires contexts returns `pending`, with one `{"name": <context>, "state": "EXPECTED"}` row per required context. The detail names the unreported contexts. The contribution path marks a required context with no row, and an App-bound context with no run, as `EXPECTED` instead of `PENDING`. Transport, malformed payloads, head mismatch and unsupported states are unchanged.
- `publication_queue._integrate`: when the existing `CHECK_WAIT_SECONDS` wait expires and the latest observation is pending with only `EXPECTED` rows, the candidate is blocked with a reason that names the unreported checks and the bound. Pending checks that GitHub has reported keep today's non-terminal `waiting` result.
- The spec scenario that calls this condition unusable is replaced by a pending scenario and a bounded-expiry scenario.

## Capabilities

### Modified Capabilities

- `publication-queue`: exact-head required-check observation classifies unreported required checks as pending, and integration bounds the wait for them.

## Impact

`template/scripts/publication_state.py` and `template/scripts/publication_queue.py`. Tests: `tests/test_publication_state.py` and `tests/test_publication_queue.py`. Other consumers of `required_check_state_for_ref` already treat pending as wait or resumable: `project_publish.wait_for_pr_checks` has a bounded completion wait, `rollout_preflight` reports `PENDING_CHECKS`, and `finish_task.resumable_remote_armed_pr` keeps pending resumable. None of them authorizes publication on pending. `publication_state.py` is rendered downstream. Downstream callers see `pending` instead of `unknown/malformed` for this race, and both outcomes refuse to publish.

## Non-goals

Changing which checks are required or branch protection; finalize, review or repair jobs; a new coordinator, queue or App mechanism; retrying other unusable causes.
