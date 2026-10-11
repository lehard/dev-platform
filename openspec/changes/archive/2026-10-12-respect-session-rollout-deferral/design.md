## Context

Start reaches the merge through one call: `start_task.start_task` -> `rollout_preflight.reconcile_pending_rollout`. `start_managed_task`, `execute_managed_task` and `execute_requirement` all start through `start_task`, so one gate covers every managed path. Project-owned harnesses may keep their own `start_task`, and `start_managed_task` introspects its signature, so the channel must not add a parameter to `start_task`.

## Decisions

1. **Environment variable as the channel, flags as convenience.** `DEV_PLATFORM_DEFER_ROLLOUT=1` is inherited by subprocesses and by `execute_requirement advance`'s in-process starts, needs no signature change and survives project-owned `start_task` variants. The entrypoint flags only set it. Rejected: a persistent file or config key (it would outlive the session and silently suppress rollout for later tasks).
2. **Strict value parsing.** Unset or empty means no deferral; `1` means deferral; anything else raises `RolloutDeferralError` naming the variable. No truthy-string guessing.
3. **Observe-only while deferred.** The deferral check sits after the existing `harness_mode` gate and before `_load_platform_reconciliation_helpers`, so the merge and sync helpers are never loaded or called. The read-only observation still runs so the skip message names the PR and its state; if observation finds nothing the result is `none`. `blocked`, `pending_checks` and `safe_to_adopt` all become `deferred` because none of them is acted on.
4. **Start continues when deferred.** The user chose to proceed on the current platform state, so a deferred rollout is a printed notice, not a blocker. This does not relax the unchanged rule that, without a deferral, an unsafe or ambiguous rollout blocks start.
5. **Preflight announcement.** The only mutation of shared state in start is the rollout merge plus local `main` sync. It is announced twice before it happens: in `agent_doctor.py` (run first by start) and with a final line immediately before the merge call. Absent the deferral the session has given no prohibition, so the existing policy applies and the merge proceeds; the announcement makes the action visible and tells the agent the one supported way to decline.
6. **No other mutation guarded.** `project_sync.py` only fast-forwards from `origin` and is unchanged.

## Risks

An agent that does not know about the variable still triggers the merge; mitigated by the doctor message, the pre-merge line and the rendered `AGENTS.md` instruction. Starting on an older platform release is the user's explicit choice and is reported on every deferred start.
