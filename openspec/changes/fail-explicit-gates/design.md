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
- **`or {}` sites are classified, not blindly changed.** Each `_latest(...) or {}` in `publication_queue.py` is classified: absence legitimate (first admission, no prior record) stays but is spelled as an explicit `None` branch; absence that implies a lost record (superseded-head lineage) raises. The classification is recorded in the inventory below.
- **Malformed trusted records.** Untrusted comments are still ignored (they are not gate input). A trusted record that fails parsing or validation raises the existing malformed-marker error with the comment id.
- **No new switches.** No env var or config value re-enables a removed fallback. Only an explicit owner decision recorded in this inventory keeps a site as it is.

## Decision inventory

| Site | Decision |
| --- | --- |
| `agent_board.hard_scope_conflicts` / `enforce_scope_gate` | Fixed: explicit errors when the capability is on; documented non-gate when off |
| `select_checks.py` stand-ins and `main_branch` default | Fixed; the scope gate is not applicable only through the explicit `--scope-gate not-applicable` flag or the coordinator base modes |
| `finish_task.py` `enforce_scope_gate` stand-in | Fixed |
| `publication_queue` superseded-head lineage `or {}` | Fixed |
| `publication_queue` other `_latest(...) or {}` sites | Classified per site; anomalies fixed, legitimate absence kept as an explicit `None` branch with its reason in the code (no owner decision involved: absence there is a normal state, not a lost record). **Fixed (absence implies a lost record, now raises `QueueError`):** `_earlier_slot_record` (the trusted record whose comment id was just found is unreadable); `admit` for a `requirement/BR-` composition head without a handoff (no trusted coordinator record at the head; previously surfaced only as a misleading "owned task branch" error). **Kept (legitimate absence):** `_transition` exact-head record (first record at a head, or a head the coordinator moved); `_transition` lineage (first admission, or an admission that predates v2 records); `_raise_if_owned_elsewhere` newest record (no trusted record means no record claims the candidate); `_awaiting_readmission` newest record (nothing to re-admit); `worker` contribution-identity lookup and `worker` newest record (v1-only candidate, or v2 comments that are all untrusted and ignored by design); `_integration_repair` lineage (a legacy admission has no attempts to count). A malformed trusted record is no longer one of these absences: it raises `MalformedMarkerError`; `_transition` reports it as an ownership change when the caller refuses other ownership, and `worker` blocks the candidate (or reports a confirmed merge) as it already did for derived malformed markers |
| `publication_queue` `--is-ancestor ... check=False` sites | Fixed through the three-valued helper |
| `candidate_lifecycle.first_record` / `latest_record` | Fixed |
| `delegation_containment.verify_remote_fast_forward` | Fixed; also requires the contract file to exist |
| `delegation_containment.verify_historical_external_advance` | Fixed: three-valued git rule, no `except Exception: return False`, no `or "main"`; `model_routing` recovery callers turn `ContainmentError` into `RoutingError` |
| `agent_board._merged_into` | Fixed: three-valued git rule |
| `agent_board` `main_branch` defaults and scope-gate `SystemExit`s | Fixed through the classified `scope-gate-unavailable` gate |
| `dev-platform/source-contract.toml` without `[capabilities]` | Fixed: carries the installed contract's capability table |
| `run_test_groups.resolve_jobs` | Fixed |
| `integration_state.serialized_integration` without `fcntl` | Fixed: unsupported platforms fail explicitly (owner may later authorize a Windows locking implementation as a separate change) |
| `_platform_common` shared-workspace stand-ins | Fixed |

The implementer completes the classification row for the `publication_queue` `or {}` sites and records any site kept by owner decision with where that decision is written. No site is kept without one.

## Found outside the publication/verification gates, not changed here

These are reported to the owner as follow-up work. They are not owner-kept decisions.

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
