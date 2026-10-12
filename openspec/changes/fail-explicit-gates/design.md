## Context

The sites share one shape: a required input is absent or unreadable and the code substitutes success. Some are guarded by "compatibility while upgrading" or "Windows fallback" comments; the platform ships these modules together in one release, so the compatibility window does not justify masking a missing module.

## Decisions

- **Mode is explicit.** The scope gate is required exactly when `[capabilities] agent_board` is `true`. A single helper in `agent_board.py` returns that boolean, raising when the key is absent or not a boolean. Callers never infer the mode from the presence of a board file or path.
- **Required means every precondition is checked.** With the gate required: board path configured, file present, valid JSON object, `items` a list, and a claim for the current worktree/branch. Any failure raises through the existing gate-failure mechanism naming which precondition failed. If a documented flow legitimately runs claimless while the capability is on, the implementer stops and reports it instead of weakening the check.
- **Scope gate is not applicable in explicitly declared disposable-checkout modes.** Coordinator checkouts (`--proven-base`, `--contribution-base`) and CI have no machine-local board, so `select_checks.py --scope-gate {enforce,not-applicable}` (default `enforce`) declares the mode explicitly: the coordinator modes imply it, CI workflows pass `--scope-gate not-applicable`, and the run prints `Scope gate not applicable: <reason>`. There is no environment sniffing and no provider detection; local task worktrees always enforce, and with `enforce` every unmet precondition still stops the run. The flag is not a free bypass: `select_checks.py` refuses `--scope-gate not-applicable` with an explicit error in a linked task worktree (git dir differs from the common git dir) or in a checkout holding `.managed-task-state.json`; it is accepted only in a plain checkout such as CI. The coordinator base modes are unchanged.
- **Scope-gate failures are classified.** Every unmet scope-gate precondition, and a missing `main_branch` in the board commands, fails through the cataloged recoverable gate `scope-gate-unavailable` (`gate_failure`), one local helper per concern in `agent_board.py`. `agent_board._merged_into` uses the same three-valued git rule as the queue.
- **Head-move verification never assumes a contract.** `verify_remote_fast_forward` and `verify_historical_external_advance` require an existing, readable `<integration_root>/.dev-platform.toml` naming `main_branch`, apply the three-valued git rule (exit 0 true, exit 1 false, other raise `ContainmentError`) and no longer swallow exceptions. `read_platform_config`'s global default for a missing file is deliberately not changed here.
- **Stand-ins are removed.** The `try/except ImportError` stubs for `agent_board` in `select_checks.py` and `finish_task.py`, and for the shared-workspace module in `_platform_common.py`, are replaced by plain imports.
- **Git answers are three-valued.** One helper in `publication_queue.py` returns `True` for exit 0, `False` for exit 1 and raises `QueueError` (command, exit code, stderr) otherwise; all `--is-ancestor` sites use it. `verify_remote_fast_forward` uses the same rule in its module.
- **Every examined site is classified into exactly one of two categories.** (a) FIXED: absence or corruption is now an explicit error. (b) NOT FAIL-OPEN, legitimate absence: the state is a normal part of the lifecycle (for example, a first admission has no prior record), nothing is substituted, the code has an explicit `None` branch, and the inventory records a per-site justification of why absence there is not a lost record. There is no third category. A site where absence would mean a lost record is always (a). Each `_latest(...) or {}` in `publication_queue.py` (and the equivalent sites in `integration_contour.py`) is classified this way in the inventory below.
- **Malformed trusted records.** Untrusted comments are still ignored (they are not gate input). A trusted record that fails parsing or validation raises `MalformedMarkerError`, a new error class in `candidate_lifecycle.py` (a `RuntimeError` subclass) used by the trusted-record readers `first_record` and `latest_record`, with the comment id in its message. `publication_queue.py` converts it at its shared readers (`_latest`, `_record_comment_id`) into `MalformedRecord`, a `QueueError`, so every queue path that maps `QueueError` handles it; `_transition` (ownership change when the caller refuses other ownership), `worker` (block, or report a confirmed merge) and `_integration_repair` (block) handle it deliberately. `integration_contour.candidate_admitted_at` turns it into `JobBlocked`.
- **No new switches.** No env var or config value re-enables a removed fallback.

## Decision inventory

