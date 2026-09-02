# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review (no `/opsx:verify` tool integration in this environment) against proposal/design/delta spec plus the full local platform test and validation matrix
Automated-Checks-Evidence: automated-checks.json

## Automated validation

Run locally on branch `agent/harden-interrupted-executor-cleanup`:

- `python3 -m compileall -q template/scripts scripts` — OK
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded)
- `python3 scripts/run_test_groups.py --all` — OK (see automated-checks.json)
- `python3 template/scripts/openspec_lifecycle.py check` — OK
- `openspec validate harden-interrupted-executor-cleanup --strict` — valid
- `python3 scripts/select_checks.py --base origin/main` — `high-impact-path`, selection `ready`
  (the executable-surface change maps to the protected full suite, not a bounded subset)

New regression coverage:

- `test_external_interrupt_reaps_process_group_and_classifies_receipt` — an external
  `SIGTERM` to the launcher while the delegated child and a descendant are live is
  funnelled through the existing terminate-and-reap boundary: the whole process
  group is gone, `writer_state` is `released`, the ownership receipt is removed,
  the launcher's prior signal disposition is restored, the abnormal class is
  `external-interrupt`, and the interrupted writer's partial file is preserved and
  reported as bounded `retained_work` (`state=present`, a path count, never a diff).
- `test_failed_reap_after_interrupt_leaves_durable_ambiguous_state` — when
  `_terminate_and_reap` cannot prove the group is absent after an interrupt,
  ownership is marked `ambiguous` with a durable on-disk receipt (`state=ambiguous`,
  `process_group` retained) and a second write-capable launch on that worktree is
  refused with `WriterOwnershipError`.
- `test_normal_completion_is_unclassified_and_restores_signal_handlers` — a clean
  run leaves `abnormal_kind` and `retained_work` unset and restores the inherited
  `SIGTERM`/`SIGINT` handlers, so the scoped handling does not leak.
- `test_child_timeout_cancellation_still_runs_post_check` now also asserts the
  steady-state timeout is classified `timeout`, distinct from `external-interrupt`.
- `test_codex_receipt_classifies_external_interrupt_and_carries_retained_work`,
  `test_codex_receipt_classifies_timeout_distinctly`,
  `test_codex_launcher_boundary_failure_receipt_marks_launch_unavailable` — the
  route receipt distinguishes `external-interrupt` / `timeout` / `launch-unavailable`
  and carries the bounded `retained_work` handoff when one exists.

Existing `test_delegated_write_guard.py` (49) and `test_model_routing.py` (50) pass,
including the unchanged timeout/cancellation, process-group-reap, single-writer and
stale-receipt scenarios.

## Semantic review

Completeness: PASS. Delta requirement "External launcher interruption preserves
single-writer ownership" — `_ScopedInterruptHandlers.arm()` installs handlers for
`SIGTERM`/`SIGHUP`/`SIGINT`/`SIGQUIT` only after a write-capable child is live and
`disarm()` restores them in `finally`; each handler raises `LauncherInterrupted`
(a `BaseException`, so a stray `except Exception` cannot swallow it), which the
pre-existing `except BaseException` path routes through `_terminate_and_reap` on
the full process group. `ownership.release()` still runs only when reap proves the
group absent; otherwise `ownership.mark_ambiguous(...)` writes the durable receipt
and `_WriterOwnership.acquire` continues to fail closed on it. Delta requirement
"Abnormal executor handoff is classified and bounded" — `GuardedRunResult` gains
`abnormal_kind` (`external-interrupt` / `timeout` / `other`) via `_classify_abnormal`
and `retained_work` via `_assigned_worktree_retained_work`, a read-only
`git status --porcelain` reduced to `state` + `changed_path_count` (never file
contents or a diff). `run_codex` mirrors both into the route receipt; the
unlaunched `OSError` boundary is labelled `launch-unavailable`.

Correctness: PASS. Signal handlers are only installed on the main thread of the
main interpreter (`threading.current_thread() is threading.main_thread()`), so the
threaded test/embedded callers keep exactly the prior `BaseException` safety net
and `signal.signal` is never called where it would raise. `disarm()` is
idempotent and runs before the snapshot/containment work in `finally`, so a second
interrupt during cleanup takes the process's restored disposition rather than
re-entering the handler. `KeyboardInterrupt` from a bare `SIGINT` is now uniformly
classified `external-interrupt` instead of taking a differently shaped path.
`retained_work` is computed only when a child actually launched and then ended
abnormally, so a clean completion or an exec-failure-before-launch carries none.
A failed or unreadable `git status` yields `state=unknown` rather than silently
understating retained work.

Coherence: PASS. Code, design and delta agree: the only writer-control mechanism
remains `start_new_session` + process-group identity + the ownership lock/receipt;
cleanup reuses the untouched `_terminate_and_reap`; no daemon, supervisor service,
process queue, automatic retry, or separate telemetry system was added. The change
is confined to `template/scripts/delegated_write_guard.py` and the Codex route
receipt in `template/scripts/model_routing.py` plus their tests, matching the
accepted boundary. The normal success and timeout paths are unchanged apart from
the additional truthful classification field.

## Scope boundary

No runtime supervisor, no automatic executor retry, and no partial-diff quality
analysis were added, per the accepted change boundary. `harness_mode=project`
consumers are unaffected; the Claude in-place handoff path (which launches no
guarded subprocess) is untouched.
