## Why

Full validation takes 25-50 minutes, and a recurring share of the lost time is a stop *after* it on a condition that was observable beforehand: the board claim dropped after a handoff (`scope-gate-unavailable` after a 50-minute run), a new worktree's Git metadata without group setgid (repeated since September), a new direct file-creation site missing from the writer-guard baseline, a task behind a conflicting main. `select_checks.py --execute` and `finish` already refuse some of these early, but each gate sits at its own place in its own command: the claim and scope gate run only under the freshness branch of the selector, the permission audit runs in `finish` and in `agent_doctor` but never before a selector run, and project test gates such as the writer-guard baseline run only inside the full suite. Nothing records which blocking gate has a cheap early check and which cannot have one, so each new gate repeats the gap.

## What Changes

- New shipped module `lifecycle_preflight.py`: an ordered registry of cheap conditions. Each condition calls the function the corresponding gate already uses (`agent_board.enforce_scope_gate`, `task_reconciliation.observe_candidate`, `shared_workspace` audit and repair) and reports `passed`, `repaired` or `not-applicable` with a stated reason, or refuses with the violated condition and the repair command. All refusals found are reported together; the printed list shows every condition checked and its result.
- `select_checks.py --execute` runs the preflight before the affected-test precheck and any selected command, folding in the freshness and scope checks it already performs inline (same functions, one place). `finish_task.py` runs it before validation, on the handoff path and on a re-submission.
- Shared-workspace condition: a finding on a path owned by the current OS account is repaired and reported as repaired; a finding on a path owned by another account is refused with the exact `chgrp`/`chmod` command and the owner.
- `[settings] preflight_commands` in `checks.toml`: project cheap gates run in the preflight. The platform lists the writer-guard baseline test, the same test the full suite runs.
- `blocking-gates.toml`: every gate carries exactly one of `preflight = "<condition id>"` or `no_preflight = "<reason>"`; the catalog loader rejects an entry with neither or both, and a test resolves each `preflight` id against the registry (and each condition's gates back against the catalog).
- A test proves the gate and its preflight condition give the same answer for the same state.

## Impact

- `template/scripts/{lifecycle_preflight,select_checks,finish_task,shared_workspace,_platform_common}.py`, `template/dev-platform/blocking-gates.toml`, `dev-platform/checks.toml`, `template/dev-platform/protected-surface.toml` (new script classification), `docs/engineering/agent-workflow.md` and the template copy, tests, platform manifest.
- Specs: completion-lifecycle, blocking-check-recovery, shared-workspace (added requirements).
- No change to what any gate accepts or rejects, to the behind-mergeable contract, or to the selected checks.
