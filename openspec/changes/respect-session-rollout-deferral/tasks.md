## 1. Deferral channel and gate

- [x] 1.1 `template/scripts/rollout_preflight.py`: add `DEFER_ROLLOUT_ENV`, strict `rollout_deferred(environ)` (unset/empty -> false, `1` -> true, else `RolloutDeferralError` naming the variable), the `DEFERRED` state, the shared `add_defer_rollout_argument` / `apply_defer_rollout` helpers, and an observe-only deferred branch in `reconcile_pending_rollout` placed after the `harness_mode` gate and before the helper import.
- [x] 1.2 Print the pre-merge announcement (PR, version, merge, local sync, how to defer) immediately before `_merge_rollout_pr`.
- [x] 1.3 `template/scripts/start_task.py`: resolve the deferral once before any rollout observation, pass it to the reconciliation, print the deferred outcome and continue; add `--defer-rollout`.
- [x] 1.4 Add `--defer-rollout` to `start_managed_task.py`, `execute_managed_task.py` and `execute_requirement.py advance` through the shared helpers.
- [x] 1.5 `template/scripts/agent_doctor.py`: report a green pending rollout as one the next start will merge, with the deferral instruction; report the deferral when set.

## 2. Tests

- [x] 2.1 `tests/test_rollout_preflight.py`: deferred + green PR -> `deferred`, merge and sync helpers never called; deferred + pending/blocked -> `deferred`; deferred + nothing pending -> `none`; invalid value raises naming the variable; `harness_mode=project` unchanged; not deferred -> announcement printed before the merge call and merge still happens.
- [x] 2.2 Start-level regression reproducing the original case: pending green rollout + deferral -> the rollout PR stays unmerged and `start_task` completes; the same fixture without the deferral still merges.
- [x] 2.3 Entrypoint tests: each `--defer-rollout` flag sets the variable and reaches the gate; `agent_doctor` message.
- [x] 2.4 Downstream: a rendered downstream project at the installed release shape runs its rendered `start_task.py` with the deferral against a pending rollout and leaves it unmerged.

## 3. Docs

- [x] 3.1 `docs/engineering/agent-workflow.md` and `template/AGENTS.md.jinja`: when the user prohibits rollout in the session, start with `--defer-rollout`/`DEV_PLATFORM_DEFER_ROLLOUT=1`; the deferral is per process, never persistent.

## 4. Delivery

- [ ] 4.1 Required platform checks, truthful verification, archive, retrospectives, publication.