| Site | Decision |
| --- | --- |
| `agent_board.hard_scope_conflicts` / `enforce_scope_gate` | Fixed: explicit errors when the capability is on; documented non-gate when off |
| `select_checks.py` stand-ins and `main_branch` default | Fixed; the scope gate is not applicable only through the explicit `--scope-gate not-applicable` flag or the coordinator base modes |
| `finish_task.py` `enforce_scope_gate` stand-in | Fixed |
| `publication_queue` superseded-head lineage `or {}` | Fixed |
| `publication_queue` / `integration_contour` other `_latest(...)` / `first_record` sites | Classified per site, each exactly (a) or (b). **(a) FIXED, absence implies a lost record, now an explicit error:** `_earlier_slot_record` (the trusted record whose comment id was just found is unreadable: `QueueError`); `admit` for a `requirement/BR-` composition head without a handoff (no trusted coordinator record at the head: `QueueError`; previously only a misleading "owned task branch" error); `integration_contour.recover_integration_repair` (the derived candidate recognised the repair push from a recorded job, so a missing lineage record is lost: `QueueError`; previously the update marker was written with `previous: null`); a malformed trusted record at any queue reader (`MalformedRecord`, a `QueueError` naming the comment id) and in `candidate_admitted_at` (`JobBlocked`). **(b) NOT FAIL-OPEN, legitimate absence (explicit `None` branch, nothing substituted):** `_transition` exact-head record: a head with no record yet (first transition, or a head the coordinator moved) has nothing to carry forward, and the transition writes the first record for it. `_transition` lineage: a candidate with no persisted record at all is a first admission or one whose admission is governed by its v1 marker alone; the transition writes the first v2 record. `_raise_if_owned_elsewhere` newest record: no trusted record means no record claims the candidate, which is the unowned state the check looks for. `_awaiting_readmission` newest record: with no record there is no earlier admitted head waiting for re-admission, so it returns none. `worker` contribution-identity lookup and `worker` newest record: a v1-only candidate (or one whose v2 comments are all untrusted and ignored by design) has no task identity to classify, and the worker's own `has_v2` branch governs it as the v1 admission alone. `_integration_repair` lineage: the same v1-only state has no recorded attempts to count, so the spent count is zero; a malformed record there blocks the candidate instead |
| `publication_queue` `--is-ancestor ... check=False` sites | Fixed through the three-valued helper |
| `candidate_lifecycle.first_record` / `latest_record` | (a) Fixed: new `MalformedMarkerError` for a malformed trusted record |
| `delegation_containment.verify_remote_fast_forward` | Fixed; also requires the contract file to exist |
| `delegation_containment.verify_historical_external_advance` | Fixed: three-valued git rule, no `except Exception: return False`, no `or "main"`; `model_routing` recovery callers turn `ContainmentError` into `RoutingError` |
| `agent_board._merged_into` | Fixed: three-valued git rule |
| `agent_board` `main_branch` defaults and scope-gate `SystemExit`s | Fixed through the classified `scope-gate-unavailable` gate |
| `dev-platform/source-contract.toml` without `[capabilities]` | Fixed: carries the installed contract's capability table |
| `run_test_groups.resolve_jobs` | Fixed |
| `integration_state.serialized_integration` without `fcntl` | Fixed: unsupported platforms fail explicitly (a Windows locking implementation would be a separate change) |
| `_platform_common` shared-workspace stand-ins | Fixed |

Every row above is category (a), except the (b) sites listed with their justification in the `publication_queue` / `integration_contour` row. A site whose absence would mean a lost record is never recorded as (b).

## Found outside the publication/verification gates, not changed here

They are reported as follow-up work and are not part of this change's inventory.

- `read_platform_config` returns a default contract (including `main_branch = "main"`) when `.dev-platform.toml` is absent; the default is global and many callers rely on it.
- Remaining `.get("main_branch", "main")` defaults in `finish_task.py`, `agent_doctor.py`, `agent_friction.py`, `independent_review.py`, `dev.py` and `model_routing.py`.
- Remaining import stand-ins for `managed_task`, `managed_project_status` and `worktree_cleanup` in `select_checks.py` and `finish_task.py`.
- `fcntl is None` paths that run unlocked in `locked_json` (`_platform_common.py`), `agent_friction.py`, `managed_work_identity.py` and `delegated_write_guard.py`.
- `finish_task.find_board_id` swallows `JSONDecodeError`.
- `os.cpu_count() or 2` in `run_test_groups.resolve_jobs`.

## Risks

- Tasks that run without a board claim while the capability is enabled would now fail; mitigated by running the full suite and reporting, not weakening.
- Downstream projects on an unsupported platform for `fcntl` now fail; this is intended and surfaced in the release note.
- A project whose contract lacks `main_branch` now fails explicitly in protected checks, the board commands and head-move verification; rendered projects always carry the key (`template/.dev-platform.toml.jinja`), so only hand-edited contracts are affected.
