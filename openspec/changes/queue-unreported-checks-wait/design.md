## Context

- `publication_state.required_check_state_for_ref` binds the observation to the expected head, then calls `_observe_required_checks`. For a main-targeted PR it runs `gh pr checks <ref> --required --json name,state,workflow,link`:
  - exit 0: the rows are classified by `_classify_required_checks`;
  - exit 1 with empty stdout: the base protection decides. It returns `not_registered` when the base requires nothing, and raises `_Unusable("malformed", "gh reported no required checks while base <b> requires status checks")` otherwise;
  - anything else: transport.
- For a contribution PR (base `requirement/BR-<n>`), the required set comes from `main`'s protection. A required context missing from the rows, or an App-bound context with no run from that App, is appended as `{"state": "PENDING"}`.
- `publication_queue._integrate` loops until `CHECK_WAIT_SECONDS` (240 s), sleeping 10 s between observations:
  - `passed` breaks the loop;
  - `failed` is `IntegrationRepairNeeded`;
  - `not_registered` is blocked at once;
  - `unknown` with cause transport or head-mismatch releases the candidate as `waiting`. Every other unknown cause raises `QueueError`, and the workflow turns that into `blocked-escalation`;
  - a wait that times out on pending returns `{"state": "waiting", "reason": "required CI pending"}`.
- Right after `_prepare` pushes a new head through GitHub `update-branch`, GitHub may take seconds to tens of seconds to attach the workflow's check runs. During that window gh exits 1 with empty stdout for `--required`.

## Decisions

1. **Unreported required contexts are pending.** In `_observe_required_checks`, the main-targeted branch with exit 1 and empty stdout reads `_protected_required_contexts(root, env, base)`. An empty set keeps `not_registered`. A non-empty set returns `RequiredCheckState("pending", "required checks not yet reported on head: <sorted names>", checks=tuple({"name": n, "state": "EXPECTED"} for n in sorted names))`. The contribution branch uses `"EXPECTED"` in place of `"PENDING"` for a missing row and for a missing App-bound run. `EXPECTED` is GitHub's own state for a required context that has not reported, and it is already in `PENDING_CHECK_STATES`, so every consumer still sees `pending`. No other classification changes.
2. **Explicit bound in the queue.** In `_integrate`, keep the last observed state. When the deadline passes and that state is `pending` with only `EXPECTED` rows, first call `_raise_if_owned_elsewhere` (as the `not_registered` block path does, so a block never overwrites a review or repair claim taken while checks ran), then return `_released(_block(root, repo, number, f"required checks were not reported on the integrated head within {CHECK_WAIT_SECONDS} s: {names}", head=head))`. Any other pending observation keeps today's `waiting` result. Not substituting an assumed state is preserved: the candidate is never integrated without passed required checks.
3. **Spec.** In "Exact-head required-check observation", remove "gh reports no required checks while the base requires some" from the unusable scenario. Add a scenario: unreported required checks are pending. Add a second scenario: the queue's bounded wait for unreported checks ends in an explicit block naming them.

## Risks

- A GitHub Actions outage longer than 240 s blocks the candidate explicitly instead of retrying silently. This is the intended explicit failure, and the candidate is re-admitted through the existing path once CI recovers.
- A downstream renderer reading `unknown/malformed` for this case now gets `pending`. Neither value authorizes publication.

## Recovery of lehard/dev-platform#469

The candidate is re-admitted on a new head by its developer through the existing re-admission path. This change is not required for that recovery.
